"""Runtime acceptance of the approved atomic extract contract, never semantic proof."""

import json
import re
from copy import deepcopy
from functools import lru_cache
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource


class InvalidResponse(Exception):
    pass


def unique_json(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise InvalidResponse()
        result[key] = value
    return result


def decode(raw):
    def invalid(_):
        raise InvalidResponse()

    try:
        return json.loads(raw, object_pairs_hook=unique_json, parse_constant=invalid)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise InvalidResponse() from exc


@lru_cache(maxsize=8)
def schema(name):
    # Both source checkout and packaged Docker image carry the unchanged schemas.
    root = Path(__file__).resolve().parents[3] / "docs/contracts/ai/v1"
    resources = [json.loads(path.read_text(encoding="utf-8")) for path in root.glob("*.json")]
    registry = Registry().with_resources(
        (item["$id"], Resource.from_contents(item)) for item in resources
    )
    target = next(item for item in resources if item["title"] == name)
    return Draft202012Validator(target, registry=registry)


@lru_cache(maxsize=1)
def response_format():
    """Self-contained schema for the provider; never retrieve .invalid schema URLs."""
    value = deepcopy(schema("extract_feedback.response").schema)
    common_path = Path(__file__).resolve().parents[3] / "docs/contracts/ai/v1/common.schema.json"
    common = json.loads(common_path.read_text(encoding="utf-8"))
    value["$defs"] = common["$defs"]
    return json.loads(json.dumps(value).replace(common["$id"] + "#/$defs/", "#/$defs/"))


def request(project_id, request_id, source_id, state_id, text):
    ref = {"kind": "feedback_source", "id": str(source_id), "state_id": str(state_id)}
    value = {
        "contract_version": "1.0",
        "operation": "extract_feedback",
        "project_id": str(project_id),
        "request_id": str(request_id),
        "input": {
            "segments": [
                {
                    "key": "s1",
                    "source_ref": ref,
                    "text_ref": ref,
                    "text": text,
                    "locator": {"start": 0, "end": len(text)},
                    "reliability": "usable",
                }
            ],
            "documents": [],
        },
    }
    schema("extract_feedback.request").validate(value)
    return value


def accept(req, response):
    try:
        schema("extract_feedback.response").validate(response)

        # All persisted strings must also be legal PostgreSQL UTF-8 text.
        def walk(value):
            if isinstance(value, str):
                if "\x00" in value or len(value) > 32768:
                    raise InvalidResponse()
                value.encode("utf-8", "strict")
            elif isinstance(value, dict):
                for item in value.values():
                    walk(item)
            elif isinstance(value, list):
                for item in value:
                    walk(item)

        walk(response)
        segment = req["input"]["segments"][0]
        cov = response["coverage"][0]
        if cov["input_key"] != segment["key"]:
            raise InvalidResponse()
        fragments = response["result"]["fragments"]
        findings = response["result"]["findings"]
        outputs = fragments + findings + response["questions"] + response["uncertainties"]
        ids = [item["local_id"] for item in outputs]
        if len(ids) != len(set(ids)) or any(len(item) > 256 for item in ids):
            raise InvalidResponse()
        positions = {}
        for fragment in fragments:
            if fragment["segment_key"] != segment["key"]:
                raise InvalidResponse()
            matches = list(re.finditer("(?=" + re.escape(fragment["quote"]) + ")", segment["text"]))
            if fragment["occurrence"] >= len(matches):
                raise InvalidResponse()
            start = matches[fragment["occurrence"]].start() + segment["locator"]["start"]
            positions[fragment["local_id"]] = (start, start + len(fragment["quote"]))
        for finding in findings:
            if (
                not set(finding["fragment_ids"]) <= positions.keys()
                or finding["considered_keys"] != [segment["key"]]
                or finding["context_keys"]
            ):
                raise InvalidResponse()
        output_kinds = {item["local_id"]: "finding" for item in findings}
        # Questions affect a finding or the primary unit, not a random fragment.
        for item in response["questions"] + response["uncertainties"]:
            for link in item["related"]:
                if link["origin"] == "input":
                    if link["key"] != segment["key"]:
                        raise InvalidResponse()
                elif link["key"] not in output_kinds:
                    raise InvalidResponse()
        if cov["disposition"] == "not_processed" and (fragments or findings):
            raise InvalidResponse()
        return positions
    except InvalidResponse:
        raise
    except Exception as exc:
        # Callers persist only the stable invalid_response code, never str(exc).
        raise InvalidResponse() from exc
