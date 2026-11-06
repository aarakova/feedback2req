"""Bounded experimental Ollama transport. Fixed loopback; no production changes."""

from __future__ import annotations

import hashlib
import http.client
import json
import math
import re
from copy import deepcopy
from urllib.error import URLError

from ai.group_findings.validation import (
    GroupingError,
    decode,
    response_format,
    validate_request,
)

from .profiles import prompt_profile

ADAPTER_VERSION = "qwen-local-experiment-2"
HOST, PORT = "127.0.0.1", 11435
MODELS = {"qwen3:4b-q4_K_M", "qwen3.5:9b-q4_K_M"}


def require(condition):
    if not condition:
        raise ValueError


def sha(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()
    ).hexdigest()


def config_check(cfg):
    """Closed research configuration, unrelated to approved application contracts."""
    try:
        require(
            set(cfg) - {"prompt_profile"}
            == {
                "model",
                "ollama_version",
                "quantization",
                "timeout_seconds",
                "run_timeout_seconds",
                "max_request_bytes",
                "max_response_bytes",
                "template_token_reserve",
                "think",
                "options",
            }
        )
        require(cfg["model"] in MODELS)
        prompt_profile(cfg)
        require(cfg["ollama_version"] == "0.40.14")
        require(cfg["quantization"] == "Q4_K_M" and cfg["think"] is False)
        for key, low, high in (
            ("timeout_seconds", 1, 600),
            ("run_timeout_seconds", 1, 3600),
            ("max_request_bytes", 1, 1048576),
            ("max_response_bytes", 1, 1048576),
            ("template_token_reserve", 512, 2048),
        ):
            require(type(cfg[key]) is int and low <= cfg[key] <= high)
        options = cfg["options"]
        required = {
            "num_ctx",
            "num_predict",
            "num_thread",
            "num_gpu",
            "temperature",
            "top_p",
            "top_k",
            "min_p",
            "seed",
        }
        require(
            required
            <= options.keys()
            <= required | {"presence_penalty", "repeat_penalty"}
        )
        for key, low, high in (
            ("num_ctx", 2048, 32768),
            ("num_predict", 1, 4096),
            ("num_thread", 1, 8),
            ("num_gpu", 0, 99),
            ("top_k", 1, 100),
            ("seed", 0, 2147483647),
        ):
            require(type(options[key]) is int and low <= options[key] <= high)
        for key, low, high in (
            ("temperature", 0, 2),
            ("top_p", 0, 1),
            ("min_p", 0, 1),
            ("presence_penalty", 0, 2),
            ("repeat_penalty", 0, 2),
        ):
            if key in options:
                require(type(options[key]) in (int, float))
                require(math.isfinite(options[key]) and low <= options[key] <= high)
        require(
            options["num_predict"] + cfg["template_token_reserve"] < options["num_ctx"]
        )
    except (AssertionError, KeyError, TypeError, ValueError):
        raise GroupingError("provider_error", "experiment_config") from None
    return cfg


class ReceivedError(GroupingError):
    """Bounded received bytes are evidence, never part of exception diagnostics."""

    def __init__(self, rule, raw):
        super().__init__("provider_error", rule)
        self.raw = raw


class LocalHTTP:
    """No proxy, redirect, DNS resolution of user-provided hosts or external URL."""

    def __call__(self, path, body, timeout, limit):
        if path not in {"/api/version", "/api/tags", "/api/show", "/api/chat"}:
            raise GroupingError("provider_error", "experiment_path")
        connection = http.client.HTTPConnection(HOST, PORT, timeout=timeout)
        try:
            raw_body = (
                None if body is None else json.dumps(body, ensure_ascii=False).encode()
            )
            connection.request(
                "GET" if body is None else "POST",
                path,
                body=raw_body,
                headers={"Content-Type": "application/json"},
            )
            response = connection.getresponse()
            try:
                raw = response.read(limit + 1)
            except http.client.IncompleteRead as error:
                raise ReceivedError(
                    "incomplete_http_body", error.partial[: limit + 1]
                ) from None
            if response.status != 200:
                # Never follow a redirect or include server error text in diagnostics.
                raise ReceivedError("http_status", raw)
            return raw
        finally:
            connection.close()


class ExperimentalOllama:
    name, synthetic = "ollama_local_experiment", False

    def __init__(self, cfg, *, enabled=False, transport=None):
        self.cfg = deepcopy(config_check(cfg))
        self.prompt_name, self.prompt_version, self.system_prompt = prompt_profile(cfg)
        self.model = cfg["model"]
        self.enabled = enabled is True
        self.transport = transport if transport is not None else LocalHTTP()
        self.raw = None
        self.content = None
        self.request_attempted = False
        self.metrics = {}

    def call(self, path, body=None):
        if not self.enabled:
            raise GroupingError("provider_error", "transfer_disabled")
        if path == "/api/chat":
            self.request_attempted = True
        try:
            return self.transport(
                path, body, self.cfg["timeout_seconds"], self.cfg["max_response_bytes"]
            )
        except ReceivedError as error:
            if path == "/api/chat":
                self.raw = error.raw
            raise
        except GroupingError:
            raise
        except TimeoutError:
            raise GroupingError("timeout", "provider_timeout") from None
        except (OSError, URLError, http.client.HTTPException):
            raise GroupingError("provider_error", "provider_transport") from None

    def identity(self):
        def metadata(path, body=None):
            raw = self.call(path, body)
            if len(raw) > self.cfg["max_response_bytes"]:
                raise GroupingError("invalid_response", "metadata_bytes")
            return decode(raw)

        version = metadata("/api/version")
        tags = metadata("/api/tags")
        show = metadata("/api/show", {"model": self.model})
        try:
            require(version["version"] == self.cfg["ollama_version"])
            matches = [m for m in tags["models"] if m["name"] == self.model]
            require(len(matches) == 1)
            model = matches[0]
            require(
                not any(
                    x.get("remote_host") or x.get("remote_model") for x in (model, show)
                )
            )
            require(re.fullmatch(r"(?:sha256:)?[0-9a-f]{64}", model["digest"]))
            require(type(model["size"]) is int and model["size"] > 0)
            require(show["details"]["quantization_level"] == self.cfg["quantization"])
            require("completion" in show["capabilities"])
            require(isinstance(show["template"], str) and show["template"])
            require(isinstance(show["model_info"], dict))
        except (ValueError, KeyError, TypeError):
            raise GroupingError("provider_error", "runtime_identity") from None
        return {
            "model": self.model,
            "digest": model["digest"],
            "size_bytes": model["size"],
            "quantization": self.cfg["quantization"],
            "ollama_version": version["version"],
            "template_sha256": sha(show["template"]),
            "show_sha256": sha(show),
            "config_sha256": sha(self.cfg),
            "prompt_profile": self.prompt_name,
            "prompt_version": self.prompt_version,
            "prompt_sha256": sha(self.system_prompt),
        }

    def group(self, request):
        self.raw, self.content, self.metrics = None, None, {}
        self.request_attempted = False
        request = validate_request(request)
        text = json.dumps(request, ensure_ascii=False, allow_nan=False)
        if len(text.encode()) > self.cfg["max_request_bytes"]:
            raise GroupingError("invalid_request", "input_bytes")
        # Conservative UTF-8 byte bound for BPE message tokens; explicit template
        # reserve. Grammar is sent in format, not duplicated into message content.
        upper = len(self.system_prompt.encode()) + len(text.encode())
        upper += self.cfg["template_token_reserve"] + self.cfg["options"]["num_predict"]
        if upper > self.cfg["options"]["num_ctx"]:
            raise GroupingError("invalid_request", "context_budget")
        body = {
            "model": self.model,
            "stream": False,
            "think": False,
            "keep_alive": 0,
            "format": response_format(),
            "options": self.cfg["options"],
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": text},
            ],
        }
        self.raw = self.call("/api/chat", body)
        if len(self.raw) > self.cfg["max_response_bytes"]:
            raise GroupingError("invalid_response", "response_bytes")
        envelope = decode(self.raw)
        if not isinstance(envelope, dict):
            raise GroupingError("invalid_response", "provider_envelope")
        for key in (
            "total_duration",
            "load_duration",
            "prompt_eval_count",
            "prompt_eval_duration",
            "eval_count",
            "eval_duration",
        ):
            number = envelope.get(key)
            self.metrics[key] = number if type(number) is int and number >= 0 else None
        message = envelope.get("message")
        if isinstance(message, dict) and isinstance(message.get("content"), str):
            self.content = message["content"]
        if (
            envelope.get("done") is not True
            or envelope.get("model") != self.model
            or not isinstance(message, dict)
            or message.get("role") != "assistant"
            or not isinstance(message.get("content"), str)
            or message.get("tool_calls")
            or message.get("thinking")
        ):
            raise GroupingError("invalid_response", "provider_envelope")
        if envelope.get("done_reason") != "stop":
            raise GroupingError("invalid_response", "generation_incomplete")
        if self.metrics["prompt_eval_count"] is None:
            raise GroupingError("invalid_response", "prompt_measurement_missing")
        if (
            self.metrics["prompt_eval_count"] + self.cfg["options"]["num_predict"]
            > self.cfg["options"]["num_ctx"]
        ):
            raise GroupingError("invalid_response", "context_exhausted")
        return message["content"]
