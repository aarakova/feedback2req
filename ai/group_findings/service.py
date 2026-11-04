"""Single-call boundary for a future worker; no queue, database or publication."""

from collections.abc import Callable
from copy import deepcopy

from .provider import GroupingProvider
from .validation import GroupingError, decode, validate_request, validate_response


def group_findings(
    request: dict,
    provider: GroupingProvider,
    *,
    verify_context: Callable[[dict], None],
) -> dict:
    """Return a validated candidate; raise a safe GroupingError on failure.

    verify_context MUST verify access, project membership, selected states,
    evidence membership, source text/locators/reliability and availability against
    trusted application data, or raise. It receives an isolated copy. The caller
    must recheck current state atomically at publication (no locks during AI).
    """
    value = validate_request(request)
    try:
        verify_context(deepcopy(value))
    except Exception:  # noqa: BLE001 -- trust boundary must not disclose context text.
        raise GroupingError("invalid_request", "context_not_verified") from None
    try:
        raw = provider.group(deepcopy(value))
    except GroupingError as error:
        if (error.code, error.rule) in {
            ("timeout", "provider_timeout"),
            ("provider_error", "provider_not_configured"),
            ("provider_error", "provider_transport"),
            ("invalid_response", "provider_envelope"),
            ("invalid_response", "json_size"),
            ("invalid_response", "json_decode"),
            ("invalid_response", "json_duplicate"),
            ("invalid_response", "json_number"),
            ("invalid_response", "json_type"),
        }:
            raise
        raise GroupingError("provider_error", "provider_failure") from None
    except TimeoutError:
        raise GroupingError("timeout", "provider_timeout") from None
    except Exception:  # noqa: BLE001 -- adapters may contain source text in exceptions.
        raise GroupingError("provider_error", "provider_failure") from None
    return validate_response(value, decode(raw))
