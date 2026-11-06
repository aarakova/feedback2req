"""Replaceable group adapter, compatible with F1's Ollama /api/chat approach."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from .prompt import SYSTEM_PROMPT
from .validation import MAX_JSON_BYTES, GroupingError, decode, response_format

ADAPTER_VERSION = "group-ollama-1.0.0"


class GroupingProvider(Protocol):
    name: str
    model: str
    synthetic: bool

    def group(self, value: dict) -> str | bytes:
        """Return canonical response JSON; no persistence or acceptance here."""
        ...


class Replay:
    """Explicit synthetic response injection; performs no semantic inference."""

    name = "synthetic_replay"
    model = "none"
    synthetic = True

    def __init__(self, response: str | bytes):
        self.response = response

    def group(self, value):
        return self.response


def read_json_bytes(path, *, side="response"):
    try:
        with Path(path).open("rb") as stream:
            raw = stream.read(MAX_JSON_BYTES + 1)
    except OSError:
        code = "invalid_request" if side == "request" else "invalid_response"
        raise GroupingError(code, "file_unreadable") from None
    # Also reject oversized files before handing them to an adapter.
    decode(raw, side=side)
    return raw


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


@dataclass(frozen=True)
class OllamaConfig:
    endpoint: str
    model: str
    transfer_enabled: bool = False
    timeout_seconds: float = 60
    temperature: float = 0
    think: bool = False


class Ollama:
    name = "ollama"
    synthetic = False
    system_prompt = SYSTEM_PROMPT
    response_schema = staticmethod(response_format)

    def __init__(self, config: OllamaConfig):
        self.config = config
        self.model = config.model

    def group(self, value):
        cfg = self.config
        try:
            endpoint = urlsplit(cfg.endpoint)
            valid = (
                cfg.transfer_enabled is True
                and isinstance(cfg.model, str)
                and bool(cfg.model.strip())
                and endpoint.scheme in {"http", "https"}
                and bool(endpoint.hostname)
                and endpoint.port != 0
                and endpoint.username is None
                and endpoint.password is None
                and endpoint.path == "/api/chat"
                and not endpoint.query
                and not endpoint.fragment
                and type(cfg.timeout_seconds) in (int, float)
                and math.isfinite(cfg.timeout_seconds)
                and cfg.timeout_seconds > 0
                and type(cfg.temperature) in (int, float)
                and math.isfinite(cfg.temperature)
                and 0 <= cfg.temperature <= 2
                and type(cfg.think) is bool
            )
        except (TypeError, ValueError):
            valid = False
        if not valid:
            raise GroupingError("provider_error", "provider_not_configured")
        body = {
            "model": cfg.model,
            "stream": False,
            "format": self.response_schema(),
            "options": {"temperature": cfg.temperature},
            "think": cfg.think,
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": json.dumps(value, ensure_ascii=False)},
            ],
        }
        try:
            req = Request(
                cfg.endpoint,
                data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            # Ignore ambient proxies and forbid redirects to another recipient.
            with build_opener(ProxyHandler({}), NoRedirect()).open(
                req, timeout=cfg.timeout_seconds
            ) as response:
                raw = response.read(MAX_JSON_BYTES + 1)
        except TimeoutError:
            raise GroupingError("timeout", "provider_timeout") from None
        except URLError as error:
            if isinstance(error.reason, TimeoutError):
                raise GroupingError("timeout", "provider_timeout") from None
            raise GroupingError("provider_error", "provider_transport") from None
        except Exception:  # noqa: BLE001 -- transport diagnostics must exclude data/URLs.
            raise GroupingError("provider_error", "provider_transport") from None
        envelope = decode(raw)
        if (
            not isinstance(envelope, dict)
            or envelope.get("done") is not True
            or not isinstance(envelope.get("message"), dict)
            or not isinstance(envelope["message"].get("content"), str)
            or envelope["message"].get("tool_calls")
        ):
            raise GroupingError("invalid_response", "provider_envelope")
        return envelope["message"]["content"]
