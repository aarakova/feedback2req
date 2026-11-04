"""Local contract and reference checks. These do not establish semantic truth."""

from __future__ import annotations

import json
import math
from collections import Counter
from copy import deepcopy
from functools import lru_cache
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

SCHEMAS = Path(__file__).resolve().parents[2] / "docs/contracts/ai/v1"
MAX_JSON_BYTES = 1_048_576


class GroupingError(Exception):
    """Only safe codes cross the module boundary, never source/model content."""

    def __init__(self, code, rule):
        self.code = code
        self.rule = rule
        super().__init__(code + ":" + rule)


def decode(raw, *, side="response"):
    code = "invalid_request" if side == "request" else "invalid_response"

    def reject(_):
        raise GroupingError(code, "json_number")

    def floating(value):
        number = float(value)
        if not math.isfinite(number):
            reject(value)
        return number

    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise GroupingError(code, "json_duplicate")
            result[key] = value
        return result

    try:
        if not isinstance(raw, (str, bytes)):
            raise GroupingError(code, "json_type")
        size = len(raw.encode("utf-8")) if isinstance(raw, str) else len(raw)
        if size > MAX_JSON_BYTES:
            raise GroupingError(code, "json_size")
        return json.loads(
            raw, object_pairs_hook=pairs, parse_constant=reject, parse_float=floating
        )
    except (ValueError, UnicodeError, RecursionError):
        raise GroupingError(code, "json_decode") from None


def walk(value):
    yield value
    if isinstance(value, dict):
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def snapshot(value, *, side):
    """Isolate callers and adapters without coercing non-JSON Python values."""
    code = "invalid_request" if side == "request" else "invalid_response"
    try:
        for item in walk(value):
            if type(item) not in (dict, list, str, int, float, bool, type(None)):
                raise GroupingError(code, "json_type")
            if isinstance(item, dict) and any(type(k) is not str for k in item):
                raise GroupingError(code, "json_type")
        raw = json.dumps(value, ensure_ascii=False, allow_nan=False)
        return decode(raw, side=side)
    except (TypeError, ValueError, UnicodeError, RecursionError):
        raise GroupingError(code, "json_value") from None


@lru_cache(maxsize=1)
def contracts():
    names = ("common", "group_findings.request", "group_findings.response")
    schemas = {
        name: json.loads((SCHEMAS / (name + ".schema.json")).read_text("utf-8"))
        for name in names
    }

    def no_retrieval(_):
        raise GroupingError("configuration_error", "nonlocal_schema")

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
    """Self-contained provider schema, derived without modifying approved files."""
    validators = contracts()
    common = validators["common"].schema
    value = deepcopy(validators["group_findings.response"].schema)
    # Keep unrelated operations out of a small local model's provider grammar.
    definitions = {}
    pending = [value]
    prefix = common["$id"] + "#/$defs/"
    while pending:
        for obj in walk(pending.pop()):
            if isinstance(obj, dict) and "$ref" in obj:
                reference = obj["$ref"]
                if reference.startswith(prefix):
                    name = reference[len(prefix) :]
                    obj["$ref"] = "#/$defs/" + name
                    if name not in definitions:
                        definitions[name] = deepcopy(common["$defs"][name])
                        pending.append(definitions[name])
    value["$defs"] = definitions
    return value


def _schema(value, side):
    if next(contracts()["group_findings." + side].iter_errors(value), None):
        code = "invalid_request" if side == "request" else "invalid_response"
        raise GroupingError(code, "schema")


def _index(value, field, code):
    objects = [v for v in walk(value) if isinstance(v, dict) and field in v]
    counts = Counter(v[field] for v in objects)
    if any(n != 1 for n in counts.values()):
        raise GroupingError(code, field + "_unique")
    return {v[field]: v for v in objects}


def validate_request(value):
    """Check canonical input locally; caller separately verifies trusted state/access."""
    value = snapshot(value, side="request")
    _schema(value, "request")
    data = value["input"]
    _index(data, "key", "invalid_request")
    findings = {f["key"] for f in data["findings"]}
    fragments = {f["key"] for f in data["fragments"]}

    def require(condition, rule):
        if not condition:
            raise GroupingError("invalid_request", rule)

    deleted = set()
    for finding in data["findings"]:
        for link in finding["evidence"]:
            if link["kind"] == "available":
                require(link["fragment_key"] in fragments, "evidence_reference")
            else:
                deleted.add(link["source_id"])
    for item in data["fragments"] + data["documents"]:
        loc = item["locator"]
        text = item.get("quote", item.get("text"))
        require(loc["end"] - loc["start"] == len(text) > 0, "locator_length")
    for fragment in data["fragments"]:
        require(fragment["source_ref"]["id"] not in deleted, "deleted_source")
        if fragment["text_ref"]["kind"] == "feedback_source":
            require(fragment["text_ref"] == fragment["source_ref"], "text_source")
        if "time_range" in fragment:
            interval = fragment["time_range"]
            require(interval["end_ms"] > interval["start_ms"], "time_order")
    for group in data.get("previous_groups", []):
        members = set(group["finding_keys"])
        require(members <= findings, "previous_group_members")
        for conflict in group["conflicts"]:
            for position in conflict["positions"]:
                require(set(position["finding_keys"]) <= members, "previous_conflict")
    return value


def validate_response(request, value):
    """Accept a whole candidate or reject it. Never repair coverage or drop results.

    A partially_processed declaration needs a trusted execution plan (AI_CONTRACTS
    §6). This single-call implementation has no such plan; it rejects that case.
    Reviewed completed/insufficient units alongside not_processed units are valid.
    """
    request = validate_request(request)
    value = snapshot(value, side="response")
    _schema(value, "response")
    inputs = _index(request["input"], "key", "invalid_request")
    outputs = _index(value, "local_id", "invalid_response")
    data = request["input"]
    primary = {f["key"] for f in data["findings"]}
    documents = {d["key"] for d in data["documents"]}
    previous = {g["key"] for g in data.get("previous_groups", [])}

    def require(condition, rule):
        if not condition:
            raise GroupingError("invalid_response", rule)

    require(
        Counter(c["input_key"] for c in value["coverage"]) == Counter(primary),
        "coverage_keys",
    )
    coverage = {c["input_key"]: c for c in value["coverage"]}
    require(
        all(c["disposition"] != "partially_processed" for c in coverage.values()),
        "partial_scope_unverifiable",
    )
    reviewed = {key for key, c in coverage.items() if c["reviewed"]}
    groups = value["result"]["groups"]
    grouped = set()
    for group in groups:
        members = set(group["finding_keys"])
        considered = set(group["considered_keys"])
        require(members <= considered <= primary, "group_considered")
        require(considered <= reviewed, "unreviewed_result")
        require(set(group["context_keys"]) <= documents, "context_role")
        grouped |= members
        for conflict in group["conflicts"]:
            for position in conflict["positions"]:
                require(set(position["finding_keys"]) <= members, "conflict_members")
    ungrouped = set(value["result"]["ungrouped_finding_keys"])
    require(ungrouped <= reviewed, "ungrouped_reference")
    require(not grouped & ungrouped, "grouped_and_ungrouped")
    completed = {key for key, c in coverage.items() if c["disposition"] == "completed"}
    require(completed <= grouped | ungrouped, "completed_finding_lost")
    # An explicitly ungrouped finding has a substantive classification. An empty
    # group array is therefore not by itself a technical failure or a missing result.
    for item in value["uncertainties"] + value["questions"]:
        for link in item["related"]:
            require(
                link["key"] in (inputs if link["origin"] == "input" else outputs),
                "related_reference",
            )
    group_ids = {g["local_id"] for g in groups}
    for question in value["questions"]:
        for link in question["related"]:
            allowed = primary | previous if link["origin"] == "input" else group_ids
            require(link["key"] in allowed, "question_scope")
    return value
