"""Generation interface, reusing the gated Ollama transport and synthetic replay."""

from typing import Protocol

from ai.group_findings.provider import Ollama as GroupOllama
from ai.group_findings.provider import OllamaConfig
from ai.group_findings.provider import Replay as GroupReplay
from ai.group_findings.provider import read_json_bytes as shared_read
from ai.group_findings.validation import GroupingError

from .prompt import SYSTEM_PROMPT
from .validation import GenerationError, response_format

ADAPTER_VERSION = "generate-ollama-1.0.0"
__all__ = [
    "ADAPTER_VERSION",
    "GenerationProvider",
    "Ollama",
    "OllamaConfig",
    "Replay",
    "read_json_bytes",
]


class GenerationProvider(Protocol):
    name: str
    model: str
    synthetic: bool

    def generate(self, request: dict) -> str | bytes:
        """Return canonical response JSON, without publishing or persisting it."""
        ...


class Replay(GroupReplay):
    def generate(self, request):
        return self.group(request)


class Ollama(GroupOllama):
    system_prompt = SYSTEM_PROMPT
    response_schema = staticmethod(response_format)

    def generate(self, request):
        try:
            return self.group(request)
        except GroupingError as error:
            raise GenerationError(error.code, error.rule) from None


def read_json_bytes(path, *, side="response"):
    try:
        return shared_read(path, side=side)
    except GroupingError as error:
        raise GenerationError(error.code, error.rule) from None
