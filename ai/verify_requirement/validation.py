"""Verification connectivity/coverage acceptance, never proof of semantic truth."""

from collections import Counter
from copy import deepcopy
from dataclasses import dataclass
from functools import lru_cache

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from ai.group_findings import validation as shared

ASSESSMENTS = frozenset({"support", "contradictions", "ambiguity"})
KINDS = ASSESSMENTS | {"duplicates"}
CATEGORIES = {
    "unsupported_claim": "support",
    "insufficient_evidence": "support",
    "contradiction": "contradictions",
    "ambiguity": "ambiguity",
    "possible_duplicate": "duplicates",
}
CONTEXT_FIELDS = frozenset({"prior_decision", "change_context", "followup"})


class VerificationError(shared.GroupingError):
    """Content-free code/rule diagnostic, compatible with existing AI modules."""


@dataclass(frozen=True)
class ReviewPlan:
    """Trusted executor metadata, NEVER reconstructed from a model's response.

    checked_assessments names completed non-duplicate checks, even if their
    semantic conclusion is inconclusive. comparison_keys identifies completed
    comparison units. No text-level partial reading can be established by this.
    """

    checked_assessments: frozenset[str]
    comparison_keys: frozenset[str]


def _require(condition, code, rule):
    if not condition:
        raise VerificationError(code, rule)


def decode(raw, *, side="response"):
    try:
        return shared.decode(raw, side=side)
    except shared.GroupingError as error:
        raise VerificationError(error.code, error.rule) from None


def _snapshot(value, side):
    try:
        return shared.snapshot(value, side=side)
    except shared.GroupingError as error:
        raise VerificationError(error.code, error.rule) from None


@lru_cache(maxsize=1)
def contracts():
    schemas = {"common": shared.contracts()["common"].schema}
    for side in ("request", "response"):
        schemas[side] = decode(
            (shared.SCHEMAS / f"verify_requirement.{side}.schema.json").read_bytes()
        )

    def no_retrieval(_):
        raise VerificationError("configuration_error", "nonlocal_schema")

    registry = Registry(retrieve=no_retrieval).with_resources(
        (s["$id"], Resource.from_contents(s)) for s in schemas.values()
    )
    for schema in schemas.values():
        Draft202012Validator.check_schema(schema)
    return {
        name: Draft202012Validator(s, registry=registry) for name, s in schemas.items()
    }


def response_format():
    common = contracts()["common"].schema
    value = deepcopy(contracts()["response"].schema)
    definitions, pending = {}, [value]
    prefix = common["$id"] + "#/$defs/"
    while pending:
        for obj in shared.walk(pending.pop()):
            if (
                isinstance(obj, dict)
                and "$ref" in obj
                and obj["$ref"].startswith(prefix)
            ):
                name = obj["$ref"][len(prefix) :]
                obj["$ref"] = "#/$defs/" + name
                if name not in definitions:
                    definitions[name] = deepcopy(common["$defs"][name])
                    pending.append(definitions[name])
    value["$defs"] = definitions
    return value


def _schema(value, side):
    _require(
        next(contracts()[side].iter_errors(value), None) is None,
        "invalid_" + side,
        "schema",
    )


def _index(value, field, code):
    objects = [v for v in shared.walk(value) if isinstance(v, dict) and field in v]
    counts = Counter(v[field] for v in objects)
    _require(all(n == 1 for n in counts.values()), code, field + "_unique")
    return {v[field]: v for v in objects}


def identity(ref):
    return ref["kind"], ref["id"], ref["state_id"]


def validate_request(request, *, required_context=frozenset()):
    value = _snapshot(request, "request")
    _schema(value, "request")
    code, data = "invalid_request", value["input"]
    _require(
        type(required_context) is frozenset and required_context <= CONTEXT_FIELDS,
        "configuration_error",
        "required_context",
    )
    _require(required_context <= data.keys(), code, "required_context_missing")
    _index(data, "key", code)
    findings = {f["key"]: f for f in data["findings"]}
    for entry in data["target"]["evidence"]:
        finding = findings.get(entry["finding_key"])
        _require(finding is not None, code, "target_finding_reference")
        _require(
            all(link in finding["evidence"] for link in entry["links"]),
            code,
            "target_evidence_mismatch",
        )
    common_view = {
        **{k: value[k] for k in ("contract_version", "project_id", "request_id")},
        "operation": "group_findings",
        "input": {
            "findings": data["findings"],
            "fragments": data["fragments"],
            "documents": data["documents"],
        },
    }
    try:
        shared.validate_request(common_view)
    except shared.GroupingError as error:
        raise VerificationError(error.code, error.rule) from None
    comparisons = {c["key"]: c for c in data["comparisons"]}
    required = set(data["comparison_scope"]["required_keys"])
    _require(required <= comparisons.keys(), code, "comparison_required_reference")
    if data["comparison_scope"]["extent"] == "project_snapshot":
        default = {
            c["key"]
            for c in comparisons.values()
            if set(c["roles"]) & {"current", "pending_change", "new_candidate"}
        }
        _require(default <= required, code, "comparison_required_set")
    seen = set()
    for comparison in comparisons.values():
        ref = identity(comparison["ref"])
        _require(
            ref != identity(data["target"]["ref"]) and ref not in seen,
            code,
            "comparison_repeated_or_target",
        )
        seen.add(ref)
    if "change_context" in data:
        base = data["change_context"]["base_revision_ref"]
        _require(base != data["target"]["ref"], code, "change_base_is_target")
        for comparison in comparisons.values():
            if comparison["ref"] == base:
                _require(
                    comparison["requirement_id"] == data["target"]["requirement_id"],
                    code,
                    "change_base_requirement",
                )
    if "prior_decision" in data:
        ref = data["prior_decision"]["revision_ref"]
        for comparison in comparisons.values():
            if comparison["ref"] == ref:
                _require(
                    comparison["requirement_id"] == data["target"]["requirement_id"],
                    code,
                    "prior_decision_requirement",
                )
    previous = {identity(c["ref"]): c for c in data["previous_checks"]}
    _require(
        len(previous) == len(data["previous_checks"]), code, "previous_result_unique"
    )
    for check in previous.values():
        _require(
            len({identity(i["ref"]) for i in check["issues"]}) == len(check["issues"]),
            code,
            "previous_issue_unique",
        )
    if "followup" in data:
        followup = data["followup"]
        check = previous.get(identity(followup["previous_result_ref"]))
        _require(check is not None, code, "followup_result")
        _require(
            {identity(r) for r in followup["issue_refs"]}
            <= {identity(i["ref"]) for i in check["issues"]},
            code,
            "followup_issue",
        )
    return value


def validate_response(request, response, *, review_plan=None):
    request = validate_request(request)
    value = _snapshot(response, "response")
    _schema(value, "response")
    code, data = "invalid_response", request["input"]
    inputs = _index(data, "key", "invalid_request")
    outputs = _index(value, "local_id", code)
    target = data["target"]["key"]
    coverage = value["coverage"][0]
    _require(coverage["input_key"] == target, code, "coverage_target")
    checks = {c["kind"]: c for c in value["result"]["checks"]}
    _require(set(checks) == KINDS, code, "check_kinds")
    _require(
        bool(data["fragments"]) or checks["support"]["conclusion"] != "no_issue_found",
        code,
        "support_without_available_evidence",
    )
    comparisons = {c["key"]: c for c in data["comparisons"]}
    required = set(data["comparison_scope"]["required_keys"])
    considered = set(checks["duplicates"]["considered_keys"])
    _require(considered <= comparisons.keys(), code, "comparison_considered_role")
    if review_plan is not None:
        _require(isinstance(review_plan, ReviewPlan), code, "partial_plan_invalid")
        _require(
            type(review_plan.checked_assessments) is frozenset
            and review_plan.checked_assessments <= ASSESSMENTS
            and type(review_plan.comparison_keys) is frozenset
            and review_plan.comparison_keys <= comparisons.keys(),
            code,
            "partial_plan_invalid",
        )
        _require(
            considered == review_plan.comparison_keys, code, "partial_plan_mismatch"
        )
        if coverage["reviewed"] and coverage["disposition"] != "partially_processed":
            _require(
                review_plan.checked_assessments == ASSESSMENTS
                and required <= review_plan.comparison_keys,
                code,
                "plan_coverage_mismatch",
            )
        if not coverage["reviewed"]:
            _require(
                not (review_plan.checked_assessments or review_plan.comparison_keys),
                code,
                "plan_coverage_mismatch",
            )
    noncomparison = {target} | {
        i["key"]
        for field in ("findings", "fragments", "documents")
        for i in data[field]
    }
    for kind in ASSESSMENTS:
        _require(
            set(checks[kind]["considered_keys"]) <= noncomparison,
            code,
            "check_considered_role",
        )
    if not coverage["reviewed"]:
        _require(not value["result"]["issues"], code, "unreviewed_issues")
        _require(
            all(
                not c["considered_keys"] and c["conclusion"] == "inconclusive"
                for c in checks.values()
            ),
            code,
            "unreviewed_assessment",
        )
    else:
        if coverage["disposition"] == "partially_processed":
            _require(isinstance(review_plan, ReviewPlan), code, "partial_plan_required")
            _require(
                type(review_plan.checked_assessments) is frozenset
                and review_plan.checked_assessments <= ASSESSMENTS
                and type(review_plan.comparison_keys) is frozenset
                and review_plan.comparison_keys <= comparisons.keys(),
                code,
                "partial_plan_invalid",
            )
            executed = review_plan.checked_assessments
            _require(
                considered == review_plan.comparison_keys, code, "partial_plan_mismatch"
            )
            _require(
                bool(executed or considered)
                and not (executed == ASSESSMENTS and required <= considered),
                code,
                "partial_plan_not_partial",
            )
        else:
            executed = ASSESSMENTS
            _require(required <= considered, code, "comparison_incomplete_coverage")
        for kind in ASSESSMENTS:
            if kind in executed:
                _require(
                    target in checks[kind]["considered_keys"],
                    code,
                    "check_target_not_considered",
                )
            else:
                _require(
                    not checks[kind]["considered_keys"]
                    and checks[kind]["conclusion"] == "inconclusive",
                    code,
                    "skipped_check_result",
                )
        if required - considered:
            _require(
                checks["duplicates"]["conclusion"] != "no_issue_found",
                code,
                "incomplete_duplicate_clean",
            )
    for obj in value["questions"] + value["uncertainties"] + value["result"]["issues"]:
        for link in obj["related"]:
            _require(
                link["key"] in (inputs if link["origin"] == "input" else outputs),
                code,
                "related_reference",
            )
    question_inputs = {target} | {f["key"] for f in data["findings"]}
    issue_ids = {i["local_id"] for i in value["result"]["issues"]}
    for question in value["questions"]:
        for link in question["related"]:
            _require(
                link["key"]
                in (question_inputs if link["origin"] == "input" else issue_ids),
                code,
                "question_scope",
            )
    question_ids = {q["local_id"] for q in value["questions"]}
    questions = {q["local_id"]: q for q in value["questions"]}
    observed = set()
    for issue in value["result"]["issues"]:
        kind = CATEGORIES[issue["category"]]
        observed.add(kind)
        _require(
            checks[kind]["conclusion"] != "no_issue_found", code, "issue_check_conflict"
        )
        _require(
            set(issue["question_ids"]) <= question_ids, code, "issue_question_reference"
        )
        for question_id in issue["question_ids"]:
            issue_inputs = {
                l["key"] for l in issue["related"] if l["origin"] == "input"
            } | {target}
            _require(
                any(
                    (l["origin"] == "output" and l["key"] == issue["local_id"])
                    or (l["origin"] == "input" and l["key"] in issue_inputs)
                    for l in questions[question_id]["related"]
                ),
                code,
                "issue_question_scope",
            )
        allowed = {target} | set(checks[kind]["considered_keys"])
        for link in issue["related"]:
            if link["origin"] == "input":
                _require(link["key"] in allowed, code, "issue_not_considered")
        if kind != "duplicates":
            _require(
                target in checks[kind]["considered_keys"],
                code,
                "issue_target_not_considered",
            )
        else:
            linked = [
                comparisons[l["key"]]
                for l in issue["related"]
                if l["origin"] == "input" and l["key"] in comparisons
            ]
            _require(
                any(
                    c["requirement_id"] != data["target"]["requirement_id"]
                    for c in linked
                ),
                code,
                "duplicate_same_requirement",
            )
    for kind, check in checks.items():
        _require(
            check["conclusion"] != "issues_found" or kind in observed,
            code,
            "check_issue_missing",
        )
    _require(
        coverage["disposition"] != "insufficient_information"
        or any(c["conclusion"] != "no_issue_found" for c in checks.values()),
        code,
        "insufficient_clean_result",
    )
    unresolved = any(
        q["blocking"]
        and any(l == {"origin": "input", "key": target} for l in q["related"])
        for q in value["questions"]
    ) or any(
        any(l == {"origin": "input", "key": target} for l in u["related"])
        for u in value["uncertainties"]
    )
    _require(
        not unresolved
        or any(c["conclusion"] != "no_issue_found" for c in checks.values()),
        code,
        "unresolved_clean_result",
    )
    return value
