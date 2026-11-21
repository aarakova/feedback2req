"""Read-only mechanical audit of supplied F1/F2 JSON, never a trusted exporter.

Local diagnostic format only. No HTTP, ORM, model inference or solver calls.
The caller must obtain authorized exact snapshots and original mappings separately.
"""

from dataclasses import asdict, dataclass, field

from ai.formal_expectations.diagnostics import ErrorCode, FormalError
from ai.formal_expectations.limits import Budget, Limits
from ai.formal_expectations.validation import decode

from .model import BridgeError, fingerprint
from .validation import array, obj, prepare, require, text

OUTSTANDING_GATES = (
    "authorized_atomic_snapshot",
    "accepted_canonical_snapshot_and_mapping_provenance",
    "semantic_formalization_and_comparability_review",
    "context_partition_and_omega_completeness_review",
    "current_access_and_source_availability_revalidation",
)


@dataclass(frozen=True)
class CompatibilityAudit:
    status: str
    packet_sha256: str | None
    saved_sha256: str | None
    checks: int
    diagnostics: list[dict] = field(default_factory=list)
    outstanding_gates: tuple[str, ...] = OUTSTANDING_GATES
    verification_created: bool = False
    classification: None = None
    interpretation: str = "mechanical_comparison_only_not_authorization_or_semantic_truth"

    def to_dict(self):
        return asdict(self)


def _ref(value, kind):
    obj(value, {"kind", "id", "state_id"})
    require(value["kind"] == kind, "reference_kind")
    return kind, text(value["id"]), text(value["state_id"])


def _identity(value, kind):
    require(type(value) is dict, "saved_object")
    return kind, text(value["id"]), text(value["state_id"])


def audit_saved_inputs(data, saved, *, limits=None) -> CompatibilityAudit:
    """Compare an existing bridge input with explicitly supplied saved DTOs.

    saved={findings: F1 Finding[], groups: F2 GroupDetail[], sources: Source[],
           group_bindings: [{local_id,ref,conflicts:[{local_id,id}]}]}.
    Bindings are external assertions, not inferred from text, order or membership.
    A matched audit never acts as Verification and never authorizes check_pair.
    """
    prepared = prepare(data, limits=limits)
    digest = fingerprint(prepared.packet) if prepared.packet is not None else None
    if prepared.status != "prepared":
        technical = (prepared.diagnostic or {}).get("code") in (
            "timeout",
            "resource_limit",
            "internal_failure",
            "solver_failure",
        )
        return CompatibilityAudit(
            "technical_error" if technical else "preparation_required",
            digest,
            None,
            0,
            [prepared.diagnostic or {}],
        )
    issues, checks, saved_digest = [], 0, None

    def note(category, rule):
        issues.append({"category": category, "rule": rule})

    def equal(left, right, rule):
        nonlocal checks
        checks += 1
        # Canonical JSON comparison distinguishes bools from integers.
        if fingerprint(left) != fingerprint(right):
            note("mismatch", rule)

    def index(items, kind):
        result = {}
        for item in array(items, empty=True):
            key = _identity(item, kind)
            require(key not in result, "duplicate_saved_state")
            result[key] = item
        return result

    try:
        budget = Budget(limits or Limits())
        saved = decode(saved, budget)
        obj(saved, {"findings", "groups", "sources", "group_bindings"})
        saved_digest = fingerprint(saved)
        findings = index(saved["findings"], "finding")
        groups = index(saved["groups"], "finding_group")
        sources = index(saved["sources"], "feedback_source")
        packet = prepared.packet["input"]
        request, response = packet["grouping_request"], packet["grouping_response"]
        canonical_findings = {f["key"]: f for f in request["input"]["findings"]}
        fragments = {f["key"]: f for f in request["input"]["fragments"]}
        for finding in canonical_findings.values():
            row = findings.get(_ref(finding["ref"], "finding"))
            if row is None:
                note("missing", "exact_finding_unavailable")
                continue
            for name in ("text", "types", "mode", "authorship"):
                equal(finding[name], row[name], "finding_" + name)
            available = {}
            for fragment in array(row["evidence"], empty=True):
                ref = _identity(fragment, "fragment")
                require(ref not in available, "duplicate_saved_evidence")
                available[ref] = fragment
            selected = set()
            for link in finding["evidence"]:
                if link["kind"] != "available":
                    note("missing", "deleted_source_cannot_confirm_basis")
                    continue
                fragment = fragments[link["fragment_key"]]
                ref = _ref(fragment["ref"], "fragment")
                selected.add(ref)
                actual = available.get(ref)
                if actual is None:
                    note("mismatch", "fragment_not_owned_by_finding")
                    continue
                for name in ("source_ref", "text_ref", "quote", "locator", "reliability"):
                    equal(fragment[name], actual[name], "fragment_" + name)
                # Integration F1 currently supports text sources, not ASR/transcripts.
                source_key = _ref(fragment["text_ref"], "feedback_source")
                source = sources.get(source_key)
                if source is None:
                    note("missing", "exact_source_text_unavailable")
                    continue
                require(type(source["text"]) is str, "source_text")
                location = fragment["locator"]
                start, end = location["start"], location["end"]
                require(
                    type(start) is int
                    and type(end) is int
                    and 0 <= start < end <= len(source["text"]),
                    "source_locator",
                )
                equal(source["text"][start:end], fragment["quote"], "source_quote")
            equal(sorted(selected), sorted(available), "full_finding_evidence_set")
            if row["freshness"] != "current":
                note("missing", "source_revalidation_required")
        bindings = {}
        bound_states = set()
        for item in array(saved["group_bindings"], empty=True):
            obj(item, {"local_id", "ref", "conflicts"})
            key, ref = text(item["local_id"]), _ref(item["ref"], "finding_group")
            require(key not in bindings and ref not in bound_states, "duplicate_group_binding")
            bound_states.add(ref)
            bindings[key] = item
        candidates = {g["local_id"]: g for g in response["result"]["groups"]}
        require(bindings.keys() <= candidates.keys(), "binding_outside_response")
        for key, candidate in candidates.items():
            if key not in bindings:
                note("missing", "local_to_persistent_group_mapping_unavailable")
                continue
            binding = bindings[key]
            row = groups.get(_ref(binding["ref"], "finding_group"))
            if row is None:
                note("missing", "exact_group_state_unavailable")
                continue
            for name in ("title", "summary"):
                equal(candidate[name], row[name], "group_" + name)
            members = {}
            for member in array(row["members"]):
                ref = _ref(member["ref"], "finding")
                require(ref not in members, "duplicate_saved_member")
                equal(ref, _identity(member["finding"], "finding"), "embedded_finding_state")
                members[ref] = member
                actual = findings.get(ref)
                if actual is None:
                    note("missing", "member_finding_snapshot_unavailable")
                else:
                    equal(member["finding"], actual, "embedded_finding_snapshot")
            for name, refs in (
                ("finding_keys", list(m["ref"] for m in row["members"])),
                ("considered_keys", row["considered_findings"]),
            ):
                expected = sorted(
                    _ref(canonical_findings[k]["ref"], "finding") for k in candidate[name]
                )
                actual = [_ref(v, "finding") for v in array(refs)]
                require(len(set(actual)) == len(actual), "duplicate_group_scope")
                equal(expected, sorted(actual), "group_" + name)
            conflict_bindings = {}
            for item in array(binding["conflicts"], empty=True):
                obj(item, {"local_id", "id"})
                local, identity = text(item["local_id"]), text(item["id"])
                require(local not in conflict_bindings, "duplicate_conflict_binding")
                conflict_bindings[local] = identity
            require(
                len(set(conflict_bindings.values())) == len(conflict_bindings),
                "duplicate_conflict_target",
            )
            actual_conflicts = {}
            for conflict in array(row["conflicts"], empty=True):
                identity = text(conflict["id"])
                require(identity not in actual_conflicts, "duplicate_saved_conflict")
                actual_conflicts[identity] = conflict
            equal(
                sorted(conflict_bindings),
                sorted(c["local_id"] for c in candidate["conflicts"]),
                "conflict_mapping_set",
            )
            equal(
                sorted(conflict_bindings.values()), sorted(actual_conflicts), "saved_conflict_set"
            )
            for conflict in candidate["conflicts"]:
                actual = actual_conflicts.get(conflict_bindings.get(conflict["local_id"]))
                if actual is None:
                    note("missing", "exact_conflict_mapping_unavailable")
                    continue
                equal(conflict["description"], actual["description"], "conflict_description")
                positions = array(actual["positions"])
                equal(len(conflict["positions"]), len(positions), "position_count")
                identities = [text(p["id"]) for p in positions]
                require(len(set(identities)) == len(identities), "duplicate_position_identity")
                for expected, position in zip(conflict["positions"], positions, strict=False):
                    equal(expected["description"], position["description"], "position_description")
                    refs = [_ref(v, "finding") for v in array(position["findings"])]
                    require(len(set(refs)) == len(refs), "duplicate_position_member")
                    require(set(refs) <= members.keys(), "position_outside_group")
                    equal(
                        sorted(
                            _ref(canonical_findings[k]["ref"], "finding")
                            for k in expected["finding_keys"]
                        ),
                        sorted(refs),
                        "full_position_members",
                    )
            if row["freshness"] != "current":
                note("missing", "group_revalidation_required")
            if candidate["context_keys"] or row["context"]:
                note("missing", "document_context_requires_separate_snapshot")
        if request["input"].get("previous_groups"):
            note("missing", "previous_group_context_requires_separate_audit")
        if request["input"]["documents"]:
            note("missing", "document_excerpt_requires_separate_audit")
        budget.remaining_ms()
    except BridgeError as error:
        note("invalid_input", error.rule)
    except FormalError as error:
        category = (
            "technical_error"
            if error.code
            in (ErrorCode.TIMEOUT, ErrorCode.RESOURCE_LIMIT, ErrorCode.INTERNAL_FAILURE)
            else "invalid_input"
        )
        note(category, error.rule)
    except (KeyError, TypeError, ValueError):
        note("invalid_input", "saved_dto_shape")
    except Exception:
        note("technical_error", "saved_audit_failure")
    categories = {i["category"] for i in issues}
    status = next(
        (s for s in ("technical_error", "invalid_input", "mismatch", "missing") if s in categories),
        "matched",
    )
    return CompatibilityAudit(status, digest, saved_digest, checks, issues)
