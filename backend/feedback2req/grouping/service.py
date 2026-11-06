"""Durable internal group_findings boundary. No provider invocation or public command."""

import hashlib
import secrets
from copy import deepcopy
from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID, uuid4

from sqlalchemy import select

from feedback2req.errors import AppError
from feedback2req.grouping import validation
from feedback2req.persistence.grouping import (
    ConflictPosition,
    FindingGroup,
    GroupConflict,
    GroupContext,
    GroupingDocument,
    GroupingInput,
    GroupingPreviousGroup,
    GroupMember,
    GroupScope,
    GroupState,
    PositionMember,
)
from feedback2req.persistence.models import DocumentState, ProductDocument
from feedback2req.persistence.processing import Attempt, Finding, Run, Unit
from feedback2req.processing.service import DEADLINE, LEASE, end, fingerprint, locked, now, owned
from feedback2req.processing.validation import InvalidResponse, decode, schema
from feedback2req.processing.views import finding_view
from feedback2req.projects.service import require_project


@dataclass(frozen=True)
class Provenance:
    provider: str
    model: str
    synthetic: bool

    def __post_init__(self):
        for value, limit in ((self.provider, 64), (self.model, 128)):
            if not isinstance(value, str) or not 1 <= len(value) <= limit:
                raise ValueError("Invalid provider metadata")
            validation.strings(value)
        if type(self.synthetic) is not bool:
            raise ValueError("Explicit synthetic marker required")


def state_ref(kind, identity, state=None):
    return {"kind": kind, "id": str(identity), "state_id": str(state or identity)}


def rows(tx, model, unit):
    return tx.scalars(
        select(model)
        .where(
            model.project_id == unit.project_id,
            model.unit_id == unit.id,
        )
        .order_by(model.key)
    ).all()


def normalized(refs, kind, *, documents=False):
    result = []
    try:
        for ref in refs:
            if set(ref) - {"kind", "id", "state_id", *(["locator"] if documents else [])}:
                raise ValueError()
            if ref.get("kind", kind) != kind:
                raise ValueError()
            item = state_ref(kind, UUID(str(ref["id"])), UUID(str(ref["state_id"])))
            if documents and "locator" in ref:
                loc = ref["locator"]
                if set(loc) != {"start", "end"} or any(type(v) is not int for v in loc.values()):
                    raise ValueError()
                item["locator"] = {"start": loc["start"], "end": loc["end"]}
            result.append(item)
        identities = [(v["id"], str(v.get("locator"))) for v in result]
        if len(set(identities)) != len(identities):
            raise ValueError()
        return sorted(result, key=lambda v: (v["id"], str(v.get("locator"))))
    except (KeyError, TypeError, ValueError) as exc:
        raise AppError(422, "invalid_input", "Exact unique input references required") from exc


def exact_finding(tx, project_id, identity, state_id):
    row = tx.scalar(select(Finding).where(Finding.project_id == project_id, Finding.id == identity))
    if row is None or row.id != state_id:
        raise AppError(404, "not_found", "Project or object not found")
    view = finding_view(tx, row)
    if not view["evidence"] or view["freshness"] != "current":
        raise AppError(409, "input_changed", "Finding inputs changed")
    return row, view


def exact_document(tx, project_id, identity, state_id):
    row = tx.scalar(
        select(DocumentState).where(
            DocumentState.project_id == project_id,
            DocumentState.document_id == identity,
            DocumentState.id == state_id,
        )
    )
    header = tx.scalar(
        select(ProductDocument).where(
            ProductDocument.project_id == project_id,
            ProductDocument.id == identity,
        )
    )
    if row is None or header is None:
        raise AppError(404, "not_found", "Project or object not found")
    if header.current_state_id != state_id:
        raise AppError(409, "input_changed", "Document inputs changed")
    return row


def relevant_annotations(attempt, identity, input_ids=()):
    annotations = (attempt.annotations if attempt else None) or {
        "questions": [],
        "uncertainties": [],
    }
    return {
        kind: [
            item
            for item in annotations[kind]
            if any(
                link.get("id") == str(identity)
                or (link["origin"] == "input" and link.get("id") in input_ids)
                for link in item["related"]
            )
        ]
        for kind in ("questions", "uncertainties")
    }


def questions(items, prefix):
    return [
        {"key": f"q-{prefix}-{q['local_id']}", **{k: q[k] for k in ("text", "reason", "blocking")}}
        for q in items
    ]


def build_request(tx, unit, attempt):
    findings, fragments = [], {}
    inputs = rows(tx, GroupingInput, unit)
    keys = {r.finding_id: r.key for r in inputs}
    for item in inputs:
        finding, view = exact_finding(tx, unit.project_id, item.finding_id, item.finding_state_id)
        origin = tx.get(Attempt, finding.attempt_id)
        ann = relevant_annotations(origin, finding.id)
        # F1 input-related annotations affect its entire atomic extraction unit.
        base = origin.annotations or {"questions": [], "uncertainties": []}
        for kind in ann:
            for note in base[kind]:
                if (
                    any(link["origin"] == "input" for link in note["related"])
                    and note not in ann[kind]
                ):
                    ann[kind].append(note)
        evidence = []
        for fragment in view["evidence"]:
            key = "e-" + str(fragment["id"])
            fragments[key] = {
                "key": key,
                "ref": state_ref("fragment", fragment["id"]),
                **{
                    k: {j: str(v) for j, v in fragment[k].items()}
                    for k in ("source_ref", "text_ref")
                },
                **{k: fragment[k] for k in ("quote", "locator", "reliability")},
            }
            evidence.append({"kind": "available", "fragment_key": key})
        findings.append(
            {
                "key": item.key,
                "ref": state_ref("finding", finding.id),
                "text": finding.text,
                "types": finding.types,
                "mode": finding.mode,
                "authorship": "ai",
                "evidence": evidence,
                "uncertainty_notes": [q["reason"] for q in ann["uncertainties"]],
                "open_questions": questions(ann["questions"], finding.id),
            }
        )
    documents = []
    for item in rows(tx, GroupingDocument, unit):
        doc = exact_document(tx, unit.project_id, item.document_id, item.document_state_id)
        if not 0 <= item.start < item.end <= len(doc.text):
            raise AppError(422, "invalid_input", "Invalid document range")
        documents.append(
            {
                "key": item.key,
                "ref": state_ref("product_document", doc.document_id, doc.id),
                "text": doc.text[item.start : item.end],
                "locator": {"start": item.start, "end": item.end},
            }
        )
    previous = []
    for item in rows(tx, GroupingPreviousGroup, unit):
        from feedback2req.grouping.views import group_detail

        detail = group_detail(tx, unit.project_id, item.group_id, item.group_state_id)
        header = tx.get(FindingGroup, item.group_id)
        if header.current_state_id != item.group_state_id or detail["freshness"] != "current":
            raise AppError(409, "input_changed", "Previous group changed")
        member_ids = {UUID(v["ref"]["id"]) for v in detail["members"]}
        if not member_ids <= keys.keys():
            raise AppError(
                422, "invalid_input", "Previous group requires explicitly supplied findings"
            )
        previous.append(
            {
                "key": item.key,
                "ref": state_ref("finding_group", item.group_id, item.group_state_id),
                "title": detail["title"],
                "summary": detail["summary"],
                "finding_keys": sorted(keys[v] for v in member_ids),
                "conflicts": [
                    {
                        "key": "c-" + str(c["id"]),
                        "description": c["description"],
                        "positions": [
                            {
                                "description": p["description"],
                                "finding_keys": [keys[UUID(f["id"])] for f in p["findings"]],
                            }
                            for p in c["positions"]
                        ],
                    }
                    for c in detail["conflicts"]
                ],
                "open_questions": questions(
                    relevant_annotations(
                        tx.get(Attempt, detail["attempt_id"]) if detail["attempt_id"] else None,
                        item.group_id,
                        {ref["id"] for ref in detail["considered_findings"]},
                    )["questions"],
                    item.group_id,
                ),
            }
        )
    request = {
        "contract_version": "1.0",
        "operation": "group_findings",
        "project_id": str(unit.project_id),
        "request_id": str(attempt.request_id if attempt else unit.id),
        "input": {
            "findings": findings,
            "fragments": list(fragments.values()),
            "documents": documents,
        },
    }
    if previous:
        request["input"]["previous_groups"] = previous
    schema("group_findings.request").validate(request)
    return request


def prepare_grouping(
    sessions,
    identity,
    session_token,
    project_id,
    command_key,
    finding_refs,
    *,
    document_refs=(),
    previous_group_refs=(),
    provenance,
):
    return _create_grouping(
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


def enqueue_grouping(
    sessions,
    identity,
    session_token,
    project_id,
    command_key,
    finding_refs,
    *,
    document_refs=(),
    previous_group_refs=(),
):
    """Authenticated internal enqueue; no Attempt, capability or token in the queue."""
    if (
        not 1 <= len(finding_refs) <= 100
        or len(document_refs) > 16
        or len(previous_group_refs) > 16
    ):
        raise AppError(422, "invalid_input", "Grouping selection exceeds internal limits")
    return _create_grouping(
        sessions,
        identity,
        session_token,
        project_id,
        command_key,
        finding_refs,
        document_refs=document_refs,
        previous_group_refs=previous_group_refs,
        queued=True,
    )


def _create_grouping(
    sessions,
    identity,
    session_token,
    project_id,
    command_key,
    finding_refs,
    *,
    document_refs=(),
    previous_group_refs=(),
    provenance=None,
    queued=False,
):
    """Authenticate a real current session. A replay never returns execution capability."""
    project_id, command_key = UUID(str(project_id)), UUID(str(command_key))
    findings = normalized(finding_refs, "finding")
    docs = normalized(document_refs, "product_document", documents=True)
    previous = normalized(previous_group_refs, "finding_group")
    if not findings or (not queued and not isinstance(provenance, Provenance)):
        raise AppError(422, "invalid_input", "Findings and explicit provenance required")
    digest = fingerprint(
        {
            "operation": "group_findings",
            "findings": findings,
            "documents": docs,
            "previous_groups": previous,
        }
    )
    with sessions.begin() as tx:
        actor = identity.authenticate(tx, session_token)
        require_project(tx, project_id, actor.user.id, write=True)
        run = tx.scalar(
            select(Run).where(
                Run.project_id == project_id,
                Run.initiated_by == actor.user.id,
                Run.command_kind == "start",
                Run.idempotency_key == command_key,
            )
        )
        if run:
            if run.fingerprint != digest:
                raise AppError(
                    409, "idempotency_conflict", "Key already identifies another command"
                )
            unit = tx.scalar(select(Unit).where(Unit.run_id == run.id))
            attempt = tx.scalar(select(Attempt).where(Attempt.unit_id == unit.id))
            return {
                "run_id": run.id,
                "unit_id": unit.id,
                "attempt_id": attempt.id if attempt else None,
                "owner_token": None,
                "request": None,
                "replayed": True,
            }
        run = Run(
            id=uuid4(),
            project_id=project_id,
            initiated_by=actor.user.id,
            operation="group_findings",
            command_kind="start",
            idempotency_key=command_key,
            fingerprint=digest,
        )
        tx.add(run)
        tx.flush()
        unit = Unit(
            id=uuid4(),
            project_id=project_id,
            run_id=run.id,
            input_kind="finding_set",
            state="queued" if queued else "running",
        )
        tx.add(unit)
        tx.flush()
        instant, token = now(tx), uuid4()
        attempt = (
            None
            if queued
            else Attempt(
                id=uuid4(),
                project_id=project_id,
                unit_id=unit.id,
                request_id=uuid4(),
                state="running",
                owner_token=token,
                grouping_owner_hash=hashlib.sha256(token.bytes).hexdigest(),
                started_at=instant,
                deadline_at=instant + timedelta(seconds=DEADLINE),
                lease_expires_at=instant + timedelta(seconds=LEASE),
                provider=provenance.provider,
                model=provenance.model,
                synthetic=provenance.synthetic,
                ai_performed=False if provenance.synthetic else None,
            )
        )
        if attempt is not None:
            tx.add(attempt)
        for index, ref in enumerate(findings):
            # Reject unknown/foreign/mismatched refs before SQL constraints execute.
            exact_finding(tx, project_id, UUID(ref["id"]), UUID(ref["state_id"]))
            tx.add(
                GroupingInput(
                    project_id=project_id,
                    unit_id=unit.id,
                    key=f"f{index + 1}",
                    finding_id=UUID(ref["id"]),
                    finding_state_id=UUID(ref["state_id"]),
                )
            )
        document_ranges = set()
        for index, ref in enumerate(docs):
            doc = exact_document(tx, project_id, UUID(ref["id"]), UUID(ref["state_id"]))
            loc = ref.get("locator", {"start": 0, "end": len(doc.text)})
            if not 0 <= loc["start"] < loc["end"] <= len(doc.text):
                raise AppError(422, "invalid_input", "Invalid document range")
            selected_range = (doc.id, loc["start"], loc["end"])
            if selected_range in document_ranges:
                raise AppError(422, "invalid_input", "Duplicate document range")
            document_ranges.add(selected_range)
            tx.add(
                GroupingDocument(
                    project_id=project_id,
                    unit_id=unit.id,
                    key=f"d{index + 1}",
                    document_id=doc.document_id,
                    document_state_id=doc.id,
                    **loc,
                )
            )
        for index, ref in enumerate(previous):
            from feedback2req.grouping.views import group_detail

            group_detail(tx, project_id, UUID(ref["id"]), UUID(ref["state_id"]))
            tx.add(
                GroupingPreviousGroup(
                    project_id=project_id,
                    unit_id=unit.id,
                    key=f"g{index + 1}",
                    group_id=UUID(ref["id"]),
                    group_state_id=UUID(ref["state_id"]),
                )
            )
        tx.flush()
        request = build_request(tx, unit, attempt)
        if queued:
            from ai.group_findings.validation import GroupingError, validate_request

            try:
                validate_request(request)
            except GroupingError:
                raise AppError(
                    422, "invalid_input", "Grouping context exceeds component limits"
                ) from None
            return {
                "run_id": run.id,
                "unit_id": unit.id,
                "attempt_id": None,
                "owner_token": None,
                "request": None,
                "replayed": False,
            }
        if not owned(tx, attempt, token):
            raise AppError(409, "attempt_not_owned", "Preparation exceeded attempt lifetime")
        return {
            "run_id": run.id,
            "unit_id": unit.id,
            "attempt_id": attempt.id,
            "owner_token": token,
            "request": request,
            "replayed": False,
        }


def current(tx, unit):
    run = tx.get(Run, unit.run_id)
    if run.operation != "group_findings" or unit.input_kind != "finding_set":
        raise AppError(409, "invalid_input", "Not a grouping attempt")
    require_project(tx, unit.project_id, run.initiated_by)


def permitted(attempt, token):
    try:
        digest = hashlib.sha256(UUID(str(token)).bytes).hexdigest()
    except (TypeError, ValueError):
        return False
    return bool(
        attempt
        and attempt.grouping_owner_hash
        and secrets.compare_digest(
            attempt.grouping_owner_hash,
            digest,
        )
    )


def result_view(tx, unit, attempt):
    return {
        "attempt_id": attempt.id,
        "state": attempt.state,
        "reason_code": attempt.reason_code,
        "group_ids": list(
            tx.scalars(
                select(GroupState.group_id)
                .where(
                    GroupState.project_id == unit.project_id,
                    GroupState.attempt_id == attempt.id,
                )
                .order_by(GroupState.group_id)
            )
        ),
        "ungrouped_findings": attempt.ungrouped_findings,
    }


def renew_grouping(sessions, unit_id, owner_token):
    with sessions.begin() as tx:
        pair = locked(tx, unit_id)
        if (
            pair is None
            or not permitted(pair[1], owner_token)
            or not owned(tx, pair[1], owner_token)
        ):
            return False
        unit, attempt = pair
        try:
            current(tx, unit)
        except AppError:
            end(tx, unit, attempt, "cancelled", "access_revoked", owner_token)
            return False
        attempt.lease_expires_at = min(now(tx) + timedelta(seconds=LEASE), attempt.deadline_at)
        return True


def publish(tx, unit, attempt, response):
    inputs = {r.key: r for r in rows(tx, GroupingInput, unit)}
    docs = {r.key: r for r in rows(tx, GroupingDocument, unit)}
    annotation_inputs = {
        key: state_ref("finding", item.finding_id, item.finding_state_id)
        for key, item in inputs.items()
    }
    annotation_inputs.update(
        {
            item.key: state_ref("finding_group", item.group_id, item.group_state_id)
            for item in rows(tx, GroupingPreviousGroup, unit)
        }
    )
    mapping = {}
    for candidate in response["result"]["groups"]:
        group_id, state_id = uuid4(), uuid4()
        mapping[candidate["local_id"]] = state_ref("finding_group", group_id, state_id)
        tx.add(FindingGroup(id=group_id, project_id=unit.project_id, current_state_id=state_id))
        tx.flush()
        tx.add(
            GroupState(
                id=state_id,
                project_id=unit.project_id,
                group_id=group_id,
                title=candidate["title"],
                summary=candidate["summary"],
                authorship="ai",
                attempt_id=attempt.id,
                local_id=candidate["local_id"],
            )
        )
        tx.flush()
        for model, keys in (
            (GroupScope, candidate["considered_keys"]),
            (GroupMember, candidate["finding_keys"]),
        ):
            for key in keys:
                item = inputs[key]
                tx.add(
                    model(
                        project_id=unit.project_id,
                        group_state_id=state_id,
                        finding_id=item.finding_id,
                        finding_state_id=item.finding_state_id,
                    )
                )
            # No ORM relationships: explicitly flush referenced scope before members.
            tx.flush()
        for key in candidate["context_keys"]:
            item = docs[key]
            tx.add(
                GroupContext(
                    project_id=unit.project_id,
                    group_state_id=state_id,
                    document_id=item.document_id,
                    document_state_id=item.document_state_id,
                    start=item.start,
                    end=item.end,
                )
            )
        tx.flush()
        for candidate_conflict in candidate["conflicts"]:
            conflict = GroupConflict(
                id=uuid4(),
                project_id=unit.project_id,
                group_state_id=state_id,
                attempt_id=attempt.id,
                local_id=candidate_conflict["local_id"],
                description=candidate_conflict["description"],
            )
            tx.add(conflict)
            tx.flush()
            for ordinal, p in enumerate(candidate_conflict["positions"]):
                position = ConflictPosition(
                    id=uuid4(),
                    project_id=unit.project_id,
                    group_state_id=state_id,
                    conflict_id=conflict.id,
                    ordinal=ordinal,
                    description=p["description"],
                )
                tx.add(position)
                tx.flush()
                for key in p["finding_keys"]:
                    item = inputs[key]
                    tx.add(
                        PositionMember(
                            project_id=unit.project_id,
                            group_state_id=state_id,
                            position_id=position.id,
                            finding_id=item.finding_id,
                            finding_state_id=item.finding_state_id,
                        )
                    )
    attempt.coverage = deepcopy(response["coverage"])
    attempt.ungrouped_findings = [
        state_ref("finding", inputs[k].finding_id)
        for k in response["result"]["ungrouped_finding_keys"]
    ]
    annotations = deepcopy({k: response[k] for k in ("questions", "uncertainties")})
    for notes in annotations.values():
        for note in notes:
            for link in note["related"]:
                ref = (
                    annotation_inputs[link["key"]]
                    if (link["origin"] == "input")
                    else mapping[link["key"]]
                )
                link.update(ref)
    attempt.annotations = annotations


def accept_grouping(sessions, unit_id, owner_token, response):
    """An unknown commit outcome escapes; retry this receipt or read Run, never re-run AI."""
    with sessions.begin() as tx:
        pair = locked(tx, unit_id)
        if pair is None or not permitted(pair[1], owner_token):
            raise AppError(409, "attempt_not_owned", "Attempt capability is invalid")
        unit, attempt = pair
        # Recheck access even on replay. An old capability grants no project membership.
        if owned(tx, attempt, owner_token):
            # The response was received even if changed inputs/access cancel its publication.
            attempt.ai_performed = not attempt.synthetic
        try:
            current(tx, unit)
        except AppError:
            if owned(tx, attempt, owner_token):
                end(tx, unit, attempt, "cancelled", "access_revoked", owner_token)
                tx.refresh(attempt)
                return result_view(tx, unit, attempt)
            raise
        if attempt.state == "completed":
            return result_view(tx, unit, attempt)
        if not owned(tx, attempt, owner_token):
            raise AppError(409, "attempt_not_owned", "Attempt expired or is terminal")
        try:
            request = build_request(tx, unit, attempt)
        except AppError:
            end(tx, unit, attempt, "cancelled", "input_changed", owner_token)
            tx.refresh(attempt)
            return result_view(tx, unit, attempt)
        try:
            if isinstance(response, (str, bytes)):
                response = decode(response)
            validation.accept(request, response)
        except InvalidResponse:
            end(tx, unit, attempt, "failed", "invalid_response", owner_token)
        else:
            publish(tx, unit, attempt, response)
            tx.flush()
            end(tx, unit, attempt, "completed", token=owner_token)
        tx.refresh(attempt)
        return result_view(tx, unit, attempt)


def fail_grouping(sessions, unit_id, owner_token, reason_code):
    if reason_code not in {
        "provider_not_configured",
        "provider_error",
        "execution_error",
        "invalid_response",
        "deadline_exceeded",
    }:
        raise ValueError("Stable failure reason required")
    with sessions.begin() as tx:
        pair = locked(tx, unit_id)
        if pair is None or not permitted(pair[1], owner_token):
            raise AppError(409, "attempt_not_owned", "Attempt capability is invalid")
        unit, attempt = pair
        try:
            current(tx, unit)
        except AppError:
            if owned(tx, attempt, owner_token):
                end(tx, unit, attempt, "cancelled", "access_revoked", owner_token)
                tx.refresh(attempt)
                return result_view(tx, unit, attempt)
            raise
        if attempt.state == "completed":
            return result_view(tx, unit, attempt)
        if not owned(tx, attempt, owner_token):
            raise AppError(409, "attempt_not_owned", "Attempt expired or is terminal")
        try:
            build_request(tx, unit, attempt)
        except AppError:
            end(tx, unit, attempt, "cancelled", "input_changed", owner_token)
            tx.refresh(attempt)
            return result_view(tx, unit, attempt)
        if reason_code == "provider_not_configured":
            attempt.ai_performed = False
        elif reason_code == "invalid_response":
            attempt.ai_performed = not attempt.synthetic
        end(tx, unit, attempt, "failed", reason_code, owner_token)
        tx.refresh(attempt)
        return result_view(tx, unit, attempt)
