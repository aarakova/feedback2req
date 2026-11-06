"""Offline, bounded replay of raw proposals. No model, HTTP or production imports."""

import json
from copy import deepcopy
from itertools import islice
from pathlib import Path

from ai.formal_expectations import Limits
from ai.formal_expectations_bridge import Verification, check_pair, fingerprint

from .dataset import dataset_hash, get_case, load_cases
from .prompt import SYSTEM_PROMPT
from .protocol import (
    ExperimentError,
    canonical,
    classify_preparation,
    input_hash,
    parse,
    prepare_response,
    response_from_reference,
    sha,
)
from .review import CRITERIA, template, validate_review, verdict, verifier

SYNTHETIC_MODEL = {
    "name": "synthetic-control",
    "revision": "registered-controls-v1",
    "runtime": "none",
    "parameters": {"seed": 0},
    "prompt_version": "qwen-z3/1",
}


def binding(case, raw, model, attempt, packet):
    return {
        "dataset_sha256": dataset_hash(),
        "case_id": case["id"],
        "input_sha256": input_hash(case),
        "raw_sha256": sha(raw),
        "model_sha256": fingerprint(model),
        "prompt_sha256": sha(SYSTEM_PROMPT.encode("utf-8")),
        "attempt": attempt,
        "reference_sha256": fingerprint(case["reference"]),
        "packet_sha256": fingerprint(packet) if packet is not None else None,
    }


def _synthetic_verifier(case_id, raw, model, attempt, packet):
    """Exact, registered engineering reference only; not an arbitrary packet factory."""
    case = get_case(case_id)
    expected_raw = canonical(response_from_reference(case))
    if (
        fingerprint(model) != fingerprint(SYNTHETIC_MODEL)
        or raw != expected_raw
        or attempt != 1
        or case["expected_formal_class"] is None
    ):
        return None
    _, _, prepared = prepare_response(case, expected_raw, SYNTHETIC_MODEL)
    if prepared is None or prepared.status != "prepared" or packet != prepared.packet:
        return None
    saved = deepcopy(prepared.packet)

    def verify(candidate):
        if candidate != saved:
            raise ExperimentError("review_error", "registered_snapshot_changed")
        return Verification(
            fingerprint(saved),
            "registered-synthetic-control-v1",
            "Exact registered engineering reference; not semantic gold or a human approval.",
            True,
            True,
            True,
            True,
            True,
        )

    return verify


def compare_fields(candidate, reference, prefix=""):
    """Mechanical differences only. Equivalent semantic alternatives require review."""
    if type(candidate) is dict and type(reference) is dict:
        paths = []
        for key in sorted(set(candidate) | set(reference)):
            path = prefix + "/" + key
            if key not in candidate or key not in reference:
                paths.append(path)
            else:
                paths.extend(compare_fields(candidate[key], reference[key], path))
        return paths[:100]
    return [] if candidate == reference else [prefix or "/"]


def evaluate(case, raw, model, *, attempt=1, review=None, synthetic=False, limits=None):
    """Return a report row, pending review template and prepared packet separately."""
    packet, prepared, converted, value = None, None, None, None
    row = {
        "case_id": case["id"],
        "attempt": attempt,
        "raw_sha256": sha(raw),
        "status": None,
        "diagnostic": None,
        "review_diagnostic": None,
        "formal_result": None,
        "solver": None,
        "review_state": "not_available",
        "expected_reference_class": case["expected_formal_class"],
        "reference_status": case["reference_status"],
        "reference_difference_paths": None,
        "semantic_accuracy": None,
        "model_criteria": None,
        "expert_comparison": None,
    }
    try:
        value, converted, prepared = prepare_response(case, raw, model)
        if value["decision"] == "abstain":
            row["status"] = "model_abstained"
        else:
            packet = prepared.packet
            row["status"] = (
                "review_required"
                if prepared.status == "prepared"
                else classify_preparation(prepared)
            )
            row["diagnostic"] = prepared.diagnostic
            if case["reference"] is not None:
                expected = response_from_reference(case)
                row["reference_difference_paths"] = compare_fields(
                    value["formalization"], expected["formalization"]
                )
    except ExperimentError as error:
        row.update(
            status=error.category, diagnostic={"category": error.category, "rule": error.rule}
        )
    bound = binding(case, raw, model, attempt, packet)
    form = template(bound, case)
    row["binding"] = bound
    callback = None
    if review is not None:
        try:
            checked_review = validate_review(review, bound)
            row["applied_review_sha256"] = fingerprint(checked_review)
            row["review_state"] = verdict(checked_review)
            row["model_criteria"] = deepcopy(checked_review["criteria"])
            row["expert_comparison"] = deepcopy(checked_review["comparison"])
            if prepared is not None and prepared.status == "prepared":
                row["status"] = row["review_state"]
                if row["review_state"] == "approved":
                    callback = verifier(packet, checked_review)
        except ExperimentError as error:
            row["review_diagnostic"] = {"category": error.category, "rule": error.rule}
            if row["status"] == "review_required":
                row.update(status="review_error", diagnostic=row["review_diagnostic"])
    elif synthetic and prepared is not None and prepared.status == "prepared":
        callback = _synthetic_verifier(case["id"], raw, model, attempt, packet)
        if callback is not None:
            row["review_state"] = "registered_synthetic_control_not_human_review"
    if callback is not None:
        result = check_pair(converted, verify=callback, limits=limits or Limits())
        row["formal_result"], row["solver"] = result.formal_result, result.solver
        row["diagnostic"] = result.diagnostic or (result.formal_result or {}).get("diagnostic")
        row["status"] = (
            "formal_conclusion"
            if result.status == "checked"
            else "z3_technical_error"
            if result.status == "formal_failure"
            else "verification_failed"
        )
    return row, form, packet


def summarize(rows):
    counts = {}
    formal_classes = dict.fromkeys(("D", "K", "S", "U"), 0)
    criteria = {key: {} for key in CRITERIA}
    comparisons = {
        key: {"true": 0, "false": 0, "unreviewed": 0}
        for key in ("false_K", "false_D", "missed_conflict")
    }
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
        relation = (row["formal_result"] or {}).get("classification")
        if relation in formal_classes:
            formal_classes[relation] += 1
        for key in CRITERIA:
            state = (row["model_criteria"] or {}).get(key, {}).get("verdict", "unreviewed")
            criteria[key][state] = criteria[key].get(state, 0) + 1
        for key in comparisons:
            value = (row["expert_comparison"] or {}).get(key)
            comparisons[key]["unreviewed" if value is None else "true" if value else "false"] += 1
    clarification = sum(
        r["status"]
        in (
            "model_abstained",
            "incomplete_omega",
            "unconfirmed_omega",
            "review_required",
            "formalization_required",
        )
        for r in rows
    )
    return {
        "records": len(rows),
        "statuses": counts,
        "formal_classes": formal_classes,
        "model_criteria": criteria,
        "joint_expert_comparisons": comparisons,
        "semantic_accuracy": None,
        "semantic_accuracy_status": "not_established_preliminary_references",
        "pairwise_only": True,
        "requires_clarification_count": clarification,
        "requires_clarification_fraction": clarification / len(rows) if rows else None,
        "clarification_denominator": len(rows),
    }


def write(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def _read(path, limit=1_048_576):
    with path.open("rb") as stream:
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise ExperimentError("input_error", "file_size_limit")
    return raw


def _confined(root, relative):
    if type(relative) is not str or Path(relative).is_absolute():
        raise ExperimentError("input_error", "relative_response_path_required")
    target = (root / relative).resolve(strict=True)
    if not target.is_relative_to(root.resolve()) or not target.is_file():
        raise ExperimentError("input_error", "response_path_escape")
    return target


def _manifest(value):
    required = {"experiment_version", "mode", "dataset_sha256", "model", "records"}
    if (
        type(value) is not dict
        or set(value) != required
        or value["experiment_version"] != "1"
        or value["mode"] not in ("synthetic_proposals", "saved_model_proposals")
        or value["dataset_sha256"] != dataset_hash()
    ):
        raise ExperimentError("input_error", "manifest_binding")
    model = value["model"]
    if type(model) is not dict or set(model) != {
        "name",
        "revision",
        "runtime",
        "parameters",
        "prompt_version",
    }:
        raise ExperimentError("input_error", "model_metadata")
    if any(
        type(model[k]) is not str or not model[k].strip() or len(model[k]) > 256
        for k in ("name", "runtime", "prompt_version")
    ) or (
        model["revision"] is not None
        and (
            type(model["revision"]) is not str
            or not model["revision"].strip()
            or len(model["revision"]) > 256
        )
    ):
        raise ExperimentError("input_error", "model_identity")
    parameters = model["parameters"]
    if (
        type(parameters) is not dict
        or set(parameters)
        - {"seed", "temperature", "top_p", "top_k", "num_ctx", "num_predict", "think"}
        or any(type(v) not in (str, int, float, bool, type(None)) for v in parameters.values())
    ):
        raise ExperimentError("input_error", "model_parameters")
    if value["mode"] == "synthetic_proposals" and fingerprint(model) != fingerprint(
        SYNTHETIC_MODEL
    ):
        raise ExperimentError("input_error", "synthetic_identity")
    if type(value["records"]) is not list or not 1 <= len(value["records"]) <= 256:
        raise ExperimentError("input_error", "record_limit")
    seen = set()
    for record in value["records"]:
        if (
            type(record) is not dict
            or set(record) != {"case_id", "attempt", "response_file", "response_sha256"}
            or type(record["attempt"]) is not int
            or not 1 <= record["attempt"] <= 1_000_000
        ):
            raise ExperimentError("input_error", "record_shape")
        if type(record["case_id"]) is not str or (record["case_id"], record["attempt"]) in seen:
            raise ExperimentError("input_error", "duplicate_or_invalid_attempt")
        try:
            get_case(record["case_id"])
        except ValueError:
            raise ExperimentError("input_error", "unknown_case") from None
        seen.add((record["case_id"], record["attempt"]))
    return value


def replay(manifest_path, output, *, reviews_path=None):
    manifest_path, output = Path(manifest_path), Path(output)
    manifest_raw = _read(manifest_path)
    manifest = _manifest(parse(manifest_raw))
    reviews_raw = _read(Path(reviews_path)) if reviews_path is not None else None
    reviews = parse(reviews_raw) if reviews_raw is not None else {"reviews": []}
    if (
        type(reviews) is not dict
        or set(reviews) != {"reviews"}
        or type(reviews["reviews"]) is not list
    ):
        raise ExperimentError("review_error", "review_registry_shape")
    indexed_reviews = {}
    for review in reviews["reviews"]:
        try:
            key = (review["binding"]["case_id"], review["binding"]["attempt"])
            if key in indexed_reviews:
                raise ValueError
            indexed_reviews[key] = review
        except (KeyError, TypeError, ValueError):
            raise ExperimentError("review_error", "duplicate_or_invalid_review") from None
    requested = {(r["case_id"], r["attempt"]) for r in manifest["records"]}
    if set(indexed_reviews) - requested:
        raise ExperimentError("review_error", "review_outside_manifest")
    inputs = []
    for record in manifest["records"]:
        raw = _read(_confined(manifest_path.parent, record["response_file"]))
        if sha(raw) != record["response_sha256"]:
            raise ExperimentError("input_error", "raw_response_hash_mismatch")
        inputs.append((record, raw))
    output.mkdir(parents=True, exist_ok=False)
    for directory in ("raw", "reviews", "packets"):
        (output / directory).mkdir()
    rows, forms = [], []
    for index, (record, raw) in enumerate(inputs):
        case = get_case(record["case_id"])
        row, form, packet = evaluate(
            case,
            raw,
            manifest["model"],
            attempt=record["attempt"],
            review=indexed_reviews.get((case["id"], record["attempt"])),
            synthetic=manifest["mode"] == "synthetic_proposals",
        )
        (output / "raw" / f"{index:03}.bin").write_bytes(raw)
        if packet is not None:
            write(output / "packets" / f"{index:03}.json", packet)
        rows.append(row)
        forms.append(form)
    report = {
        "experiment_version": "1",
        "mode": manifest["mode"],
        "dataset_sha256": dataset_hash(),
        "manifest_sha256": sha(manifest_raw),
        "model": manifest["model"],
        "review_registry_sha256": sha(reviews_raw) if reviews_raw is not None else None,
        "inference_performed_by_this_tool": False,
        "base_commit": "9f3a1a0b440535ae1513e2bd64a7c9d1c62d58ee",
        "summary": summarize(rows),
        "records": rows,
    }
    write(output / "report.json", report)
    write(output / "reviews.json", {"reviews": forms})
    write(output / "manifest.json", manifest)
    write(
        output / "references.json",
        {"semantic_gold": False, "cases": [get_case(r["case_id"]) for r in manifest["records"]]},
    )
    (output / "source-manifest.bin").write_bytes(manifest_raw)
    if reviews_raw is not None:
        (output / "applied-reviews.bin").write_bytes(reviews_raw)
    return report


def generate_synthetic(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    records = []
    for index, case in enumerate(load_cases()):
        raw = canonical(response_from_reference(case))
        name = f"{index:03}.json"
        (output / name).write_bytes(raw)
        records.append(
            {
                "case_id": case["id"],
                "attempt": 1,
                "response_file": name,
                "response_sha256": sha(raw),
            }
        )
    manifest = {
        "experiment_version": "1",
        "mode": "synthetic_proposals",
        "dataset_sha256": dataset_hash(),
        "model": deepcopy(SYNTHETIC_MODEL),
        "records": records,
    }
    write(output / "manifest.json", manifest)
    return manifest


def collect(responses, model_path, output, *, case_ids, attempt=1):
    """Package received content bytes without rewriting them or doing inference."""
    selected = list(islice(case_ids, 257))
    if not 1 <= len(selected) <= 256:
        raise ExperimentError("input_error", "record_limit")
    if type(attempt) is not int or not 1 <= attempt <= 1_000_000:
        raise ExperimentError("input_error", "record_shape")
    seen = set()
    for case_id in selected:
        if type(case_id) is not str or case_id in seen:
            raise ExperimentError("input_error", "duplicate_or_invalid_attempt")
        try:
            get_case(case_id)
        except ValueError:
            raise ExperimentError("input_error", "unknown_case") from None
        seen.add(case_id)
    responses, output = Path(responses), Path(output)
    model_raw = _read(Path(model_path))
    model = parse(model_raw)
    records, saved = [], []
    for index, case_id in enumerate(selected):
        case = get_case(case_id)
        raw = _read(_confined(responses, case["id"] + ".json"))
        filename = f"{index:03}.bin"
        records.append(
            {
                "case_id": case["id"],
                "attempt": attempt,
                "response_file": filename,
                "response_sha256": sha(raw),
            }
        )
        saved.append((filename, raw))
    manifest = _manifest(
        {
            "experiment_version": "1",
            "mode": "saved_model_proposals",
            "dataset_sha256": dataset_hash(),
            "model": model,
            "records": records,
        }
    )
    output.mkdir(parents=True, exist_ok=False)
    for filename, raw in saved:
        (output / filename).write_bytes(raw)
    write(output / "manifest.json", manifest)
    (output / "source-model.bin").write_bytes(model_raw)
    return manifest
