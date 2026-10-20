"""Проверка схем и демонстрационных примеров, не реализация приёма AI в приложении.

Проверки APP-* охватывают только явно реализованные свойства локальных пар.
Они не проверяют БД, права, реальный состав проекта, актуальность или смысл AI.
Все JSON Schema разрешаются из локального реестра без сетевого retrieval.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from importlib.metadata import version
from pathlib import Path

try:
    from jsonschema import Draft202012Validator
    from referencing import Registry, Resource
except ImportError:
    raise SystemExit(
        "Install validation tools: python -m pip install -r scripts/requirements-ai-contracts.txt"
    )


ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "docs/contracts/ai/v1"
EXAMPLES = ROOT / "docs/contracts/ai/examples"
DRAFT = "https://json-schema.org/draft/2020-12/schema"
OPERATIONS = (
    "extract_feedback", "group_findings", "generate_requirements", "verify_requirement"
)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON property: {key}")
        result[key] = value
    return result


def read_json(path):
    def invalid_constant(value):
        raise ValueError(f"Non-JSON constant: {value}")

    return json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=unique_object,
        parse_constant=invalid_constant,
    )


def walk(value, path=()):
    yield path, value
    if isinstance(value, dict):
        for key, child in value.items():
            yield from walk(child, path + (key,))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from walk(child, path + (index,))


def error_keywords(errors):
    result = set()
    for error in errors:
        result.add(error.validator)
        result.update(error_keywords(error.context))
    return result


def index_objects(value, id_field):
    items = [item for _, item in walk(value) if isinstance(item, dict) and id_field in item]
    counts = Counter(item[id_field] for item in items)
    return {item[id_field]: item for item in items}, {key for key, count in counts.items() if count > 1}


def check_fixture_pair(request, response):
    """Конечные офлайн-assertions примеров; не полный прикладной валидатор."""
    errors = set()
    data = request["input"]
    operation = request["operation"]
    inputs, repeated_inputs = index_objects(data, "key")
    outputs, repeated_outputs = index_objects(response, "local_id")
    if repeated_inputs or repeated_outputs:
        errors.add("APP-KEYS")
    if operation == "extract_feedback":
        primary = {item["key"] for item in data["segments"]}
    elif operation in ("group_findings", "generate_requirements"):
        primary = {item["key"] for item in data["findings"]}
    else:
        primary = {data["target"]["key"]}
    coverage = response["coverage"]
    if Counter(item["input_key"] for item in coverage) != Counter({key: 1 for key in primary}):
        errors.add("APP-COVERAGE")

    for _, value in walk(response):
        if not isinstance(value, dict):
            continue
        if "origin" in value and "key" in value:
            catalog = inputs if value["origin"] == "input" else outputs
            if value["key"] not in catalog:
                errors.add("APP-LINKS")
        if "considered_keys" in value and not set(value["considered_keys"]) <= inputs.keys():
            errors.add("APP-LINKS")
        if "context_keys" in value and not set(value["context_keys"]) <= inputs.keys():
            errors.add("APP-LINKS")

    for _, value in walk(data):
        if isinstance(value, dict) and "locator" in value:
            locator = value["locator"]
            content = value.get("text", value.get("quote"))
            if locator["end"] <= locator["start"]:
                errors.add("APP-LOCATOR")
            if content is not None and locator["end"] - locator["start"] != len(content):
                errors.add("APP-LOCATOR")
        if isinstance(value, dict) and "time_range" in value:
            if value["time_range"]["end_ms"] <= value["time_range"]["start_ms"]:
                errors.add("APP-LOCATOR")

    result = response["result"]
    if operation == "extract_feedback":
        segments = {item["key"]: item for item in data["segments"]}
        previous_fragments = {item["key"]: item for item in data.get("previous_fragments", [])}
        for finding in data.get("previous_findings", []):
            for link in finding["evidence"]:
                if link["kind"] == "available" and link["fragment_key"] not in previous_fragments:
                    errors.add("APP-EVIDENCE")
        fragments = {item["local_id"]: item for item in result["fragments"]}
        for fragment in fragments.values():
            segment = segments.get(fragment["segment_key"])
            if segment is None:
                errors.add("APP-LINKS")
                continue
            # Вхождения считаются по всем начальным позициям, включая перекрытия.
            matches = list(re.finditer("(?=" + re.escape(fragment["quote"]) + ")", segment["text"]))
            if fragment["occurrence"] >= len(matches):
                errors.add("APP-QUOTE")
        for finding in result["findings"]:
            if not set(finding["fragment_ids"]) <= fragments.keys():
                errors.add("APP-EVIDENCE")
            if not set(finding["considered_keys"]) <= segments.keys():
                errors.add("APP-LINKS")
    else:
        fragments = {item["key"]: item for item in data["fragments"]}
        findings = {item["key"]: item for item in data["findings"]}
        for finding in findings.values():
            for link in finding["evidence"]:
                if link["kind"] == "available" and link["fragment_key"] not in fragments:
                    errors.add("APP-EVIDENCE")
        if operation == "generate_requirements":
            for previous in data.get("previous_candidates", []):
                for evidence in previous["evidence"]:
                    finding = findings.get(evidence["finding_key"])
                    if finding is None or any(link not in finding["evidence"] for link in evidence["links"]):
                        errors.add("APP-EVIDENCE")
            for candidate in result["requirements"]:
                for selection in candidate["evidence"]:
                    finding = findings.get(selection["finding_key"])
                    available = set() if finding is None else {
                        link["fragment_key"] for link in finding["evidence"] if link["kind"] == "available"
                    }
                    if not set(selection["fragment_keys"]) <= available or not set(selection["fragment_keys"]) <= fragments.keys():
                        errors.add("APP-EVIDENCE")
        elif operation == "group_findings":
            for previous in data.get("previous_groups", []):
                if not set(previous["finding_keys"]) <= findings.keys():
                    errors.add("APP-GROUPING")
            grouped = set()
            for group in result["groups"]:
                grouped.update(group["finding_keys"])
                if not set(group["finding_keys"]) <= findings.keys():
                    errors.add("APP-GROUPING")
            ungrouped = set(result["ungrouped_finding_keys"])
            completed = {item["input_key"] for item in coverage if item["disposition"] == "completed"}
            if grouped & ungrouped or not ungrouped <= findings.keys() or not completed <= grouped | ungrouped:
                errors.add("APP-GROUPING")
        elif operation == "verify_requirement":
            for evidence in data["target"]["evidence"]:
                finding = findings.get(evidence["finding_key"])
                if finding is None or any(link not in finding["evidence"] for link in evidence["links"]):
                    errors.add("APP-EVIDENCE")
            comparisons = {item["key"]: item for item in data["comparisons"]}
            required = set(data["comparison_scope"]["required_keys"])
            duplicate_check = next(item for item in result["checks"] if item["kind"] == "duplicates")
            considered = set(duplicate_check["considered_keys"])
            if not required <= comparisons.keys() or not considered <= comparisons.keys():
                errors.add("APP-COMPARISON")
            if duplicate_check["conclusion"] == "no_issue_found" and not required <= considered:
                errors.add("APP-COMPARISON")
            target_ref = data["target"]["ref"]
            seen_revisions = set()
            for comparison in comparisons.values():
                identity = (comparison["ref"]["id"], comparison["ref"]["state_id"])
                if comparison["ref"] == target_ref or identity in seen_revisions:
                    errors.add("APP-COMPARISON")
                seen_revisions.add(identity)
            question_ids = {item["local_id"] for item in response["questions"]}
            for issue in result["issues"]:
                if not set(issue["question_ids"]) <= question_ids:
                    errors.add("APP-LINKS")
                if issue["category"] == "possible_duplicate":
                    related_comparisons = [comparisons[link["key"]] for link in issue["related"]
                                           if link["origin"] == "input" and link["key"] in comparisons]
                    if not any(item["requirement_id"] != data["target"]["requirement_id"] for item in related_comparisons):
                        errors.add("APP-DUPLICATE")
    return errors


def main():
    schemas = {path.name: read_json(path) for path in sorted(SCHEMAS.glob("*.schema.json"))}
    expected = {"common.schema.json"} | {
        f"{operation}.{direction}.schema.json" for operation in OPERATIONS for direction in ("request", "response")
    }
    if schemas.keys() != expected:
        raise ValueError("Unexpected schema inventory")
    ids = [schema["$id"] for schema in schemas.values()]
    if len(ids) != len(set(ids)):
        raise ValueError("Repeated schema $id")
    registry = Registry().with_resources(
        (schema["$id"], Resource.from_contents(schema)) for schema in schemas.values()
    )
    reference_count = 0
    for name, schema in schemas.items():
        if schema["$schema"] != DRAFT:
            raise ValueError(f"Wrong dialect: {name}")
        Draft202012Validator.check_schema(schema)
        for _, value in walk(schema):
            if not isinstance(value, dict):
                continue
            if value.get("type") == "object" and value.get("additionalProperties") is not False:
                raise ValueError(f"Open declared object in {name}")
            if "$ref" in value:
                registry.resolver().lookup(value["$ref"])
                reference_count += 1
    validators = {name: Draft202012Validator(schema, registry=registry) for name, schema in schemas.items()}
    manifest = read_json(EXAMPLES / "manifest.json")
    failures = []
    mutation_count = 0
    positive = negative = 0
    for case in manifest["cases"]:
        instance = read_json(EXAMPLES / case["file"])
        validator = validators[case["schema"]]
        errors = list(validator.iter_errors(instance))
        if bool(errors) == case["valid"]:
            failures.append(f"Unexpected schema result: {case['file']}: {[error.message for error in errors[:2]]}")
        if not case["valid"] and case.get("keyword") not in error_keywords(errors):
            failures.append(f"Expected keyword {case.get('keyword')} absent: {case['file']}")
        if case["valid"]:
            positive += 1
            # Проверяем запрет неизвестного поля во всех объектах позитивных примеров.
            for _, value in walk(instance):
                if isinstance(value, dict):
                    value["__unexpected_contract_field__"] = True
                    try:
                        if validator.is_valid(instance):
                            failures.append(f"Unknown nested field accepted: {case['file']}")
                    finally:
                        del value["__unexpected_contract_field__"]
                    mutation_count += 1
        else:
            negative += 1
    # manifest — точный перечень примеров, не частичная выборка.
    listed = {case["file"] for case in manifest["cases"]}
    actual = {path.name for path in EXAMPLES.glob("*.json")} - {"manifest.json"}
    if listed != actual or len(listed) != len(manifest["cases"]):
        failures.append("Example inventory does not match manifest")
    for pair in manifest["pairs"]:
        request = read_json(EXAMPLES / pair["request"])
        response = read_json(EXAMPLES / pair["response"])
        errors = check_fixture_pair(request, response)
        if bool(errors) == pair["application_valid"]:
            failures.append(f"Unexpected fixture-pair result: {pair['response']}: {sorted(errors)}")
        if not pair["application_valid"] and pair["rule"] not in errors:
            failures.append(f"Expected fixture rule {pair['rule']} absent: {pair['response']}")
    if failures:
        print("\n".join(failures))
        return 1
    print(f"PASS jsonschema {version('jsonschema')}; {len(schemas)} Draft 2020-12 schemas; {reference_count} local refs")
    print(f"PASS {positive} schema-positive and {negative} schema-negative examples; {mutation_count} unknown-field mutations")
    print(f"PASS {len(manifest['pairs'])} offline fixture pairs (APP-* checks only)")
    print("NOT CHECKED: live project membership/state, persistence, permissions, providers, AI semantics")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        print(f"VALIDATION ERROR: {type(error).__name__}: {error}", file=sys.stderr)
        sys.exit(1)
