#!/usr/bin/env python3
"""Offline dataset/replay management and content-free diagnostic reports."""

from __future__ import annotations

import hashlib
import json
import math
import platform
from collections import Counter
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path

from checks import (
    CATEGORIES,
    Contracts,
    InputError,
    check_request,
    check_response,
    strict_load,
)

HOME = Path(__file__).resolve().parent
DEFAULT_DATASET = HOME / "datasets/synthetic-ru-v1"
MANUAL_CRITERIA = (
    "semantic_support",
    "semantic_completeness",
    "absence_of_false_positives",
    "direct_vs_inferred",
    "uncertainty_and_conflicts",
    "severity_and_blocking",
    "robustness",
)
CRITERION_DEFINITIONS = {
    "semantic_support": "Существенные выводы поддержаны соответствующими доступными основаниями.",
    "semantic_completeness": "Ожидаемые смыслы сохранены в фактически рассмотренной области.",
    "absence_of_false_positives": "Нет выдуманных находок, доработок или необоснованных замечаний проверки.",
    "direct_vs_inferred": "Прямые высказывания отделены от интерпретации; участнику не приписано предложение модели.",
    "uncertainty_and_conflicts": "Неопределённость и конфликтующие позиции сохранены; вопросы обоснованы и адресны.",
    "severity_and_blocking": "Серьёзность, блокирующее действие, причины и область обоснованы; серьёзность не задаёт блокировку автоматически.",
    "robustness": "При сравнении с указанным базовым примером существенные смыслы и полномочия сохранены.",
}
VERDICTS = {"pending", "met", "not_met", "uncertain", "not_applicable"}


def digest(value):
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def file_digest(paths, root):
    return digest(
        [
            (p.relative_to(root).as_posix(), hashlib.sha256(p.read_bytes()).hexdigest())
            for p in sorted(paths)
        ]
    )


def local_file(root, name):
    if not isinstance(name, str):
        raise InputError("PATH-NOT-STRING")
    path = (root / name).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise InputError("PATH-OUTSIDE-INPUT-OR-MISSING")
    return path


class Dataset:
    def __init__(self, root=DEFAULT_DATASET):
        self.root = Path(root).resolve()
        self.manifest = strict_load(self.root / "manifest.json")
        self.contracts = Contracts()
        m = self.manifest
        if (
            not isinstance(m, dict)
            or m.get("synthetic") is not True
            or m.get("annotation_status") != "preliminary"
            or m.get("semantic_gold") is not False
        ):
            raise InputError("DATASET-STATUS")
        if (
            not isinstance(m.get("cases"), list)
            or len(m["cases"]) != 14
            or len(set(m["cases"])) != 14
        ):
            raise InputError("DATASET-CASE-INVENTORY")
        self.cases, self.examples = {}, {}
        raw_cases = []
        for filename in m["cases"]:
            case = strict_load(local_file(self.root, filename))
            raw_cases.append(case)
            if (
                not isinstance(case, dict)
                or case.get("id") not in {f"S{i:02}" for i in range(1, 15)}
                or case["id"] in self.cases
            ):
                raise InputError("CASE-ID")
            if case.get("synthetic") is not True or not case.get("version"):
                raise InputError("CASE-PROVENANCE")
            annotation = case.get("annotation", {})
            if annotation.get("status") != "preliminary" or annotation.get(
                "version"
            ) != m.get("annotation_version"):
                raise InputError("ANNOTATION-STATUS-OR-VERSION")
            for field in (
                "required_meanings",
                "allowed_alternatives",
                "forbidden_claims",
                "expert_questions",
            ):
                if not isinstance(annotation.get(field), list) or any(
                    not isinstance(t, str) or not t for t in annotation[field]
                ):
                    raise InputError("ANNOTATION-FIELDS")
            if (
                not annotation["required_meanings"]
                or not annotation["forbidden_claims"]
            ):
                raise InputError("ANNOTATION-EMPTY")
            trace = case.get("traceability", {})
            for field in ("requirements", "acceptance_criteria", "contract_rules"):
                if not isinstance(trace.get(field), list) or not trace[field]:
                    raise InputError("TRACEABILITY-MISSING")
            sources = {
                "requirements": (HOME.parents[1] / "docs/REQUIREMENTS.md").read_text(
                    encoding="utf-8"
                ),
                "acceptance_criteria": (
                    HOME.parents[1] / "docs/REQUIREMENTS.md"
                ).read_text(encoding="utf-8"),
                "contract_rules": (HOME.parents[1] / "docs/AI_CONTRACTS.md").read_text(
                    encoding="utf-8"
                ),
            }
            if any(
                any(identifier not in sources[field] for identifier in trace[field])
                for field in sources
            ):
                raise InputError("TRACEABILITY-UNKNOWN")
            self.cases[case["id"]] = case
            if not isinstance(case.get("examples"), list) or not case["examples"]:
                raise InputError("CASE-EXAMPLES-EMPTY")
            for example in case["examples"]:
                if example.get("fixture_role") not in {
                    "engineering_control",
                    "intentional_semantic_error",
                }:
                    raise InputError("FIXTURE-ROLE")
                claims = example.get("expert_claims", [])
                if not isinstance(claims, list) or any(
                    not isinstance(c, dict)
                    or not isinstance(c.get("id"), str)
                    or not c["id"]
                    or not isinstance(c.get("text"), str)
                    or not c["text"]
                    for c in claims
                ):
                    raise InputError("EXPERT-CLAIM-DEFINITIONS")
                if len({c["id"] for c in claims}) != len(claims):
                    raise InputError("EXPERT-CLAIM-IDS")
                identity = (case["id"], example["id"])
                if identity in self.examples:
                    raise InputError("EXAMPLE-ID-REPEATED")
                if not isinstance(example.get("id"), str) or not all(
                    c.isalnum() or c == "-" for c in example["id"]
                ):
                    raise InputError("EXAMPLE-ID")
                errors = check_request(
                    self.contracts, example["request"], example["trusted"]
                )
                errors += self.contracts.schema_errors(
                    example["request"]["operation"],
                    "response",
                    example["fixture_response"],
                )
                if errors:
                    raise InputError(
                        "DATASET-EXAMPLE-INVALID:"
                        + case["id"]
                        + "/"
                        + example["id"]
                        + ":"
                        + errors[0]["code"]
                    )
                self.examples[identity] = example
        for example in self.examples.values():
            relation = example.get("relationship")
            if relation and tuple(relation["of"].split("/")) not in self.examples:
                raise InputError("RELATIONSHIP-MISSING")
        self.sha256 = digest([m, raw_cases])


def validate_metadata(replay):
    if replay.get("format_version") != "1.0" or replay.get("mode") not in {
        "synthetic_fixture_replay",
        "saved_model_responses",
    }:
        raise InputError("REPLAY-FORMAT-OR-MODE")
    model = replay.get("model")
    if (
        not isinstance(model, dict)
        or set(model) != {"name", "revision"}
        or any(not isinstance(v, str) or not v for v in model.values())
    ):
        raise InputError("MODEL-METADATA")
    if (replay["mode"] == "synthetic_fixture_replay") != (model["name"] == "none"):
        raise InputError("MODEL-MODE-MISMATCH")
    config = replay.get("configuration")
    if not isinstance(config, dict) or set(config) != {
        "prompt_version",
        "adapter_version",
        "generation_settings",
        "seed",
    }:
        raise InputError("CONFIGURATION-METADATA")
    if any(
        not isinstance(config[field], str) or not config[field]
        for field in ("prompt_version", "adapter_version")
    ):
        raise InputError("CONFIGURATION-VERSIONS")
    if config["seed"] is not None and (type(config["seed"]) is not int):
        raise InputError("CONFIGURATION-SEED")
    settings = config["generation_settings"]
    allowed = {
        "temperature",
        "top_p",
        "max_output_tokens",
        "frequency_penalty",
        "presence_penalty",
        "reasoning_effort",
    }
    if not isinstance(settings, dict) or not settings.keys() <= allowed:
        raise InputError("CONFIGURATION-SETTINGS")
    if any(
        not isinstance(v, (str, bool, int, float))
        or (isinstance(v, float) and not math.isfinite(v))
        for v in settings.values()
    ):
        raise InputError("CONFIGURATION-VALUES")


def evaluate(dataset, replay_path, expert_path=None):
    replay_path = Path(replay_path)
    replay = strict_load(replay_path)
    if not isinstance(replay, dict):
        raise InputError("REPLAY-OBJECT")
    validate_metadata(replay)
    for field in ("dataset_version", "annotation_version"):
        if replay.get(field) != dataset.manifest[field]:
            raise InputError("REPLAY-VERSION-MISMATCH")
    if replay.get("dataset_sha256") != dataset.sha256:
        raise InputError("REPLAY-DATASET-MISMATCH")
    if not isinstance(replay.get("records"), list) or not replay["records"]:
        raise InputError("REPLAY-RECORDS-EMPTY")
    rows, seen, response_digests = [], set(), []
    for record in replay["records"]:
        if not isinstance(record, dict):
            raise InputError("REPLAY-RECORD")
        key = (record.get("case_id"), record.get("example_id"))
        if key not in dataset.examples:
            raise InputError("REPLAY-EXAMPLE-UNKNOWN")
        attempt = record.get("attempt", 1)
        if type(attempt) is not int or attempt < 1 or (*key, attempt) in seen:
            raise InputError("REPLAY-ATTEMPT")
        seen.add((*key, attempt))
        example = dataset.examples[key]
        req, trusted = example["request"], example["trusted"]
        if record.get("request_sha256") != digest(req):
            raise InputError("REPLAY-REQUEST-MISMATCH")
        diagnostics = check_request(dataset.contracts, req, trusted)
        facts = {}
        status = record.get("outcome")
        source = {"response", "response_file"} & record.keys()
        if status == "failed":
            if source or record.get("error_code") not in {
                "timeout",
                "provider_error",
                "invalid_response",
                "cancelled",
            }:
                raise InputError("TECHNICAL-RECORD")
            diagnostics.append(
                {
                    "category": "technical",
                    "code": "TECH-" + record["error_code"].upper(),
                    "side": "execution",
                    "path": "/",
                }
            )
            response_digests.append(None)
        elif status == "returned" and len(source) == 1 and "error_code" not in record:
            try:
                if "response_file" in record:
                    path = local_file(replay_path.parent, record["response_file"])
                    response_digests.append(
                        hashlib.sha256(path.read_bytes()).hexdigest()
                    )
                    resp = strict_load(path)
                else:
                    resp = record["response"]
                    response_digests.append(digest(resp))
            except InputError as error:
                if str(error).startswith("PATH-"):
                    raise
                diagnostics.append(
                    {
                        "category": "structure",
                        "code": "RESPONSE-" + str(error),
                        "side": "response",
                        "path": "/",
                    }
                )
            else:
                if not diagnostics:
                    more, facts = check_response(dataset.contracts, req, resp, trusted)
                    diagnostics += more
        else:
            raise InputError("REPLAY-OUTCOME")
        duration = record.get("duration_ms")
        if duration is not None and (
            type(duration) not in (float, int)
            or not math.isfinite(duration)
            or duration < 0
        ):
            raise InputError("REPLAY-DURATION")
        rows.append(
            {
                "case_id": key[0],
                "example_id": key[1],
                "attempt": attempt,
                "operation": req["operation"],
                "technical_outcome": status,
                "duration_ms": duration,
                "request_sha256": digest(req),
                "automatic": {
                    "status": "violations_found"
                    if diagnostics
                    else "no_violations_in_implemented_checks",
                    "diagnostics": diagnostics,
                    "facts": facts,
                },
                "expert": {"status": "pending", "annotation_status": "preliminary"},
                "relationship": example.get("relationship"),
                "reference_fixture_role": example["fixture_role"],
            }
        )
    replay_sha256 = digest([replay, response_digests])
    template = {
        "format_version": "1.0",
        "dataset_sha256": dataset.sha256,
        "replay_sha256": replay_sha256,
        "annotation_version": dataset.manifest["annotation_version"],
        "annotation_status": "preliminary",
        "reviewer": None,
        "criterion_definitions": CRITERION_DEFINITIONS,
        "instructions": "met — критерий выполнен; not_met — нарушен; uncertain — нельзя решить; not_applicable — неприменим. Для технического сбоя содержательные критерии не оцениваются. Сверяйтесь с REVIEW.md и реальным сохранённым ответом; инженерная фикстура не единственный эталон.",
        "records": [
            {
                "case_id": row["case_id"],
                "example_id": row["example_id"],
                "attempt": row["attempt"],
                "annotation": dataset.cases[row["case_id"]]["annotation"],
                "example_review_note": dataset.examples[
                    (row["case_id"], row["example_id"])
                ].get("review_note"),
                "relationship": row["relationship"],
                "reference_fixture_role": row["reference_fixture_role"],
                "coverage_notes": dataset.cases[row["case_id"]].get(
                    "coverage_notes", []
                ),
                "claim_reviews": [
                    {
                        "id": claim["id"],
                        "text": claim["text"],
                        "verdict": "pending",
                        "rationale": None,
                    }
                    for claim in dataset.examples[
                        (row["case_id"], row["example_id"])
                    ].get("expert_claims", [])
                ],
                "criteria": [
                    {"id": criterion, "verdict": "pending", "rationale": None}
                    for criterion in MANUAL_CRITERIA
                ],
            }
            for row in rows
        ],
    }
    if expert_path:
        apply_expert(rows, template, strict_load(expert_path))
    counts = {
        category: {
            "records_with_diagnostics": sum(
                any(d["category"] == category for d in r["automatic"]["diagnostics"])
                for r in rows
            ),
            "records_total": len(rows),
        }
        for category in CATEGORIES
    }
    expert_counts = {
        criterion: dict(
            Counter(
                next(
                    (
                        c["verdict"]
                        for c in row["expert"].get("criteria", [])
                        if c["id"] == criterion
                    ),
                    "pending",
                )
                for row in rows
            )
        )
        for criterion in MANUAL_CRITERIA
    }
    scheduled = {(r["case_id"], r["example_id"]) for r in rows}
    report = {
        "format_version": "1.0",
        "diagnostic_only": True,
        "final_model_quality_assessment": False,
        "created_at": datetime.now(UTC).isoformat(),
        "dataset": {
            "version": dataset.manifest["dataset_version"],
            "sha256": dataset.sha256,
            "annotation_version": dataset.manifest["annotation_version"],
            "annotation_status": "preliminary",
        },
        "execution": {
            "mode": replay["mode"],
            "model": replay["model"],
            "configuration": replay["configuration"],
            "replay_sha256": replay_sha256,
            "python": platform.python_version(),
            "jsonschema": version("jsonschema"),
            "referencing": version("referencing"),
            "schemas_sha256": file_digest(list(schema_files()), HOME.parents[1]),
            "tool_sha256": file_digest(
                list(HOME.glob("*.py")) + [HOME / "requirements.txt"], HOME
            ),
        },
        "summary": {
            "records": len(rows),
            "returned": sum(r["technical_outcome"] == "returned" for r in rows),
            "failed": sum(r["technical_outcome"] == "failed" for r in rows),
            "automatic_categories": counts,
            "expert_categories_preliminary": expert_counts,
            "expert_pending": sum(r["expert"]["status"] == "pending" for r in rows),
            "examples_scheduled": len(scheduled),
            "examples_available": len(dataset.examples),
            "examples_not_scheduled": len(set(dataset.examples) - scheduled),
        },
        "records": rows,
        "limitations": [
            "PRELIMINARY annotations; no final semantic quality score or model ranking.",
            "Coverage is declared, not proof of semantic reading.",
            "Trusted states are synthetic fixture facts, not database/permission/race checks.",
            "No ASR, application lifecycle, provider calls, or deletion implementation tested.",
            "Semantic support, completeness, false positives, uncertainty/conflicts and robustness require expert review.",
            "Engineering reference fixtures, including intentional_semantic_error, are not positive semantic gold.",
            "S06 has only conflicting positions: independent continuation during a semantic conflict is not covered; S10 covers a technical failure.",
        ],
    }
    return report, template


def schema_files():
    return (HOME.parents[1] / "docs/contracts/ai/v1").glob("*.schema.json")


def apply_expert(rows, template, reviews):
    if not isinstance(reviews, dict) or any(
        reviews.get(k) != template[k]
        for k in (
            "format_version",
            "dataset_sha256",
            "replay_sha256",
            "annotation_version",
            "annotation_status",
        )
    ):
        raise InputError("EXPERT-BINDING-MISMATCH")
    if not isinstance(reviews.get("reviewer"), str) or not reviews["reviewer"].strip():
        raise InputError("EXPERT-REVIEWER-MISSING")
    records = reviews.get("records")
    if not isinstance(records, list) or len(records) != len(rows):
        raise InputError("EXPERT-RECORD-INVENTORY")
    catalog = {}
    for record in records:
        key = (record.get("case_id"), record.get("example_id"), record.get("attempt"))
        if key in catalog:
            raise InputError("EXPERT-RECORD-REPEATED")
        catalog[key] = record
    templates = {
        (r["case_id"], r["example_id"], r["attempt"]): r for r in template["records"]
    }
    for row in rows:
        key = row["case_id"], row["example_id"], row["attempt"]
        if key not in catalog:
            raise InputError("EXPERT-RECORD-MISSING")
        criteria = catalog[key].get("criteria")
        if not isinstance(criteria, list) or Counter(
            c.get("id") for c in criteria
        ) != Counter(MANUAL_CRITERIA):
            raise InputError("EXPERT-CRITERIA")
        for criterion in criteria:
            if criterion.get("verdict") not in VERDICTS:
                raise InputError("EXPERT-VERDICT")
            if criterion["verdict"] != "pending" and (
                not isinstance(criterion.get("rationale"), str)
                or not criterion["rationale"].strip()
            ):
                raise InputError("EXPERT-RATIONALE-MISSING")
        claims = catalog[key].get("claim_reviews", [])
        expected_claims = templates[key]["claim_reviews"]
        if (
            not isinstance(claims, list)
            or any(not isinstance(c, dict) for c in claims)
            or Counter(c.get("id") for c in claims)
            != Counter(c["id"] for c in expected_claims)
        ):
            raise InputError("EXPERT-CLAIM-INVENTORY")
        for claim in claims:
            if claim.get("verdict") not in VERDICTS:
                raise InputError("EXPERT-CLAIM-VERDICT")
            if claim["verdict"] != "pending" and (
                not isinstance(claim.get("rationale"), str)
                or not claim["rationale"].strip()
            ):
                raise InputError("EXPERT-CLAIM-RATIONALE")
        row["expert"] = {
            "status": "pending"
            if any(c["verdict"] == "pending" for c in criteria + claims)
            else "provisional_reviewed",
            "annotation_status": "preliminary",
            "criteria": [{"id": c["id"], "verdict": c["verdict"]} for c in criteria],
            "claim_reviews": [{"id": c["id"], "verdict": c["verdict"]} for c in claims],
        }


def markdown(report):
    lines = [
        "# Диагностический replay AI",
        "",
        "**Разметка предварительная; окончательной оценки качества модели нет.**",
        "",
        f"Режим: `{report['execution']['mode']}`. Записей: {report['summary']['records']}.",
        f"Получены ответы: {report['summary']['returned']}; технических сбоев: {report['summary']['failed']}.",
        f"Не назначено примеров: {report['summary']['examples_not_scheduled']}; экспертных листов pending: {report['summary']['expert_pending']}.",
        "",
        "| Категория автоматических проверок | Записей с нарушениями / всего |",
        "|---|---:|",
    ]
    lines += [
        f"| {category} | {counts['records_with_diagnostics']} / {counts['records_total']} |"
        for category, counts in report["summary"]["automatic_categories"].items()
    ]
    lines += [
        "",
        "## Отдельные экспертные критерии (предварительно)",
        "",
        "Значения met/not_met/uncertain/not_applicable задаёт эксперт; pending означает отсутствие оценки.",
        "",
        "| Критерий | Распределение вердиктов |",
        "|---|---|",
    ]
    lines += [
        f"| {criterion} | "
        + ", ".join(f"{key}: {count}" for key, count in sorted(counts.items()))
        + " |"
        for criterion, counts in report["summary"][
            "expert_categories_preliminary"
        ].items()
    ]
    lines += [
        "",
        "## Сценарии",
        "",
        "| Сценарий / пример / попытка | Операция | Диагностика | Эксперт |",
        "|---|---|---|---|",
    ]
    for row in report["records"]:
        codes = (
            ", ".join(sorted({d["code"] for d in row["automatic"]["diagnostics"]}))
            or "Нарушений в реализованных проверках нет"
        )
        lines.append(
            f"| {row['case_id']} / {row['example_id']} / {row['attempt']} | {row['operation']} | {codes} | {row['expert']['status']} |"
        )
    lines += ["", "## Ограничения", ""] + [
        "- " + line for line in report["limitations"]
    ]
    return "\n".join(lines) + "\n"


def write_report(report, template, output):
    output = Path(output)
    try:
        output.mkdir(parents=True, exist_ok=False)
    except OSError as error:
        raise InputError("REPORT-DIRECTORY-EXISTS-OR-UNWRITABLE") from error
    for name, value in (("report.json", report), ("expert-review.json", template)):
        (output / name).write_text(
            json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    (output / "report.md").write_text(markdown(report), encoding="utf-8", newline="\n")


def compare_reports(left, right):
    """Compare diagnostics only on the same inputs/checks; no winner or aggregate score."""
    for report in (left, right):
        if (
            not isinstance(report, dict)
            or report.get("format_version") != "1.0"
            or report.get("diagnostic_only") is not True
            or report.get("final_model_quality_assessment") is not False
        ):
            raise InputError("COMPARE-REPORT-FORMAT")
    try:
        if left["dataset"] != right["dataset"] or any(
            left["execution"][k] != right["execution"][k]
            for k in ("schemas_sha256", "tool_sha256")
        ):
            raise InputError("COMPARE-INCOMPATIBLE-VERSIONS")
        inputs = []
        for report in (left, right):
            keys = [
                (r["case_id"], r["example_id"], r["attempt"], r["request_sha256"])
                for r in report["records"]
            ]
            if len(keys) != len(set(keys)) or not keys:
                raise InputError("COMPARE-RECORD-INVENTORY")
            inputs.append(set(keys))
        if inputs[0] != inputs[1]:
            raise InputError("COMPARE-DIFFERENT-INPUTS-OR-ATTEMPTS")
        scenarios = []
        for case in sorted({key[0] for key in inputs[0]}):
            if case not in {f"S{i:02}" for i in range(1, 15)}:
                raise InputError("COMPARE-CASE-ID")
            sides = []
            for report in (left, right):
                rows = [r for r in report["records"] if r["case_id"] == case]
                sides.append(
                    {
                        "records": len(rows),
                        "automatic_categories": {
                            c: sum(
                                any(
                                    d["category"] == c
                                    for d in r["automatic"]["diagnostics"]
                                )
                                for r in rows
                            )
                            for c in CATEGORIES
                        },
                        "expert_pending": sum(
                            r["expert"]["status"] == "pending" for r in rows
                        ),
                    }
                )
            scenarios.append({"case_id": case, "left": sides[0], "right": sides[1]})
        return {
            "diagnostic_only": True,
            "final_model_quality_assessment": False,
            "dataset": left["dataset"],
            "same_inputs_and_checks": True,
            "configuration_equal": left["execution"]["configuration"]
            == right["execution"]["configuration"],
            "models_equal": left["execution"]["model"] == right["execution"]["model"],
            "replays": [
                left["execution"]["replay_sha256"],
                right["execution"]["replay_sha256"],
            ],
            "scenarios": scenarios,
        }
    except (KeyError, TypeError) as error:
        raise InputError("COMPARE-REPORT-INCOMPLETE") from error


def write_comparison(comparison, output):
    try:
        Path(output).mkdir(parents=True, exist_ok=False)
    except OSError as error:
        raise InputError("REPORT-DIRECTORY-EXISTS-OR-UNWRITABLE") from error
    (Path(output) / "comparison.json").write_text(
        json.dumps(comparison, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    lines = [
        "# Сопоставление диагностических результатов",
        "",
        "Предварительная разметка; итоговый балл, рейтинг и окончательная оценка качества не вычисляются.",
        "",
        "Входы, версии набора, разметки, схем и проверочного инструмента совпадают.",
        f"Конфигурации совпадают: {comparison['configuration_equal']}; модели совпадают: {comparison['models_equal']}.",
        "",
        "| Сценарий | Категория | Слева: записей с нарушениями / всего | Справа: записей с нарушениями / всего |",
        "|---|---|---:|---:|",
    ]
    for scenario in comparison["scenarios"]:
        for category in CATEGORIES:
            left, right = scenario["left"], scenario["right"]
            lines.append(
                f"| {scenario['case_id']} | {category} | {left['automatic_categories'][category]} / {left['records']} | {right['automatic_categories'][category]} / {right['records']} |"
            )
    lines += [
        "",
        "Экспертные вердикты остаются отдельными предварительными суждениями в исходных отчётах.",
        "Разные конфигурации — разные условия эксперимента; разницу нельзя приписывать только модели.",
        "",
    ]
    (Path(output) / "comparison.md").write_text(
        "\n".join(lines), encoding="utf-8", newline="\n"
    )
