"""Verification adapters reuse the existing gated Ollama transport and replay."""

from typing import Protocol

from ai.group_findings.provider import Ollama as BaseOllama
from ai.group_findings.provider import OllamaConfig
from ai.group_findings.provider import Replay as BaseReplay
from ai.group_findings.provider import read_json_bytes as shared_read
from ai.group_findings.validation import GroupingError

from .prompt import SYSTEM_PROMPT
from .validation import VerificationError, response_format

ADAPTER_VERSION = "verify-ollama-1.0.0"
__all__ = [
    "ADAPTER_VERSION",
    "Ollama",
    "OllamaConfig",
    "Replay",
    "VerificationProvider",
    "read_json_bytes",
]


class VerificationProvider(Protocol):
    name: str
    model: str
    synthetic: bool

    def verify(self, request: dict) -> str | bytes:
        """Return canonical response JSON without accepting or storing it."""
        ...


class Replay(BaseReplay):
    def verify(self, request):
        return self.group(request)


class Ollama(BaseOllama):
    system_prompt = SYSTEM_PROMPT
    response_schema = staticmethod(response_format)

    def verify(self, request):
        try:
            return self.group(request)
        except GroupingError as error:
            raise VerificationError(error.code, error.rule) from None


def read_json_bytes(path, *, side="response"):
    try:
        return shared_read(path, side=side)
    except GroupingError as error:
        raise VerificationError(error.code, error.rule) from None
