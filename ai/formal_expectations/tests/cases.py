"""Synthetic inputs, expected outcomes and rationales; no LLM-derived labels.

Run as a module to export the four CLI examples. The full catalog is executable
fixture data shared by tests and the reviewable scenarios.json snapshot.
"""

import json
from copy import deepcopy
from pathlib import Path


def interval(lower=1, upper=3, unit="s"):
    return {"kind": "interval", "lower": str(lower), "upper": str(upper), "unit": unit}


def request():
    domain = interval(0, 100)
    domain["dimension"] = "time"
    return {
        "format_version": "1",
        "model": {
            "object_id": "product:export",
            "parameter_id": "latency",
            "situations": ["online", "offline", "maintenance"],
            "domain": domain,
        },
        "left": {
            "object_id": "product:export",
            "parameter_id": "latency",
            "basis": "synthetic:finding-left",
            "conditions": ["online"],
            "values": interval(),
        },
        "right": {
            "object_id": "product:export",
            "parameter_id": "latency",
            "basis": "synthetic:finding-right",
            "conditions": ["online"],
            "values": interval(5, 10),
        },
    }


def completion(expectation):
    return {k: deepcopy(expectation[k]) for k in ("conditions", "values")}


def uncertain():
    value = request()
    first = {side: completion(value[side]) for side in ("left", "right")}
    second = deepcopy(first)
    second["left"]["conditions"] = ["offline"]
    value["left"]["conditions"] = None
    value["omega"] = {"complete": True, "variants": [first, second]}
    return value


def catalog():
    cases = []

    def save(name, value, explanation, classification=None, diagnostic=None, **extra):
        cases.append(
            {
                "id": name,
                "input": deepcopy(value),
                "expected_class": classification,
                "expected_diagnostic": diagnostic,
                "explanation": explanation,
                **extra,
            }
        )

    value = request()
    value["right"]["conditions"] = ["offline"]
    save("01-D", value, "Application situations are disjoint.", "D")
    save("02-K", request(), "In the common situation [1,3] and [5,10] are disjoint.", "K")
    value = request()
    value["left"]["values"] = interval(1, 5)
    value["right"]["values"] = interval(1, 3)
    save("03-S", value, "Common values form [1,3].", "S")
    value["right"]["values"] = interval(5, 10)
    save("04-closed-boundary", value, "The shared endpoint 5 belongs to both closed sets.", "S")
    save("05-U", uncertain(), "The unknown condition admits one K and one D refinement.", "U")
    value = uncertain()
    value["right"]["conditions"] = ["online", "offline"]
    for variant in value["omega"]["variants"]:
        variant["right"]["conditions"] = ["online", "offline"]
    save(
        "06-irrelevant-missing", value, "Both possible conditions overlap; every variant is K.", "K"
    )
    value = uncertain()
    value["omega"]["variants"] = []
    save(
        "07-empty-omega",
        value,
        "An empty refinement space is a formalization error.",
        diagnostic="invalid_formalization",
    )
    value = request()
    value["right"]["object_id"] = "other-product"
    save(
        "08-objects",
        value,
        "Different objects have no established comparability.",
        diagnostic="not_comparable",
    )
    value = request()
    value["right"]["parameter_id"] = "memory"
    save(
        "09-parameters",
        value,
        "Different parameters cannot be classified as a pair.",
        diagnostic="not_comparable",
    )
    value = request()
    value["left"]["values"] = interval(3, 1)
    save(
        "10-interval",
        value,
        "A reversed interval is not an atomic admissible value set.",
        diagnostic="invalid_formalization",
    )
    value = request()
    value["left"]["values"]["unit"] = "m"
    save(
        "11-units",
        value,
        "Length cannot be compared with the declared time dimension.",
        diagnostic="invalid_formalization",
    )
    value = request()
    value["model"]["domain"] = {"kind": "boolean", "allowed": [False, True]}
    value["left"]["values"] = {"kind": "boolean", "allowed": [True]}
    value["right"]["values"] = {"kind": "boolean", "allowed": [False]}
    save(
        "12-boolean", value, "Opposite Boolean expectations conflict in the common situation.", "K"
    )
    value["model"]["domain"] = {"kind": "enum", "allowed": ["a", "b", "c"]}
    value["left"]["values"] = {"kind": "enum", "allowed": ["a", "b"]}
    value["right"]["values"] = {"kind": "enum", "allowed": ["b", "c"]}
    save("13-enum", value, "The common enum value is b.", "S")
    value = request()
    value["left"]["values"] = {"kind": "python", "code": "__import__('os').system('echo unsafe')"}
    save(
        "14-malicious",
        value,
        "Executable structures are outside the closed grammar.",
        diagnostic="unsupported_input",
    )
    save(
        "15-budget",
        request(),
        "One solver call cannot complete both required checks.",
        diagnostic="resource_limit",
        limits={"max_solver_calls": 1},
    )
    save(
        "16-solver-failure",
        request(),
        "Injected native solver failure produces no semantic class.",
        diagnostic="solver_failure",
        fault="solver_exception",
    )
    save("17-symmetry", request(), "Swapping the two expectations preserves K.", "K")
    value = uncertain()
    value["right"]["conditions"] = ["online", "offline"]
    for variant in value["omega"]["variants"]:
        variant["right"]["conditions"] = ["online", "offline"]
    save("18-refinement", value, "Any nonempty subset of this unchanged Ω still yields K.", "K")
    value = request()
    value["model"]["domain"] = {"kind": "enum", "allowed": ["a", "b", "c"]}
    value["left"]["values"] = {"kind": "enum", "allowed": ["a", "b"]}
    value["right"]["values"] = {"kind": "enum", "allowed": ["b", "c"]}
    save(
        "19-pairwise-not-global",
        value,
        "Sets {a,b}, {b,c}, {a,c} intersect pairwise but their triple intersection is empty.",
        "S",
        third_values={"kind": "enum", "allowed": ["a", "c"]},
    )
    return cases


def write_snapshots():
    root = Path(__file__).resolve().parents[1]
    (root / "examples").mkdir(exist_ok=True)
    cases = catalog()
    (root / "tests" / "scenarios.json").write_text(
        json.dumps(cases, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    for name, case_id in {"D": "01-D", "K": "02-K", "S": "03-S", "U": "05-U"}.items():
        value = next(case["input"] for case in cases if case["id"] == case_id)
        (root / "examples" / f"{name}.json").write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )


if __name__ == "__main__":
    write_snapshots()
