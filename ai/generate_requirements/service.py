"""Single-call generator boundary. Backend owns permission, state and publication."""

from collections.abc import Callable
from copy import deepcopy

from .provider import GenerationProvider
from .validation import GenerationError, decode, validate_request, validate_response


def generate_requirements(
    request: dict,
    provider: GenerationProvider,
    *,
    verify_context: Callable[[dict], None],
) -> dict:
    """Check input, verify trusted application facts, call once, accept whole output.

    verify_context must raise if access/project/state/evidence checks fail. It is
    mandatory; callers must also recheck current state atomically at publication.
    Copies protect the snapshot from verifier/adapter mutation. No automatic retry.
    """
    value = validate_request(request)
    try:
        verify_context(deepcopy(value))
    except Exception:  # noqa: BLE001 -- callback errors can disclose source content.
        raise GenerationError("invalid_request", "context_not_verified") from None
    try:
        raw = provider.generate(deepcopy(value))
    except GenerationError as error:
        if (error.code, error.rule) in {
            ("timeout", "provider_timeout"),
            ("provider_error", "provider_not_configured"),
            ("provider_error", "provider_transport"),
            ("invalid_response", "provider_envelope"),
            *(
                ("invalid_response", "json_" + rule)
                for rule in ("size", "decode", "duplicate", "number", "type")
            ),
        }:
            raise
        raise GenerationError("provider_error", "provider_failure") from None
    except TimeoutError:
        raise GenerationError("timeout", "provider_timeout") from None
    except Exception:  # noqa: BLE001 -- provider errors can disclose material or URL.
        raise GenerationError("provider_error", "provider_failure") from None
    return validate_response(value, decode(raw))
