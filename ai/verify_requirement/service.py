"""One verification call and acceptance; backend owns lifecycle and publication."""

from collections.abc import Callable
from copy import deepcopy

from .provider import VerificationProvider
from .validation import (
    ReviewPlan,
    VerificationError,
    decode,
    validate_request,
    validate_response,
)


def verify_requirement(
    request: dict,
    provider: VerificationProvider,
    *,
    verify_context: Callable[[dict], None],
    review_plan: ReviewPlan | None = None,
    required_context=frozenset(),
) -> dict:
    """Verify a snapshot, preserving prior facts and returning only canonical JSON.

    verify_context must raise on wrong access/project/state/scope/history. The
    application independently determines conditionally mandatory history fields.
    A partial ReviewPlan is trusted executor metadata, never model-supplied proof.
    No retries, issue resolutions, human decisions, or persistence occur here.
    """
    value = validate_request(request, required_context=required_context)
    try:
        verify_context(deepcopy(value))
    except Exception:  # noqa: BLE001 -- trust callback errors may include private content.
        raise VerificationError("invalid_request", "context_not_verified") from None
    try:
        raw = provider.verify(deepcopy(value))
    except VerificationError as error:
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
        raise VerificationError("provider_error", "provider_failure") from None
    except TimeoutError:
        raise VerificationError("timeout", "provider_timeout") from None
    except Exception:  # noqa: BLE001 -- do not leak provider responses/URLs in errors.
        raise VerificationError("provider_error", "provider_failure") from None
    return validate_response(value, decode(raw), review_plan=review_plan)
