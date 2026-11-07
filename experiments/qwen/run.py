"""Opt-in real local inference. Tests inject transport; CLI never replays fixtures."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import multiprocessing
import platform
import sys
import tempfile
import time
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path

from ai.group_findings.validation import (
    GroupingError,
    contracts,
    decode,
    validate_response,
)

from .adapter import ADAPTER_VERSION, ExperimentalOllama, config_check, sha
from .dataset import ROOT, load_cases
from .profiles import prompt_profile


def write(path, value):
    with Path(path).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def execute(cfg, request, *, transport=None):
    """One measured attempt; preserves received bytes even on validation failure."""
    provider = ExperimentalOllama(cfg, enabled=True, transport=transport)
    started = time.monotonic()
    result = {
        "raw": None,
        "content": None,
        "schema": "not_run",
        "application": "not_run",
        "error": None,
        "metrics": {},
        "candidate": None,
        "provider_completed": False,
        "started_at": datetime.now(UTC).isoformat(),
    }
    try:
        result["content"] = provider.group(request)
        result["provider_completed"] = True
        value = decode(result["content"])
        if next(contracts()["group_findings.response"].iter_errors(value), None):
            result["schema"] = "failed"
            raise GroupingError("invalid_response", "schema")
        result["schema"] = "passed"
        result["application"] = "failed"
        result["candidate"] = validate_response(request, value)
        result["application"] = "passed"
    except GroupingError as error:
        result["error"] = {"code": error.code, "rule": error.rule}
        if error.rule.startswith("json_"):
            result["schema"] = "failed_json_decode"
    except Exception:  # noqa: BLE001 -- never expose source/model text in exceptions.
        result["error"] = {"code": "provider_error", "rule": "unexpected_failure"}
    result.update(
        raw=provider.raw,
        content=provider.content,
        request_attempted=provider.request_attempted,
        metrics=provider.metrics,
        duration_ms=round((time.monotonic() - started) * 1000, 3),
    )
    return result


def child(cfg, request, sender):
    try:
        sender.send(execute(cfg, request))
    finally:
        sender.close()


def identity_child(cfg, sender):
    try:
        try:
            sender.send({"identity": ExperimentalOllama(cfg, enabled=True).identity()})
        except GroupingError as error:
            sender.send({"error": {"code": error.code, "rule": error.rule}})
        except Exception:  # noqa: BLE001 -- child returns only safe technical codes.
            sender.send(
                {"error": {"code": "provider_error", "rule": "identity_failed"}}
            )
    finally:
        sender.close()


class ResultFile:
    """Private child result file avoids unbounded blocking inside Pipe.recv()."""

    def __init__(self, path):
        self.path = path

    def send(self, result):
        result = dict(result)
        raw = result.pop("raw", None)
        result["raw_base64"] = (
            base64.b64encode(raw).decode("ascii") if raw is not None else None
        )
        with Path(self.path).open("x", encoding="utf-8") as stream:
            json.dump(result, stream, ensure_ascii=True, allow_nan=False)

    def close(self):
        pass


def bounded_job(target, args, timeout):
    # A socket timeout alone is not a wall-clock deadline (slow chunked responses).
    context = multiprocessing.get_context("spawn")
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="qwen-result-") as folder:
        path = Path(folder) / "result.json"
        process = context.Process(target=target, args=(*args, ResultFile(path)))
        process.start()
        try:
            process.join(timeout=max(0, timeout - (time.monotonic() - started)))
            if process.is_alive():
                error = {"code": "timeout", "rule": "wall_deadline"}
            else:
                error = {"code": "provider_error", "rule": "child_failed"}
            if not process.is_alive() and process.exitcode == 0 and path.is_file():
                try:
                    with path.open("rb") as stream:
                        data = stream.read(16 * 1048576 + 1)
                    if len(data) > 16 * 1048576:
                        raise ValueError
                    result = json.loads(data)
                    encoded = result.pop("raw_base64", None)
                    result["raw"] = (
                        base64.b64decode(encoded, validate=True)
                        if encoded is not None
                        else None
                    )
                    result["duration_ms"] = round(
                        (time.monotonic() - started) * 1000, 3
                    )
                    return result
                except (OSError, ValueError, KeyError, TypeError):
                    pass
            return {
                "raw": None,
                "content": None,
                "candidate": None,
                "schema": "not_run",
                "application": "not_run",
                "metrics": {},
                "provider_completed": False,
                "request_attempted": None,
                "duration_ms": round((time.monotonic() - started) * 1000, 3),
                "error": error,
            }
        finally:
            if process.is_alive():
                process.terminate()
                process.join(timeout=2)
            if process.is_alive():
                process.kill()
                process.join(timeout=2)
            if process.is_alive():
                raise GroupingError("provider_error", "child_stop_failed")


def bounded_execute(cfg, request, timeout=None):
    return bounded_job(child, (cfg, request), timeout or cfg["timeout_seconds"])


def bounded_identity(cfg):
    result = bounded_job(identity_child, (cfg,), cfg["timeout_seconds"])
    if result.get("error"):
        raise GroupingError(result["error"]["code"], result["error"]["rule"])
    return result["identity"]


def output_path(value):
    path = Path(value).resolve()
    # Reports/weights cannot accidentally become tracked artifacts or overwrite code.
    allowed = (ROOT / ".local/qwen-runs").resolve()
    if not path.is_relative_to(allowed) or path == allowed:
        raise GroupingError("provider_error", "output_must_be_local_qwen_runs_child")
    return path


def run(cfg, lock, output, selected, *, allowed=False, synthetic_only=False):
    if not allowed or not synthetic_only:
        raise GroupingError(
            "provider_error", "explicit_local_synthetic_opt_in_required"
        )
    config_check(cfg)
    profile_name, prompt_version, system_prompt = prompt_profile(cfg)
    dataset, cases, applicability = load_cases()
    inventory = cases
    if selected:
        selected = set(selected)
        if not selected <= {case["id"] for case in cases}:
            raise GroupingError("invalid_request", "unknown_case")
        cases = [case for case in cases if case["id"] in selected]
    started = time.monotonic()
    if bounded_identity(cfg) != lock:
        raise GroupingError("provider_error", "lock_mismatch")
    output = output_path(output)
    output.mkdir(parents=True, exist_ok=False)
    (output / "responses").mkdir()
    records, reviews, legacy = [], [], []
    metadata = {
        "mode": "real_local_inference",
        "synthetic_data": True,
        "created_at": datetime.now(UTC).isoformat(),
        "runtime": lock,
        "configuration": cfg,
        "wall_deadline_includes_child_startup": True,
        "adapter_version": ADAPTER_VERSION,
        "prompt_profile": profile_name,
        "prompt_version": prompt_version,
        "prompt_sha256": sha(system_prompt),
        "python": sys.version,
        "dependencies": {name: version(name) for name in ("jsonschema", "referencing")},
        "platform": platform.platform(),
        "dataset_sha256": sha(inventory),
        "source_dataset_sha256": dataset.sha256,
        "source_dataset_version": dataset.manifest["dataset_version"],
        "annotation_version": dataset.manifest["annotation_version"],
        "annotation_status": "preliminary",
        "semantic_quality": "not_evaluated",
        "schema_sha256": {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (ROOT / "docs/contracts/ai/v1").glob("*.json")
        },
        "code_sha256": {
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for folder in (
                ROOT / "experiments/qwen",
                ROOT / "ai/group_findings",
                ROOT / "evals/ai",
            )
            for p in folder.glob("*.py")
        },
        "applicability": applicability,
        "scheduled": [c["id"] for c in cases],
        "resource_measurements": {
            "server_peak_rss_bytes": None,
            "server_peak_vram_bytes": None,
            "server_cpu_seconds": None,
            "reason": "Not instrumented; Ollama durations/token counts are not RAM/VRAM measurements. Client watchdog does not guarantee server cancellation.",
        },
    }
    write(output / "metadata.json", metadata)
    # Persist exact requests and preliminary review focus for every scheduled case.
    write(output / "dataset.json", cases)
    for case in cases:
        remaining = cfg["run_timeout_seconds"] - (time.monotonic() - started)
        if remaining <= 0:
            break
        dispatched_at = datetime.now(UTC).isoformat()
        result = bounded_execute(
            cfg, case["request"], min(cfg["timeout_seconds"], remaining)
        )
        envelope_path = "responses/" + case["id"] + ".envelope.bin"
        response_path = "responses/" + case["id"] + ".json"
        if result["raw"] is not None:
            with (output / envelope_path).open("xb") as stream:
                stream.write(result["raw"])
        if result["content"] is not None:
            with (output / response_path).open("xb") as stream:
                stream.write(result["content"].encode("utf-8", errors="surrogatepass"))
        record = {
            "id": case["id"],
            "request_sha256": case["request_sha256"],
            "duration_ms": result["duration_ms"],
            "started_at": result.get("started_at"),
            "dispatched_at": dispatched_at,
            "ollama_metrics": result["metrics"],
            "schema": result["schema"],
            "application": result["application"],
            "error": result["error"],
            "provider_completed": result["provider_completed"],
            "request_attempted": result["request_attempted"],
            "relationship": case["relationship"],
            "envelope_file": envelope_path if result["raw"] is not None else None,
            "response_file": response_path if result["content"] is not None else None,
            "response_sha256": hashlib.sha256(
                result["content"].encode("utf-8", errors="surrogatepass")
            ).hexdigest()
            if result["content"] is not None
            else None,
        }
        records.append(record)
        # Checkpoint after each call; an interrupted run retains completed attempts.
        write(output / (case["id"] + ".diagnostics.json"), record)
        reviews.append(
            {
                "id": case["id"],
                "request_sha256": case["request_sha256"],
                "response_sha256": record["response_sha256"],
                "status": "pending" if result["error"] is None else "technical_failure",
                "annotation": case["annotation"],
                "relationship": case["relationship"],
                "reviewer": None,
                "criteria": {
                    name: {"verdict": "pending", "rationale": None}
                    for name in (
                        "meaning",
                        "similarity",
                        "opposite_positions",
                        "conditions",
                        "uncertainty",
                        "direct_inferred",
                        "unsupported_additions",
                        "evidence",
                        "coverage",
                        "injection",
                        "metamorphic_consistency",
                    )
                },
            }
        )
        if case["source"]:
            from runner import digest

            row = {
                "case_id": case["source"][0],
                "example_id": case["source"][1],
                "attempt": 1,
                "request_sha256": digest(case["request"]),
                "duration_ms": result["duration_ms"],
            }
            if result["provider_completed"]:
                row.update(outcome="returned", response_file=response_path)
            else:
                row.update(
                    outcome="failed",
                    error_code=(result["error"] or {}).get("code", "provider_error"),
                )
                if row["error_code"] not in {
                    "timeout",
                    "provider_error",
                    "invalid_response",
                    "cancelled",
                }:
                    row["error_code"] = "provider_error"
            legacy.append(row)
        print(
            json.dumps(
                {
                    "case": case["id"],
                    "schema": result["schema"],
                    "application": result["application"],
                    "duration_ms": result["duration_ms"],
                }
            ),
            flush=True,
        )
        if result["error"] and result["error"]["code"] == "timeout":
            # Do not queue another load while server cancellation is uncertain.
            break
    write(
        output / "diagnostics.json",
        {
            "mode": "real_local_inference",
            "records": records,
            "attempted": len(records),
            "scheduled": len(cases),
            "technical_errors": sum(r["error"] is not None for r in records),
            "attempt_failure_rate": sum(r["error"] is not None for r in records)
            / len(records)
            if records
            else None,
            "confirmed_http_attempts": sum(
                r["request_attempted"] is True for r in records
            ),
            "unknown_http_attempts": sum(
                r["request_attempted"] is None for r in records
            ),
            "elapsed_ms": round((time.monotonic() - started) * 1000, 3),
            "not_attempted": [c["id"] for c in cases[len(records) :]],
            "semantic_quality": "not_evaluated",
        },
    )
    write(
        output / "expert-review.json",
        {
            "annotation_status": "preliminary",
            "dataset_sha256": sha(inventory),
            "instructions": "Use evals/ai/REVIEW.md. Do not treat fixtures as unique gold. Compare partitions and conflict positions by finding keys, not local_id or group order. Record evidence for every verdict; no final quality score.",
            "records": reviews,
        },
    )
    if legacy:
        from runner import evaluate, write_report

        saved = {
            "format_version": "1.0",
            "dataset_version": dataset.manifest["dataset_version"],
            "annotation_version": dataset.manifest["annotation_version"],
            "dataset_sha256": dataset.sha256,
            "mode": "saved_model_responses",
            "model": {"name": cfg["model"], "revision": lock["digest"]},
            "configuration": {
                "prompt_version": prompt_version,
                "adapter_version": ADAPTER_VERSION,
                "generation_settings": {
                    "temperature": cfg["options"]["temperature"],
                    "top_p": cfg["options"]["top_p"],
                    "max_output_tokens": cfg["options"]["num_predict"],
                },
                "seed": cfg["options"]["seed"],
            },
            "records": legacy,
        }
        write(output / "saved-model-responses.json", saved)
        report, template = evaluate(dataset, output / "saved-model-responses.json")
        write_report(report, template, output / "source-evaluation")
    return int(len(records) != len(cases) or any(row["error"] for row in records))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["inventory", "lock", "run"])
    parser.add_argument(
        "--config", default=str(Path(__file__).with_name("qwen3-4b.json"))
    )
    parser.add_argument("--lock")
    parser.add_argument("--output")
    parser.add_argument("--case", action="append", default=[])
    parser.add_argument("--allow-local-inference", action="store_true")
    parser.add_argument("--synthetic-only", action="store_true")
    args = parser.parse_args()
    try:
        cfg = config_check(decode(Path(args.config).read_bytes(), side="request"))
        if args.command == "inventory":
            dataset, cases, applicable = load_cases()
            print(
                json.dumps(
                    {
                        "mode": "inventory_no_inference",
                        "cases": [c["id"] for c in cases],
                        "applicability": applicable,
                        "dataset_sha256": sha(cases),
                        "source_dataset_sha256": dataset.sha256,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 0
        if not args.allow_local_inference or not args.synthetic_only:
            raise GroupingError(
                "provider_error", "explicit_local_synthetic_opt_in_required"
            )
        if args.command == "lock":
            output = output_path(args.output)
            output.parent.mkdir(parents=True, exist_ok=True)
            write(output, bounded_identity(cfg))
            return 0
        lock = decode(Path(args.lock).read_bytes())
        return run(cfg, lock, args.output, args.case, allowed=True, synthetic_only=True)
    except GroupingError as error:
        print(json.dumps({"code": error.code, "rule": error.rule}), file=sys.stderr)
        return 2
    except Exception:  # noqa: BLE001 -- never print untrusted exceptions.
        # Never echo server content, material text, path or exception traceback.
        print(
            "qwen_experiment_failed; inspect local diagnostics if created",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
