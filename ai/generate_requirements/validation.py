"""Generation contract and evidence connectivity; semantic support needs review."""

from collections import Counter
from copy import deepcopy
from functools import lru_cache

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from ai.group_findings import validation as shared


class GenerationError(shared.GroupingError):
    """Safe generation diagnostic, with the shared code/rule interface."""


def decode(raw, *, side="response"):
    try:
        return shared.decode(raw, side=side)
    except shared.GroupingError as error:
        raise GenerationError(error.code, error.rule) from None


def snapshot(value, *, side):
    try:
        return shared.snapshot(value, side=side)
    except shared.GroupingError as error:
        raise GenerationError(error.code, error.rule) from None


@lru_cache(maxsize=1)
def contracts():
    common = shared.contracts()["common"].schema
    schemas = {"common": common}
    for side in ("request", "response"):
        schemas[side] = decode(
            (shared.SCHEMAS / f"generate_requirements.{side}.schema.json").read_bytes(),
        )

    def no_retrieval(_):
        raise GenerationError("configuration_error", "nonlocal_schema")

    registry = Registry(retrieve=no_retrieval).with_resources(
        (s["$id"], Resource.from_contents(s)) for s in schemas.values()
    )
    for schema in schemas.values():
        Draft202012Validator.check_schema(schema)
    return {
        name: Draft202012Validator(schema, registry=registry)
        for name, schema in schemas.items()
    }


def response_format():
    """Reachable definitions only; no remote schema resolution or file mutation."""
    validators = contracts()
    common = validators["common"].schema
    value = deepcopy(validators["response"].schema)
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


def _require(condition, code, rule):
    if not condition:
        raise GenerationError(code, rule)


def _schema(value, side):
    code = "invalid_request" if side == "request" else "invalid_response"
    _require(next(contracts()[side].iter_errors(value), None) is None, code, "schema")


def _index(value, field, code):
    objects = [
        obj for obj in shared.walk(value) if isinstance(obj, dict) and field in obj
    ]
    counts = Counter(obj[field] for obj in objects)
    _require(all(n == 1 for n in counts.values()), code, field + "_unique")
    return {obj[field]: obj for obj in objects}


def validate_request(value):
    value = snapshot(value, side="request")
    _schema(value, "request")
    code, data = "invalid_request", value["input"]
    _index(data, "key", code)
    # Reuse common Finding/Fragment/Document/Group checks through a local view.
    # This view is never transmitted and does not change either canonical schema.
    common_view = {
        **{key: value[key] for key in ("contract_version", "project_id", "request_id")},
        "operation": "group_findings",
        "input": {
            "findings": data["findings"],
            "fragments": data["fragments"],
            "documents": data["documents"],
            "previous_groups": data["groups"],
        },
    }
    try:
        shared.validate_request(common_view)
    except shared.GroupingError as error:
        raise GenerationError(error.code, error.rule) from None
    findings = {f["key"]: f for f in data["findings"]}
    for previous in data.get("previous_candidates", []):
        for entry in previous["evidence"]:
            finding = findings.get(entry["finding_key"])
            _require(finding is not None, code, "previous_finding_reference")
            _require(
                all(link in finding["evidence"] for link in entry["links"]),
                code,
                "previous_evidence_mismatch",
            )
    return value


def validate_response(request, response):
    request = validate_request(request)
    value = snapshot(response, side="response")
    _schema(value, "response")
    code, data = "invalid_response", request["input"]
    inputs = _index(data, "key", "invalid_request")
    outputs = _index(value, "local_id", code)
    findings = {f["key"]: f for f in data["findings"]}
    fragments = {f["key"] for f in data["fragments"]}
    primary = set(findings)
    context = {obj["key"] for field in ("groups", "documents") for obj in data[field]}
    _require(
        Counter(c["input_key"] for c in value["coverage"]) == Counter(primary),
        code,
        "coverage_keys",
    )
    coverage = {c["input_key"]: c for c in value["coverage"]}
    _require(
        all(c["disposition"] != "partially_processed" for c in coverage.values()),
        code,
        "partial_scope_unverifiable",
    )
    reviewed = {key for key, item in coverage.items() if item["reviewed"]}
    supported = set()
    for candidate in value["result"]["requirements"]:
        considered = set(candidate["considered_keys"])
        _require(considered <= primary, code, "considered_role")
        _require(considered <= reviewed, code, "unreviewed_result")
        _require(set(candidate["context_keys"]) <= context, code, "context_role")
        for entry in candidate["evidence"]:
            key = entry["finding_key"]
            _require(key in findings, code, "evidence_finding")
            _require(key in considered, code, "evidence_not_considered")
            available = {
                link["fragment_key"]
                for link in findings[key]["evidence"]
                if link["kind"] == "available"
            }
            _require(
                set(entry["fragment_keys"]) <= available & fragments,
                code,
                "evidence_fragment",
            )
            supported.add(key)
    for key, item in coverage.items():
        if item["disposition"] == "completed" and key not in supported:
            _require(bool(item.get("reason")), code, "empty_result_reason")
    candidate_ids = {r["local_id"] for r in value["result"]["requirements"]}
    question_inputs = (
        primary
        | {g["key"] for g in data["groups"]}
        | {p["key"] for p in data.get("previous_candidates", [])}
    )
    for item in value["questions"] + value["uncertainties"]:
        for link in item["related"]:
            _require(
                link["key"] in (inputs if link["origin"] == "input" else outputs),
                code,
                "related_reference",
            )
    for question in value["questions"]:
        for link in question["related"]:
            _require(
                link["key"]
                in (question_inputs if link["origin"] == "input" else candidate_ids),
                code,
                "question_scope",
            )
    return value
