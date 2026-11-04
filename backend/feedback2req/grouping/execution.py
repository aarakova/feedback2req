"""Internal F2/component bridge. No public command or default model/provider."""

from ai.group_findings import GroupingError, group_findings

from feedback2req.errors import AppError
from feedback2req.grouping.service import (
    Provenance,
    accept_grouping,
    build_request,
    current,
    fail_grouping,
    prepare_grouping,
    renew_grouping,
    result_view,
)
from feedback2req.persistence.processing import Attempt, Unit
from feedback2req.processing.service import Heartbeat, locked, owned

HEARTBEAT_SECONDS = 5


class GroupingHeartbeat(Heartbeat):
    def loop(self):
        while not self.stop.wait(HEARTBEAT_SECONDS):
            try:
                if not renew_grouping(self.sessions, self.unit_id, self.token):
                    self.lost.set()
                    return
            except Exception:
                self.lost.set()
                return


def verify_context(sessions, unit_id, owner_token, request):
    """Verify live data in a short transaction; release all locks before compute."""
    with sessions.begin() as tx:
        pair = locked(tx, unit_id)
        if pair is None or not owned(tx, pair[1], owner_token):
            raise AppError(409, "attempt_not_owned", "Grouping context expired")
        unit, attempt = pair
        current(tx, unit)
        if request != build_request(tx, unit, attempt):
            raise AppError(409, "input_changed", "Grouping context changed")


def failure_reason(error):
    if error.rule == "provider_not_configured":
        return "provider_not_configured"
    if error.code == "invalid_response":
        return "invalid_response"
    if error.code in {"timeout", "provider_error"}:
        return "provider_error"
    return "execution_error"


def execute_grouping(
    sessions,
    identity,
    session_token,
    project_id,
    command_key,
    finding_refs,
    *,
    provider,
    document_refs=(),
    previous_group_refs=(),
):
    """Run an explicitly supplied adapter once, then atomically accept its candidate.

    The caller must separately authorize/configure any real provider and ensure
    its timeout fits the attempt deadline. This function never selects a model,
    retries a call or catches a publication/COMMIT failure.
    """
    provenance = Provenance(provider.name, provider.model, provider.synthetic)
    handle = prepare_grouping(
        sessions,
        identity,
        session_token,
        project_id,
        command_key,
        finding_refs,
        document_refs=document_refs,
        previous_group_refs=previous_group_refs,
        provenance=provenance,
    )
    if handle["replayed"]:
        with sessions() as tx:
            unit = tx.get(Unit, handle["unit_id"])
            current(tx, unit)
            result = result_view(tx, unit, tx.get(Attempt, handle["attempt_id"]))
    else:
        heartbeat = GroupingHeartbeat(sessions, handle["unit_id"], handle["owner_token"])
        heartbeat.thread.start()
        candidate, failure = None, None
        try:
            candidate = group_findings(
                handle["request"],
                provider,
                verify_context=lambda request: verify_context(
                    sessions,
                    handle["unit_id"],
                    handle["owner_token"],
                    request,
                ),
            )
        except GroupingError as error:
            failure = failure_reason(error)
        except Exception:
            # Persist stable codes only; adapter exceptions may contain source text.
            failure = "execution_error"
        finally:
            heartbeat.stop.set()
            heartbeat.thread.join(timeout=10)
        if heartbeat.lost.is_set() or heartbeat.thread.is_alive():
            raise AppError(409, "attempt_not_owned", "Grouping execution lost ownership")
        # Deliberately outside the compute error handler: unknown COMMIT must escape.
        if failure:
            result = fail_grouping(sessions, handle["unit_id"], handle["owner_token"], failure)
        else:
            result = accept_grouping(sessions, handle["unit_id"], handle["owner_token"], candidate)
    return {
        "run_id": handle["run_id"],
        "unit_id": handle["unit_id"],
        "attempt_id": handle["attempt_id"],
        "replayed": handle["replayed"],
        "result": result,
    }
