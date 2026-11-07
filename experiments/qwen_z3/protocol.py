"""Closed experimental grammar and lossless conversion to the existing bridge."""

import hashlib
import json
from copy import deepcopy
from pathlib import Path

from ai.formal_expectations_bridge import fingerprint, prepare
from ai.group_findings.validation import decode
from jsonschema import Draft202012Validator

VERSION = "qwen-formal-proposal/1"
SCHEMA_PATH = Path(__file__).with_name("response.schema.json")


class ExperimentError(Exception):
    def __init__(self, category, rule):
        self.category, self.rule = category, rule
        super().__init__(category + ":" + rule)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(value) -> bytes:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode(
        "ascii"
    )


def parse(raw: bytes | str):
    try:
        value = decode(raw)
        pending, count = [(value, 0)], 0
        while pending:
            item, depth = pending.pop()
            count += 1
            if count > 50_000 or depth > 24:
                raise ValueError("JSON complexity")
            if type(item) is dict:
                pending.extend((v, depth + 1) for v in item.values())
            elif type(item) is list:
                pending.extend((v, depth + 1) for v in item)
        return value
    except Exception:
        raise ExperimentError("syntax_error", "invalid_bounded_json") from None


def validate_response(raw):
    value = parse(raw)
    schema = json.loads(SCHEMA_PATH.read_text("utf-8"))
    if next(Draft202012Validator(schema).iter_errors(value), None) is not None:
        raise ExperimentError("structure_error", "proposal_schema")
    return value


def input_view(case):
    data = case["input"]
    return {
        "case_id": case["id"],
        "grouping_request": deepcopy(data["grouping_request"]),
        "grouping_response": deepcopy(data["grouping_response"]),
        "selection_scope": deepcopy(data["selection"]),
    }


def input_hash(case):
    return fingerprint(input_view(case))


def response_from_reference(case):
    """Engineering fixture proposal, never a real Qwen answer or semantic gold."""
    reference = deepcopy(case["reference"])
    if reference is None:
        return {
            "format_version": VERSION,
            "case_id": case["id"],
            "input_sha256": input_hash(case),
            "decision": "abstain",
            "selection": None,
            "formalization": None,
            "questions": [case["abstention_reason"]],
            "limitations": ["Synthetic control; no model inference."],
        }
    proposal = reference["proposal"]
    if proposal is None:
        return {
            "format_version": VERSION,
            "case_id": case["id"],
            "input_sha256": input_hash(case),
            "decision": "abstain",
            "selection": None,
            "formalization": None,
            "questions": [case["abstention_reason"]],
            "limitations": ["No supported reference."],
        }
    proposal.pop("origin")
    if proposal["omega"] is not None:
        proposal["omega"].pop("origin")
    return {
        "format_version": VERSION,
        "case_id": case["id"],
        "input_sha256": input_hash(case),
        "decision": "propose",
        "selection": reference["selection"],
        "formalization": proposal,
        "questions": [case["abstention_reason"]],
        "limitations": ["Synthetic proposal; review required."],
    }


def convert(case, value, model):
    if value["case_id"] != case["id"] or value["input_sha256"] != input_hash(case):
        raise ExperimentError("provenance_error", "case_snapshot_mismatch")
    if value["decision"] == "abstain":
        return None
    scope, selection = case["input"]["selection"], value["selection"]
    for field in ("left_finding_keys", "right_finding_keys"):
        if set(scope[field]) != set(selection[field]):
            raise ExperimentError("provenance_error", "incomplete_or_changed_selection")
    if scope["conflict"] != selection["conflict"]:
        raise ExperimentError("provenance_error", "changed_conflict_position")
    data = deepcopy(case["input"])
    data["selection"] = deepcopy(selection)
    proposal = deepcopy(value["formalization"])
    # Origin is assigned by the experiment, never accepted as a trust claim from text.
    origin = {
        "kind": "ai",
        "actor": model["name"],
        "method": "saved_proposal:" + (model["revision"] or "unknown"),
    }
    proposal["origin"] = deepcopy(origin)
    if proposal["omega"] is not None:
        proposal["omega"]["origin"] = deepcopy(origin)
    data["proposal"] = proposal
    return data


def classify_preparation(prepared):
    if prepared.status == "needs_refinements":
        return "incomplete_omega"
    if prepared.status == "needs_formalization":
        return "formalization_required"
    code = (prepared.diagnostic or {}).get("code")
    rule = (prepared.diagnostic or {}).get("rule", "")
    if code == "basis_unavailable" or any(
        v in rule
        for v in ("state_mismatch", "evidence", "position", "scope", "reference", "unaccounted")
    ):
        return "provenance_error"
    if code in ("timeout", "resource_limit", "internal_failure"):
        return "preparation_failure"
    return "formalization_error"


def prepare_response(case, raw, model):
    value = validate_response(raw)
    data = convert(case, value, model)
    return value, data, prepare(data) if data is not None else None
