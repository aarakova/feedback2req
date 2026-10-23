#!/usr/bin/env python3
"""Deterministic offline checks, NOT application acceptance or semantic verification."""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[2]
SCHEMAS = ROOT / "docs/contracts/ai/v1"
OPERATIONS = (
    "extract_feedback",
    "group_findings",
    "generate_requirements",
    "verify_requirement",
)
CATEGORIES = ("technical", "structure", "provenance", "coverage", "consistency")


class InputError(ValueError):
    """Input/configuration error with a safe, content-free diagnostic code."""


def strict_load(path):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise InputError("JSON-DUPLICATE-PROPERTY")
            result[key] = value
        return result

    def constant(_):
        raise InputError("JSON-NONFINITE-NUMBER")

    def floating(value):
        parsed = float(value)
        if not math.isfinite(parsed):
            raise InputError("JSON-NONFINITE-NUMBER")
        return parsed

    try:
        return json.loads(
            Path(path).read_text(encoding="utf-8"),
            object_pairs_hook=pairs,
            parse_constant=constant,
            parse_float=floating,
        )
    except (OSError, UnicodeError, json.JSONDecodeError, RecursionError) as error:
        raise InputError("JSON-UNREADABLE") from error


def walk(value, path=()):
    yield path, value
    if isinstance(value, dict):
        for key, child in value.items():
            yield from walk(child, path + (key,))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from walk(child, path + (index,))


def index(value, field):
    items = [obj for _, obj in walk(value) if isinstance(obj, dict) and field in obj]
    counts = Counter(obj[field] for obj in items)
    return {obj[field]: obj for obj in items}, any(n > 1 for n in counts.values())


def identity(value):
    return value["kind"], value["id"], value["state_id"]


class Contracts:
    def __init__(self):
        self.schemas = {
            p.name: strict_load(p) for p in sorted(SCHEMAS.glob("*.schema.json"))
        }
        expected = {"common.schema.json"} | {
            f"{op}.{direction}.schema.json"
            for op in OPERATIONS
            for direction in ("request", "response")
        }
        if set(self.schemas) != expected:
            raise InputError("SCHEMA-INVENTORY")
        registry = Registry().with_resources(
            (s["$id"], Resource.from_contents(s)) for s in self.schemas.values()
        )
        try:
            for schema in self.schemas.values():
                Draft202012Validator.check_schema(schema)
                for _, obj in walk(schema):
                    if isinstance(obj, dict) and "$ref" in obj:
                        registry.resolver().lookup(obj["$ref"])
        except Exception as error:
            raise InputError("SCHEMA-INVALID-OR-NONLOCAL-REF") from error
        self.validators = {
            name: Draft202012Validator(s, registry=registry)
            for name, s in self.schemas.items()
        }
        # Report paths use only declared property names, never unknown input keys or values.
        self.properties = {
            key
            for s in self.schemas.values()
            for _, obj in walk(s)
            if isinstance(obj, dict)
            for key in obj.get("properties", {})
        }

    def schema_errors(self, operation, direction, value):
        errors = []
        for error in self.validators[
            f"{operation}.{direction}.schema.json"
        ].iter_errors(value):
            pointer = "/" + "/".join(
                str(p) if isinstance(p, int) or p in self.properties else "<field>"
                for p in error.absolute_path
            )
            errors.append(
                {
                    "category": "structure",
                    "code": "SCHEMA-" + error.validator.upper(),
                    "side": direction,
                    "path": pointer,
                }
            )
        return errors


def check_request(contracts, request, trusted):
    if not isinstance(request, dict) or request.get("operation") not in OPERATIONS:
        return [
            {
                "category": "structure",
                "code": "REQUEST-OPERATION",
                "side": "request",
                "path": "/operation",
            }
        ]
    errors = contracts.schema_errors(request["operation"], "request", request)
    if errors:
        return errors

    def fail(code, category="provenance"):
        errors.append(
            {"category": category, "code": code, "side": "request", "path": "/input"}
        )

    data = request["input"]
    _inputs, repeated = index(data, "key")
    if repeated:
        fail("KEYS-NOT-UNIQUE")
    if request["project_id"] != trusted.get("project_id"):
        fail("PROJECT-MISMATCH")
    states = {identity(state) for state in trusted.get("states", [])}
    for _, obj in walk(data):
        if (
            isinstance(obj, dict)
            and set(obj) == {"kind", "id", "state_id"}
            and identity(obj) not in states
        ):
            fail("STATE-NOT-IN-FIXTURE")
    texts = {identity(t["ref"]): t for t in trusted.get("texts", [])}
    docs = {identity(d["ref"]): d for d in trusted.get("documents", [])}
    deleted = {
        obj["source_id"]
        for _, obj in walk(data)
        if isinstance(obj, dict) and obj.get("kind") == "deleted_source"
    }
    if any(t["source_ref"]["id"] in deleted for t in texts.values()):
        fail("DELETED-TEXT-IN-FIXTURE")
    for item in data.get("segments", []) + data.get("fragments", []):
        source = texts.get(identity(item["text_ref"]))
        if source is None:
            fail("TEXT-STATE-UNAVAILABLE")
            continue
        # Draft 2020-12 also accepts mathematically integral JSON numbers (e.g. 0.0).
        # Interpret validated values for indexing; never rewrite the saved input.
        start, end = int(item["locator"]["start"]), int(item["locator"]["end"])
        content = item.get("text", item.get("quote"))
        if (
            not 0 <= start < end <= len(source["text"])
            or source["text"][start:end] != content
        ):
            fail("LOCATOR-OR-TEXT")
        if item["source_ref"] != source["source_ref"]:
            fail("SOURCE-MISMATCH")
        if item["reliability"] != source["reliability"]:
            fail("RELIABILITY-MISMATCH")
        if item.get("time_range") != source.get("time_range"):
            fail("TIME-MAPPING-MISMATCH")
        if (
            "time_range" in item
            and item["time_range"]["end_ms"] <= item["time_range"]["start_ms"]
        ):
            fail("TIME-ORDER")
    for document in data["documents"]:
        source = docs.get(identity(document["ref"]))
        if source is None:
            fail("DOCUMENT-STATE-UNAVAILABLE")
            continue
        start, end = int(document["locator"]["start"]), int(document["locator"]["end"])
        if (
            not 0 <= start < end <= len(source["text"])
            or source["text"][start:end] != document["text"]
        ):
            fail("DOCUMENT-LOCATOR-OR-TEXT")
    findings = {
        f["key"]: f for f in data.get("findings", data.get("previous_findings", []))
    }
    fragments = {
        f["key"]: f for f in data.get("fragments", data.get("previous_fragments", []))
    }
    for finding in findings.values():
        for link in finding["evidence"]:
            if link["kind"] == "available" and link["fragment_key"] not in fragments:
                fail("INPUT-EVIDENCE-MISSING")
    revisions = data.get("previous_candidates", []) + (
        [data["target"]] if "target" in data else []
    )
    for revision in revisions:
        for entry in revision["evidence"]:
            finding = findings.get(entry["finding_key"])
            if finding is None or any(
                link not in finding["evidence"] for link in entry["links"]
            ):
                fail("REVISION-EVIDENCE-MISMATCH")
    for group in data.get("groups", []) + data.get("previous_groups", []):
        members = set(group["finding_keys"])
        if not members <= findings.keys():
            fail("INPUT-GROUP-MEMBERS")
        for conflict in group["conflicts"]:
            if any(
                not set(p["finding_keys"]) <= members for p in conflict["positions"]
            ):
                fail("INPUT-CONFLICT-MEMBERS")
    if request["operation"] == "verify_requirement":
        comparisons = data["comparisons"]
        scope = data["comparison_scope"]
        if scope != trusted.get("comparison_scope") or comparisons != trusted.get(
            "comparisons"
        ):
            fail("COMPARISON-SNAPSHOT-MISMATCH")
        required = set(scope["required_keys"])
        available = {c["key"] for c in comparisons}
        default = {
            c["key"]
            for c in comparisons
            if set(c["roles"]) & {"current", "pending_change", "new_candidate"}
        }
        if not required <= available or (
            scope["extent"] == "project_snapshot" and not default <= required
        ):
            fail("COMPARISON-REQUIRED-SET")
        seen = set()
        for comparison in comparisons:
            ident = identity(comparison["ref"])
            if ident == identity(data["target"]["ref"]) or ident in seen:
                fail("COMPARISON-REPEATED-OR-TARGET")
            seen.add(ident)
        # These facts are trusted fixture facts, not inferred by the evaluator.
        for field in (
            "prior_decision",
            "change_context",
            "followup",
            "previous_checks",
        ):
            if data.get(field) != trusted.get(field):
                fail("HISTORY-CONTEXT-MISMATCH")
    return errors


def check_response(contracts, request, response, trusted):
    operation, data = request["operation"], request["input"]
    errors = contracts.schema_errors(operation, "response", response)
    if errors:
        return errors, {}

    def fail(code, category="provenance"):
        errors.append(
            {"category": category, "code": code, "side": "response", "path": "/"}
        )

    inputs, _ = index(data, "key")
    outputs, repeated = index(response, "local_id")
    if repeated:
        fail("LOCAL-IDS-NOT-UNIQUE")
    primary = (
        {i["key"] for i in data["segments"]}
        if operation == "extract_feedback"
        else (
            {data["target"]["key"]}
            if operation == "verify_requirement"
            else {i["key"] for i in data["findings"]}
        )
    )
    coverage = {i["input_key"]: i for i in response["coverage"]}
    if Counter(i["input_key"] for i in response["coverage"]) != Counter(
        {k: 1 for k in primary}
    ):
        fail("COVERAGE-KEYS", "coverage")
    reviewed = {key for key, item in coverage.items() if item["reviewed"]}
    for _, obj in walk(response):
        if not isinstance(obj, dict):
            continue
        if (
            "origin" in obj
            and "key" in obj
            and obj["key"] not in (inputs if obj["origin"] == "input" else outputs)
        ):
            fail("LINK-UNRESOLVED")
    result = response["result"]
    contextual = {d["key"] for d in data["documents"]}
    if operation == "generate_requirements":
        contextual |= {g["key"] for g in data["groups"]}
    candidates = (
        result.get("findings", [])
        + result.get("groups", [])
        + result.get("requirements", [])
    )
    for candidate in candidates:
        considered = set(candidate["considered_keys"])
        if (
            not considered <= primary
            or not set(candidate["context_keys"]) <= contextual
        ):
            fail("LINK-WRONG-ROLE")
        if not considered <= reviewed:
            fail("RESULT-FROM-UNREVIEWED", "coverage")
    question_targets = primary | {
        i["key"] for field in ("findings", "groups") for i in data.get(field, [])
    }
    if "target" in data:
        question_targets.add(data["target"]["key"])
    output_targets = {c["local_id"] for c in candidates}
    for question in response["questions"]:
        for link in question["related"]:
            if link["key"] not in (
                question_targets if link["origin"] == "input" else output_targets
            ):
                fail("QUESTION-SCOPE", "consistency")
    derived = []
    if operation == "extract_feedback":
        segments = {s["key"]: s for s in data["segments"]}
        fragments = {f["local_id"]: f for f in result["fragments"]}
        for fragment in fragments.values():
            segment = segments.get(fragment["segment_key"])
            if segment is None:
                fail("FRAGMENT-SEGMENT-MISSING")
                continue
            if fragment["segment_key"] not in reviewed:
                fail("RESULT-FROM-UNREVIEWED", "coverage")
            matches = [
                m.start()
                for m in re.finditer(
                    "(?=" + re.escape(fragment["quote"]) + ")", segment["text"]
                )
            ]
            if fragment["occurrence"] >= len(matches):
                fail("QUOTE-OCCURRENCE")
            else:
                start = (
                    int(segment["locator"]["start"])
                    + matches[int(fragment["occurrence"])]
                )
                derived.append(
                    {
                        "locator": {
                            "start": start,
                            "end": start + len(fragment["quote"]),
                        },
                        "reliability": segment["reliability"],
                        **(
                            {"time_range": segment["time_range"]}
                            if "time_range" in segment
                            else {}
                        ),
                    }
                )
        for finding in result["findings"]:
            if not set(finding["fragment_ids"]) <= fragments.keys():
                fail("FINDING-FRAGMENT-MISSING")
    elif operation == "group_findings":
        grouped = set()
        for group in result["groups"]:
            members = set(group["finding_keys"])
            grouped |= members
            if not members <= primary:
                fail("GROUP-MEMBER-MISSING")
            if not members <= reviewed:
                fail("RESULT-FROM-UNREVIEWED", "coverage")
            if not members <= set(group["considered_keys"]):
                fail("GROUP-MEMBER-NOT-CONSIDERED", "coverage")
            for conflict in group["conflicts"]:
                if any(
                    not set(p["finding_keys"]) <= members for p in conflict["positions"]
                ):
                    fail("CONFLICT-MEMBER-OUTSIDE-GROUP")
        ungrouped = set(result["ungrouped_finding_keys"])
        completed = {
            key for key, item in coverage.items() if item["disposition"] == "completed"
        }
        if (
            grouped & ungrouped
            or not ungrouped <= primary
            or not completed <= grouped | ungrouped
        ):
            fail("GROUP-COVERAGE", "coverage")
        if not ungrouped <= reviewed:
            fail("RESULT-FROM-UNREVIEWED", "coverage")
    elif operation == "generate_requirements":
        findings = {f["key"]: f for f in data["findings"]}
        fragments = {f["key"] for f in data["fragments"]}
        supported = set()
        for candidate in result["requirements"]:
            for selection in candidate["evidence"]:
                key = selection["finding_key"]
                finding = findings.get(key)
                available = (
                    set()
                    if finding is None
                    else {
                        link["fragment_key"]
                        for link in finding["evidence"]
                        if link["kind"] == "available"
                    }
                )
                if not set(selection["fragment_keys"]) <= available & fragments:
                    fail("REQUIREMENT-EVIDENCE-MISMATCH")
                if key not in reviewed or key not in candidate["considered_keys"]:
                    fail("EVIDENCE-NOT-CONSIDERED", "coverage")
                supported.add(key)
        for key, item in coverage.items():
            if (
                item["disposition"] == "completed"
                and key not in supported
                and not item.get("reason")
            ):
                fail("EMPTY-RESULT-REASON", "coverage")
    else:
        checks = {c["kind"]: c for c in result["checks"]}
        comparisons = {c["key"]: c for c in data["comparisons"]}
        duplicates = checks["duplicates"]
        considered = set(duplicates["considered_keys"])
        required = set(data["comparison_scope"]["required_keys"])
        if not considered <= comparisons.keys():
            fail("COMPARISON-CONSIDERED-ROLE")
        missed = required - considered
        if missed:
            if duplicates["conclusion"] == "no_issue_found":
                fail("DUPLICATES-INCOMPLETE-CLEAN", "coverage")
            if (
                coverage.get(data["target"]["key"], {}).get("disposition")
                != "partially_processed"
            ):
                fail("COMPARISON-PARTIAL-COVERAGE", "coverage")
        noncomparison = {data["target"]["key"]} | {
            item["key"]
            for field in ("findings", "fragments", "documents")
            for item in data[field]
        }
        for kind, check in checks.items():
            if (
                kind != "duplicates"
                and not set(check["considered_keys"]) <= noncomparison
            ):
                fail("CHECK-CONSIDERED-ROLE")
            if not reviewed and check["considered_keys"]:
                fail("RESULT-FROM-UNREVIEWED", "coverage")
        question_ids = {q["local_id"] for q in response["questions"]}
        categories = {
            "unsupported_claim": "support",
            "insufficient_evidence": "support",
            "contradiction": "contradictions",
            "ambiguity": "ambiguity",
            "possible_duplicate": "duplicates",
        }
        observed = set()
        for issue in result["issues"]:
            kind = categories[issue["category"]]
            observed.add(kind)
            if checks[kind]["conclusion"] == "no_issue_found":
                fail("ISSUE-CHECK-CONTRADICTION", "consistency")
            if not set(issue["question_ids"]) <= question_ids:
                fail("ISSUE-QUESTION-MISSING")
            if issue["category"] == "possible_duplicate":
                linked = [
                    comparisons[link["key"]]
                    for link in issue["related"]
                    if link["origin"] == "input" and link["key"] in comparisons
                ]
                if not any(
                    c["requirement_id"] != data["target"]["requirement_id"]
                    for c in linked
                ):
                    fail("DUPLICATE-SAME-REQUIREMENT")
                if any(c["key"] not in considered for c in linked):
                    fail("DUPLICATE-NOT-CONSIDERED", "coverage")
        for kind, check in checks.items():
            if check["conclusion"] == "issues_found" and kind not in observed:
                fail("CHECK-ISSUE-MISSING", "consistency")
    if operation != "verify_requirement":
        for item in coverage.values():
            if item["disposition"] == "partially_processed" and not trusted.get(
                "partial_plan"
            ):
                fail("PARTIAL-UNITS-UNRESOLVED", "coverage")
    facts = {
        "coverage": {
            state: sum(i["disposition"] == state for i in response["coverage"])
            for state in (
                "completed",
                "insufficient_information",
                "not_processed",
                "partially_processed",
            )
        },
        "declared_reviewed": sum(i["reviewed"] for i in response["coverage"]),
        "primary_units": len(primary),
        "derived_fragments": derived,
        "open_prior_blockers": sum(
            issue["is_open"] and issue["blocking"]
            for check in data.get("previous_checks", [])
            for issue in check["issues"]
        ),
        "scope": data.get("comparison_scope", {}).get("extent"),
        "semantic_reading_proven": False,
    }
    return errors, facts
