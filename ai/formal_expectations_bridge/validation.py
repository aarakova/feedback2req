"""Explicit selection/decomposition and provenance, without text extraction."""

from copy import deepcopy
from itertools import combinations

from ai.formal_expectations.diagnostics import ErrorCode, FormalError
from ai.formal_expectations.limits import Budget, Limits
from ai.formal_expectations.model import SubjectModel
from ai.formal_expectations.validation import _domain, _expectation, decode, parse_request
from ai.group_findings.validation import GroupingError, validate_request, validate_response

from .model import BridgeError, Preparation, fingerprint


def require(condition, rule, code="invalid_preparation"):
    if not condition:
        raise BridgeError(code, rule)


def obj(value, keys):
    require(type(value) is dict and set(value) == set(keys), "closed_object")
    return value


def text(value):
    require(type(value) is str and bool(value.strip()) and len(value) <= 1024, "bounded_text")
    return value


def array(value, *, empty=False):
    require(type(value) is list and len(value) <= 256 and (empty or value), "bounded_array")
    return value


def strings(value, *, empty=False):
    items = [text(v) for v in array(value, empty=empty)]
    require(len(set(items)) == len(items), "duplicate_member")
    return items


def origin(value):
    obj(value, {"kind", "actor", "method"})
    require(value["kind"] in ("human", "ai"), "origin_kind")
    text(value["actor"])
    text(value["method"])


def _selection(data, request, response):
    obj(data, {"left_finding_keys", "right_finding_keys", "conflict", "rationale"})
    text(data["rationale"])
    left, right = (set(strings(data[k])) for k in ("left_finding_keys", "right_finding_keys"))
    findings = {f["key"]: f for f in request["input"]["findings"]}
    require(left | right <= findings.keys(), "selection_outside_input")
    # Structural acceptance of a group does not imply every member was processed.
    coverage = {c["input_key"]: c for c in response["coverage"]}
    require(all(coverage[k]["reviewed"] for k in left | right), "unreviewed_selection")
    require(
        all(coverage[k]["disposition"] == "completed" for k in left | right),
        "incomplete_finding_context",
        "context_incomplete",
    )
    if data["conflict"] is not None:
        ref = obj(
            data["conflict"],
            {"group_local_id", "conflict_local_id", "left_position", "right_position"},
        )
        text(ref["group_local_id"])
        text(ref["conflict_local_id"])
        group = next(
            (g for g in response["result"]["groups"] if g["local_id"] == ref["group_local_id"]),
            None,
        )
        require(group is not None, "unknown_group")
        conflict = next(
            (c for c in group["conflicts"] if c["local_id"] == ref["conflict_local_id"]), None
        )
        require(conflict is not None, "unknown_conflict")
        indexes = [ref["left_position"], ref["right_position"]]
        require(
            all(type(i) is int and 0 <= i < len(conflict["positions"]) for i in indexes),
            "position_index",
        )
        require(indexes[0] != indexes[1], "same_position")
        require(
            left == set(conflict["positions"][indexes[0]]["finding_keys"])
            and right == set(conflict["positions"][indexes[1]]["finding_keys"]),
            "position_members_must_be_explicit_and_complete",
        )
    return left, right, findings


def _contexts(model):
    obj(model, {"id", "version", "formal_model", "contexts", "relations", "method", "rationale"})
    for key in ("id", "version", "method", "rationale"):
        text(model[key])
    formal = obj(model["formal_model"], {"object_id", "parameter_id", "situations", "domain"})
    situations = strings(formal["situations"])
    subject = SubjectModel(
        text(formal["object_id"]),
        text(formal["parameter_id"]),
        tuple(situations),
        _domain(formal["domain"]),
    )
    contexts = {}
    for context in array(model["contexts"]):
        obj(context, {"id", "situations"})
        key = text(context["id"])
        require(key not in contexts, "duplicate_context")
        members = set(strings(context["situations"]))
        require(members <= set(situations), "context_outside_model")
        contexts[key] = members
    relations = set()
    for item in array(model["relations"], empty=True):
        obj(item, {"left", "right", "relation"})
        left, right = text(item["left"]), text(item["right"])
        require(
            left in contexts and right in contexts and left != right, "context_relation_reference"
        )
        pair = frozenset((left, right))
        require(pair not in relations, "duplicate_context_relation")
        relations.add(pair)
        require(
            item["relation"] in ("overlap", "disjoint"),
            "context_relation_unresolved",
            "unsupported_context",
        )
        overlaps = bool(contexts[left] & contexts[right])
        require(overlaps == (item["relation"] == "overlap"), "context_partition_contradiction")
    require(
        relations == {frozenset(p) for p in combinations(contexts, 2)},
        "context_relations_incomplete",
        "unsupported_context",
    )
    return subject, contexts


def _atoms(proposal, findings, selected, subject, contexts, fragments):
    text(proposal["version"])
    origin(proposal["origin"])
    text(proposal["decomposition_rationale"])
    atoms, expectations, linked = {}, {}, set()
    for atom in array(proposal["atoms"]):
        obj(
            atom,
            {
                "id",
                "object_id",
                "parameter_id",
                "context_id",
                "values",
                "missing_fields",
                "sources",
            },
        )
        key = text(atom["id"])
        require(key not in atoms, "duplicate_atom")
        atoms[key] = atom
        missing = set(strings(atom["missing_fields"], empty=True))
        expected_missing = ({"conditions"} if atom["context_id"] is None else set()) | (
            {"values"} if atom["values"] is None else set()
        )
        require(missing == expected_missing, "missing_information_must_be_explicit")
        context = atom["context_id"]
        if context is not None:
            require(type(context) is str and context in contexts, "unknown_context")
        source_keys = set()
        for source in array(atom["sources"]):
            obj(source, {"finding_key", "finding_ref", "evidence_keys"})
            finding_key = text(source["finding_key"])
            require(
                finding_key in selected and finding_key not in source_keys, "atom_finding_scope"
            )
            finding = findings[finding_key]
            require(source["finding_ref"] == finding["ref"], "finding_state_mismatch")
            evidence = set(strings(source["evidence_keys"]))
            available = {e["fragment_key"] for e in finding["evidence"] if e["kind"] == "available"}
            require(
                evidence <= available and evidence <= fragments.keys(),
                "unavailable_or_foreign_evidence",
                "basis_unavailable",
            )
            # Uncertain speech cannot silently become a trusted numeric premise.
            require(
                all(fragments[k]["reliability"] == "usable" for k in evidence),
                "unreliable_evidence",
                "basis_unavailable",
            )
            source_keys.add(finding_key)
        linked |= source_keys
        expectation = {
            "object_id": atom["object_id"],
            "parameter_id": atom["parameter_id"],
            "conditions": None if context is None else sorted(contexts[context]),
            "values": atom["values"],
            "basis": "bridge-atom:" + fingerprint(atom),
        }
        # Reuse the existing grammar/domain validation; no new Z3 translator.
        _expectation(expectation, subject)
        expectations[key] = expectation
    omitted = set()
    for omission in array(proposal["omissions"], empty=True):
        obj(omission, {"finding_key", "reason"})
        key = text(omission["finding_key"])
        text(omission["reason"])
        require(key in selected and key not in linked | omitted, "invalid_omission")
        omitted.add(key)
    require(linked | omitted == selected, "unaccounted_position_finding")
    return atoms, expectations


def _build(data, limits):
    budget = Budget(limits)
    data = deepcopy(decode(data, budget))
    obj(data, {"bridge_version", "grouping_request", "grouping_response", "selection", "proposal"})
    require(data["bridge_version"] == "1", "bridge_version")
    request = validate_request(data["grouping_request"])
    response = validate_response(request, data["grouping_response"])
    left, right, findings = _selection(data["selection"], request, response)
    if data["proposal"] is None:
        return Preparation(
            "needs_formalization",
            {"input": data, "formal_input": None, "unselected_atom_ids": []},
            {"code": "needs_formalization", "rule": "no_prepared_atoms"},
        )
    proposal = obj(
        data["proposal"],
        {
            "version",
            "origin",
            "decomposition_rationale",
            "model",
            "atoms",
            "pair",
            "omissions",
            "omega",
        },
    )
    subject, contexts = _contexts(proposal["model"])
    fragments = {f["key"]: f for f in request["input"]["fragments"]}
    atoms, expectations = _atoms(proposal, findings, left | right, subject, contexts, fragments)
    pair = obj(proposal["pair"], {"left_atom_id", "right_atom_id", "rationale"})
    text(pair["rationale"])
    left_id, right_id = text(pair["left_atom_id"]), text(pair["right_atom_id"])
    require(left_id != right_id and left_id in atoms and right_id in atoms, "atom_pair_reference")
    for key, members in ((left_id, left), (right_id, right)):
        require({s["finding_key"] for s in atoms[key]["sources"]} <= members, "pair_position_scope")
    formal = {
        "format_version": "1",
        "model": proposal["model"]["formal_model"],
        "left": expectations[left_id],
        "right": expectations[right_id],
    }
    if proposal["omega"] is not None:
        omega = obj(
            proposal["omega"],
            {"origin", "method", "justification", "declared_complete", "variants"},
        )
        origin(omega["origin"])
        text(omega["method"])
        text(omega["justification"])
        require(type(omega["declared_complete"]) is bool, "omega_complete_type")
        formal["omega"] = {"complete": omega["declared_complete"], "variants": omega["variants"]}
    # The packet binds original snapshots, versions, decomposition, source states,
    # context mapping, Ω and exact derived solver input, including all omissions.
    packet = {
        "input": data,
        "formal_input": formal,
        "unselected_atom_ids": sorted(set(atoms) - {left_id, right_id}),
    }
    try:
        parsed = parse_request(formal, budget)
    except FormalError as error:
        if error.code == ErrorCode.INCOMPLETE_OMEGA:
            return Preparation(
                "needs_refinements", packet, {"code": error.code.value, "rule": error.rule}
            )
        raise
    if not parsed.omega_complete:
        return Preparation(
            "needs_refinements",
            packet,
            {"code": "incomplete_omega", "rule": "omega_not_declared_complete"},
        )
    budget.remaining_ms()
    return Preparation("prepared", packet, None)


def prepare(data: dict | str | bytes, *, limits: Limits | None = None) -> Preparation:
    """Explicit standalone preparation step. Structure alone never authorizes solving."""
    try:
        return _build(data, limits or Limits())
    except (BridgeError, FormalError, GroupingError) as error:
        return Preparation("rejected", None, {"code": str(error.code), "rule": error.rule})
    except Exception:  # noqa: BLE001 -- no input or exception text at the boundary.
        return Preparation(
            "rejected", None, {"code": "internal_failure", "rule": "preparation_failure"}
        )
