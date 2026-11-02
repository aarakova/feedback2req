import hashlib
import json
import threading
from datetime import timedelta
from uuid import uuid4

from sqlalchemy import create_engine, func, or_, select, update
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from feedback2req.errors import AppError
from feedback2req.persistence.models import (
    DocumentState,
    FeedbackSource,
    ProductDocument,
    SourceTextState,
)
from feedback2req.persistence.processing import (
    Attempt,
    Finding,
    FindingEvidence,
    Fragment,
    Run,
    Unit,
)
from feedback2req.processing import validation
from feedback2req.processing.provider import Ollama, ProviderError
from feedback2req.projects.service import require_project

LEASE = 30
DEADLINE = 120


def worker_database(url):
    existing_options = make_url(url).query.get("options", "")
    engine = create_engine(
        url,
        hide_parameters=True,
        pool_pre_ping=True,
        pool_size=2,
        max_overflow=0,
        pool_timeout=3,
        connect_args={
            "connect_timeout": 3,
            "options": existing_options
            + " -clock_timeout=2000 -cstatement_timeout=5000 -ctransaction_timeout=8000",
        },
    )
    return engine, sessionmaker(engine, expire_on_commit=False)


def input_ref(unit):
    source = unit.source_id is not None
    return {
        "kind": "source" if source else "document",
        "id": str(unit.source_id if source else unit.document_id),
        "state_id": str(unit.source_state_id if source else unit.document_state_id),
    }


def validate_input(tx, project_id, ref):
    source = ref["kind"] == "source"
    header = FeedbackSource if source else ProductDocument
    material = tx.scalar(
        select(header).where(header.project_id == project_id, header.id == ref["id"])
    )
    if material is None:
        raise AppError(404, "not_found", "Project or object not found")
    state = tx.scalar(
        select(SourceTextState).where(
            SourceTextState.project_id == project_id, SourceTextState.id == ref["state_id"]
        )
    )
    document_state = tx.scalar(
        select(DocumentState).where(
            DocumentState.project_id == project_id, DocumentState.id == ref["state_id"]
        )
    )
    matched = state if source else document_state
    if state is None and document_state is None:
        raise AppError(404, "not_found", "Project or object not found")
    if matched is None or (matched.source_id if source else matched.document_id) != material.id:
        raise AppError(422, "invalid_input", "Input must belong to the selected material")
    if material.current_state_id != matched.id:
        raise AppError(409, "input_changed", "Input is no longer current")
    if source and material.availability != "available":
        raise AppError(409, "input_changed", "Input is no longer available")
    return matched


def fingerprint(body):
    return hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def command(tx, project_id, actor_id, key, operation, inputs, *, retry=None):
    require_project(tx, project_id, actor_id, write=True)
    kind = "retry" if retry else "start"
    refs = sorted(inputs, key=lambda ref: (ref["kind"], str(ref["id"])))
    canonical = {
        "operation": operation,
        "inputs": [{k: str(v) for k, v in ref.items()} for ref in refs],
        "retry": str(retry) if retry else None,
    }
    digest = fingerprint(canonical)
    previous = tx.scalar(
        select(Run).where(
            Run.project_id == project_id,
            Run.initiated_by == actor_id,
            Run.command_kind == kind,
            Run.idempotency_key == key,
        )
    )
    if previous:
        if previous.fingerprint != digest:
            raise AppError(409, "idempotency_conflict", "Key already identifies another command")
        return previous
    if len({(ref["kind"], ref["id"]) for ref in refs}) != len(refs):
        raise AppError(422, "invalid_input", "Duplicate input material")
    for ref in refs:
        if operation == "extract_feedback" and ref["kind"] != "source":
            raise AppError(422, "invalid_input", "Extraction requires feedback text")
        validate_input(tx, project_id, ref)
    if retry:
        old = tx.scalar(
            select(Attempt).where(Attempt.project_id == project_id, Attempt.id == retry)
        )
        if old is None or old.state != "failed":
            raise AppError(409, "retry_not_allowed", "Only failed attempts can be retried")
        if tx.scalar(select(Unit.id).where(Unit.retry_of_attempt_id == retry)):
            raise AppError(409, "retry_already_requested", "Retry already exists")
    run = Run(
        id=uuid4(),
        project_id=project_id,
        initiated_by=actor_id,
        operation=operation,
        command_kind=kind,
        idempotency_key=key,
        fingerprint=digest,
    )
    tx.add(run)
    tx.flush()
    for ref in refs:
        tx.add(
            Unit(
                project_id=project_id,
                run_id=run.id,
                retry_of_attempt_id=retry,
                **{
                    ("source_id" if ref["kind"] == "source" else "document_id"): ref["id"],
                    ("source_state_id" if ref["kind"] == "source" else "document_state_id"): ref[
                        "state_id"
                    ],
                },
            )
        )
    tx.flush()
    return run


def aggregate(states):
    if all(state == "queued" for state in states):
        return "queued"
    if any(state in {"queued", "running"} for state in states):
        return "running"
    return states[0] if len(set(states)) == 1 else "partial"


def run_view(tx, run):
    rows = tx.execute(
        select(Unit, Attempt)
        .outerjoin(Attempt, Attempt.unit_id == Unit.id)
        .where(Unit.run_id == run.id, Unit.project_id == run.project_id)
        .order_by(Unit.id)
    ).all()
    units = []
    for unit, attempt in rows:
        view = None
        if attempt:
            finding_ids = list(
                tx.scalars(select(Finding.id).where(Finding.attempt_id == attempt.id))
            )
            fragment_ids = list(
                tx.scalars(select(Fragment.id).where(Fragment.attempt_id == attempt.id))
            )
            view = {
                key: getattr(attempt, key)
                for key in (
                    "id",
                    "request_id",
                    "state",
                    "started_at",
                    "finished_at",
                    "reason_code",
                    "provider",
                    "model",
                    "synthetic",
                    "ai_performed",
                    "coverage",
                    "annotations",
                )
            }
            view["finding_ids"] = finding_ids
            view["fragment_ids"] = fragment_ids
            view["technical_result"] = (
                {
                    "character_count": attempt.character_count,
                    "utf8_byte_count": attempt.utf8_byte_count,
                }
                if attempt.character_count is not None
                else None
            )
        units.append(
            {
                "id": unit.id,
                "input": input_ref(unit),
                "state": unit.state,
                "retry_of_attempt_id": unit.retry_of_attempt_id,
                "attempt": view,
            }
        )
    return {
        "id": run.id,
        "operation": run.operation,
        "created_at": run.created_at,
        "execution_kind": "technical" if run.operation == "inspect_text" else "semantic",
        "state": aggregate([unit["state"] for unit in units]),
        "units": units,
    }


def locked(tx, unit_id):
    candidate = tx.get(Unit, unit_id)
    if candidate is None:
        return None
    from feedback2req.persistence.models import Project

    if (
        tx.scalar(select(Project).where(Project.id == candidate.project_id).with_for_update())
        is None
    ):
        return None
    unit = tx.scalar(
        select(Unit)
        .where(Unit.id == unit_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    attempt = tx.scalar(select(Attempt).where(Attempt.unit_id == unit.id).with_for_update())
    return unit, attempt


def now(tx):
    return tx.scalar(select(func.clock_timestamp()))


def owned(tx, attempt, token):
    instant = now(tx)
    return (
        attempt is not None
        and attempt.state == "running"
        and attempt.owner_token == token
        and attempt.lease_expires_at > instant
        and attempt.deadline_at > instant
    )


def end(tx, unit, attempt, state, reason=None, token=None):
    if token is not None:
        changed = tx.execute(
            update(Attempt)
            .where(
                Attempt.id == attempt.id,
                Attempt.state == "running",
                Attempt.owner_token == token,
                Attempt.lease_expires_at > func.clock_timestamp(),
                Attempt.deadline_at > func.clock_timestamp(),
            )
            .values(
                state=state,
                reason_code=reason,
                owner_token=None,
                lease_expires_at=None,
                finished_at=func.clock_timestamp(),
            )
            .execution_options(synchronize_session=False)
        )
        if changed.rowcount != 1:
            raise RuntimeError("Attempt ownership expired")
        unit.state = state
        return
    unit.state = attempt.state = state
    attempt.finished_at = now(tx)
    attempt.reason_code = reason
    attempt.owner_token = attempt.lease_expires_at = None


def current_input(tx, unit, run):
    try:
        require_project(tx, unit.project_id, run.initiated_by)
    except AppError:
        return None, "access_revoked"
    ref = input_ref(unit)
    from uuid import UUID

    ref = {k: UUID(v) if k != "kind" else v for k, v in ref.items()}
    try:
        return validate_input(tx, unit.project_id, ref), None
    except AppError:
        return None, "input_changed"


def recover_one(sessions):
    with sessions.begin() as tx:
        unit_id = tx.scalar(
            select(Attempt.unit_id)
            .where(
                Attempt.state == "running",
                or_(
                    Attempt.lease_expires_at <= func.clock_timestamp(),
                    Attempt.deadline_at <= func.clock_timestamp(),
                ),
            )
            .order_by(Attempt.started_at)
            .limit(1)
        )
        pair = locked(tx, unit_id) if unit_id else None
        if pair:
            unit, attempt = pair
            instant = now(tx)
            if (
                attempt.state == "running"
                and min(attempt.deadline_at, attempt.lease_expires_at) <= instant
            ):
                reason = "deadline_exceeded" if attempt.deadline_at <= instant else "lease_expired"
                end(tx, unit, attempt, "failed", reason)


def claim(sessions):
    with sessions.begin() as tx:
        unit_id = tx.scalar(
            select(Unit.id)
            .where(Unit.state == "queued")
            .order_by(Unit.created_at, Unit.id)
            .limit(1)
        )
        pair = locked(tx, unit_id) if unit_id else None
        if pair is None or pair[0].state != "queued":
            return None
        unit, _ = pair
        run = tx.get(Run, unit.run_id)
        _, reason = current_input(tx, unit, run)
        instant, token = now(tx), uuid4()
        attempt = Attempt(
            id=uuid4(),
            project_id=unit.project_id,
            unit_id=unit.id,
            state="running",
            owner_token=token,
            started_at=instant,
            deadline_at=instant + timedelta(seconds=DEADLINE),
            lease_expires_at=instant + timedelta(seconds=LEASE),
        )
        tx.add(attempt)
        unit.state = "running"
        if reason:
            end(tx, unit, attempt, "cancelled", reason)
        return (unit.id, token) if not reason else None
    # Returning from with occurs only after a confirmed commit. A lost commit
    # acknowledgement raises; the caller must exit without invoking a provider.


class Heartbeat:
    def __init__(self, sessions, unit_id, token):
        self.sessions, self.unit_id, self.token = sessions, unit_id, token
        self.stop = threading.Event()
        self.lost = threading.Event()
        self.thread = threading.Thread(target=self.loop, daemon=True)

    def loop(self):
        while not self.stop.wait(5):
            try:
                with self.sessions.begin() as tx:
                    pair = locked(tx, self.unit_id)
                    if pair is None or not owned(tx, pair[1], self.token):
                        self.lost.set()
                        return
                    pair[1].lease_expires_at = min(
                        now(tx) + timedelta(seconds=LEASE), pair[1].deadline_at
                    )
            except Exception:
                self.lost.set()
                return


def execute_one(sessions, settings, provider=None):
    recover_one(sessions)
    claimed = claim(sessions)
    if claimed is None:
        return False
    unit_id, token = claimed
    adapter = provider or Ollama(settings)
    with sessions.begin() as tx:
        pair = locked(tx, unit_id)
        if pair is None or not owned(tx, pair[1], token):
            return True
        unit, attempt = pair
        run = tx.get(Run, unit.run_id)
        state, reason = current_input(tx, unit, run)
        if reason:
            end(tx, unit, attempt, "cancelled", reason, token)
            return True
        operation, text = run.operation, state.text
        if operation == "extract_feedback":
            attempt.provider, attempt.model = adapter.name, adapter.model
            attempt.synthetic = adapter.synthetic
            attempt.ai_performed = False if adapter.synthetic else None
        req = (
            validation.request(
                unit.project_id, attempt.request_id, unit.source_id, unit.source_state_id, text
            )
            if operation == "extract_feedback"
            else None
        )
    heartbeat = Heartbeat(sessions, unit_id, token)
    heartbeat.thread.start()
    response, positions, failure = None, None, None
    try:
        if req:
            response = adapter.extract(req)
            positions = validation.accept(req, response)
    except validation.InvalidResponse:
        failure = "invalid_response"
    except ProviderError as exc:
        failure = exc.code
    except Exception:
        failure = "execution_error"
    finally:
        heartbeat.stop.set()
        heartbeat.thread.join(timeout=10)
    if heartbeat.lost.is_set() or heartbeat.thread.is_alive():
        return True
    # Exactly one completion transaction. Any exception, including unknown commit,
    # escapes the child; do not catch it and write a second outcome.
    with sessions.begin() as tx:
        pair = locked(tx, unit_id)
        if pair is None or not owned(tx, pair[1], token):
            return True
        unit, attempt = pair
        run = tx.get(Run, unit.run_id)
        _, reason = current_input(tx, unit, run)
        if reason:
            end(tx, unit, attempt, "cancelled", reason, token)
            return True
        if req:
            attempt.provider, attempt.model = adapter.name, adapter.model
            attempt.synthetic = adapter.synthetic
            attempt.ai_performed = (
                False
                if adapter.synthetic or failure == "provider_not_configured"
                else True
                if response is not None
                else None
            )
        if failure:
            end(tx, unit, attempt, "failed", failure, token)
            return True
        if req:
            mapping = {}
            for item in response["result"]["fragments"]:
                fragment_id = mapping[item["local_id"]] = uuid4()
                start, finish = positions[item["local_id"]]
                tx.add(
                    Fragment(
                        id=fragment_id,
                        project_id=unit.project_id,
                        attempt_id=attempt.id,
                        local_id=item["local_id"],
                        source_id=unit.source_id,
                        source_state_id=unit.source_state_id,
                        quote=item["quote"],
                        start=start,
                        end=finish,
                        reliability="usable",
                    )
                )
            tx.flush()
            for item in response["result"]["findings"]:
                finding_id = mapping[item["local_id"]] = uuid4()
                tx.add(
                    Finding(
                        id=finding_id,
                        project_id=unit.project_id,
                        attempt_id=attempt.id,
                        local_id=item["local_id"],
                        text=item["text"],
                        types=item["types"],
                        mode=item["mode"],
                    )
                )
                tx.flush()
                for fragment in item["fragment_ids"]:
                    tx.add(
                        FindingEvidence(
                            project_id=unit.project_id,
                            finding_id=finding_id,
                            fragment_id=mapping[fragment],
                        )
                    )
            attempt.coverage = response["coverage"]
            annotations = {
                "questions": response["questions"],
                "uncertainties": response["uncertainties"],
            }
            annotations = json.loads(json.dumps(annotations))
            for item in annotations["questions"] + annotations["uncertainties"]:
                for link in item["related"]:
                    link["id"] = str(unit.id if link["origin"] == "input" else mapping[link["key"]])
            attempt.annotations = annotations
        else:
            attempt.character_count, attempt.utf8_byte_count = len(text), len(text.encode("utf-8"))
        tx.flush()
        # Recheck after all SQL/flush work, immediately before the final transition.
        end(tx, unit, attempt, "completed", token=token)
    return True
