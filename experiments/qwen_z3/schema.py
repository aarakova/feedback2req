"""Source of the standalone experimental response schema. No AI 1.0 edits."""

import json
from pathlib import Path


def obj(properties):
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


def array(items, minimum=0):
    return {"type": "array", "items": items, "minItems": minimum, "maxItems": 256}


TEXT = {"type": "string", "minLength": 1, "maxLength": 1024}
STRINGS = {**array(TEXT), "uniqueItems": True}
NONEMPTY = {**STRINGS, "minItems": 1}
NULL = {"type": "null"}
REF = obj({"kind": {"const": "finding"}, "id": TEXT, "state_id": TEXT})
NUMBER = {
    "oneOf": [
        {"type": "integer"},
        {"type": "string", "pattern": r"^-?(0|[1-9][0-9]*)(\.[0-9]+)?$", "maxLength": 64},
    ]
}
INTERVAL = {"kind": {"const": "interval"}, "lower": NUMBER, "upper": NUMBER, "unit": TEXT}
VALUES = {
    "oneOf": [
        obj(INTERVAL),
        obj(
            {
                "kind": {"const": "boolean"},
                "allowed": {**array({"type": "boolean"}, 1), "uniqueItems": True},
            }
        ),
        obj({"kind": {"const": "enum"}, "allowed": NONEMPTY}),
    ]
}
DOMAIN = {"oneOf": [obj({**INTERVAL, "dimension": TEXT}), *VALUES["oneOf"][1:]]}
CONFLICT = obj(
    {
        "group_local_id": TEXT,
        "conflict_local_id": TEXT,
        "left_position": {"type": "integer", "minimum": 0},
        "right_position": {"type": "integer", "minimum": 0},
    }
)
SELECTION = obj(
    {
        "left_finding_keys": NONEMPTY,
        "right_finding_keys": NONEMPTY,
        "conflict": {"oneOf": [CONFLICT, NULL]},
        "rationale": TEXT,
    }
)
MODEL = obj(
    {
        "id": TEXT,
        "version": TEXT,
        "method": TEXT,
        "rationale": TEXT,
        "formal_model": obj(
            {"object_id": TEXT, "parameter_id": TEXT, "situations": NONEMPTY, "domain": DOMAIN}
        ),
        "contexts": array(obj({"id": TEXT, "situations": NONEMPTY}), 1),
        "relations": array(
            obj(
                {
                    "left": TEXT,
                    "right": TEXT,
                    "relation": {"enum": ["overlap", "disjoint", "unknown"]},
                }
            )
        ),
    }
)
ATOM = obj(
    {
        "id": TEXT,
        "object_id": TEXT,
        "parameter_id": TEXT,
        "context_id": {"oneOf": [TEXT, NULL]},
        "values": {"oneOf": [VALUES, NULL]},
        "missing_fields": {**array({"enum": ["conditions", "values"]}), "uniqueItems": True},
        "sources": array(
            obj({"finding_key": TEXT, "finding_ref": REF, "evidence_keys": NONEMPTY}), 1
        ),
    }
)
COMPLETION = obj({"conditions": NONEMPTY, "values": VALUES})
OMEGA = obj(
    {
        "method": TEXT,
        "justification": TEXT,
        "declared_complete": {"type": "boolean"},
        "variants": array(obj({"left": COMPLETION, "right": COMPLETION})),
    }
)
FORMALIZATION = obj(
    {
        "version": TEXT,
        "decomposition_rationale": TEXT,
        "model": MODEL,
        "atoms": array(ATOM, 1),
        "pair": obj({"left_atom_id": TEXT, "right_atom_id": TEXT, "rationale": TEXT}),
        "omissions": array(obj({"finding_key": TEXT, "reason": TEXT})),
        "omega": {"oneOf": [OMEGA, NULL]},
    }
)
SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$defs": {"selection": SELECTION, "formalization": FORMALIZATION},
    **obj(
        {
            "format_version": {"const": "qwen-formal-proposal/1"},
            "case_id": TEXT,
            "input_sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
            "decision": {"enum": ["propose", "abstain"]},
            "selection": {"oneOf": [{"$ref": "#/$defs/selection"}, NULL]},
            "formalization": {"oneOf": [{"$ref": "#/$defs/formalization"}, NULL]},
            "questions": STRINGS,
            "limitations": NONEMPTY,
        }
    ),
    "allOf": [
        {
            "if": {"properties": {"decision": {"const": "propose"}}},
            "then": {
                "properties": {"selection": {"type": "object"}, "formalization": {"type": "object"}}
            },
            "else": {
                "properties": {"selection": NULL, "formalization": NULL, "questions": NONEMPTY}
            },
        }
    ],
}


if __name__ == "__main__":
    Path(__file__).with_name("response.schema.json").write_text(
        json.dumps(SCHEMA, indent=2) + "\n", encoding="utf-8"
    )
