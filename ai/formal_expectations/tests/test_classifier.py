import itertools
import json
import random
import subprocess
import sys
import unittest
from contextlib import nullcontext
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

import z3

from ai.formal_expectations import Limits, analyze
from ai.formal_expectations.tests.cases import catalog, completion, interval, request, uncertain

ROOT = Path(__file__).resolve().parents[1]


class ClassifierTests(unittest.TestCase):
    def assert_class(self, value, expected):
        result = analyze(value)
        self.assertEqual(result.classification, expected, result.to_dict())
        self.assertTrue(result.complete)
        self.assertIsNone(result.diagnostic)
        self.assertEqual(len(result.checks), 2 * result.variants_total)
        return result

    def assert_error(self, value, code, rule=None, **kwargs):
        result = analyze(value, **kwargs)
        self.assertEqual(result.status, "failed", result.to_dict())
        self.assertIsNone(result.classification)
        self.assertFalse(result.complete)
        self.assertEqual(result.diagnostic.code, code, result.to_dict())
        if rule:
            self.assertEqual(result.diagnostic.rule, rule)
        return result

    def test_saved_scenarios(self):
        saved = json.loads((ROOT / "tests" / "scenarios.json").read_text(encoding="utf-8"))
        self.assertEqual(saved, catalog())
        self.assertEqual(len(saved), 19)
        for case in saved:
            with self.subTest(case=case["id"]):
                self.assertTrue(case["explanation"])
                context = (
                    patch(
                        "ai.formal_expectations.solver.z3.Solver.check",
                        side_effect=z3.Z3Exception("untrusted source in exception"),
                    )
                    if case.get("fault")
                    else nullcontext()
                )
                with context:
                    result = analyze(case["input"], limits=Limits(**case.get("limits", {})))
                self.assertEqual(result.classification, case["expected_class"], result.to_dict())
                diagnostic = result.diagnostic.code if result.diagnostic else None
                self.assertEqual(diagnostic, case["expected_diagnostic"], result.to_dict())

    def test_independent_checks_and_D_precedence(self):
        value = request()
        value["right"]["conditions"] = ["offline"]
        result = self.assert_class(value, "D")
        self.assertEqual([c.state for c in result.checks], ["unsat", "unsat"])

    def test_numeric_domains_units_exactness_and_singletons(self):
        value = request()
        value["left"]["values"] = interval("0.1", "0.3")
        value["right"]["values"] = interval(300, 300, "ms")
        self.assert_class(value, "S")
        value["right"]["values"] = interval("300.000000000000000001", 301, "ms")
        self.assert_class(value, "K")
        value["left"]["values"] = interval(-1, 1)
        self.assert_error(value, "invalid_formalization", "outside_parameter_domain")

    def test_negative_interval_and_zero(self):
        value = request()
        value["model"]["domain"] = {**interval(-10, 10, "1"), "dimension": "dimensionless"}
        value["left"]["values"] = interval(-3, 0, "1")
        value["right"]["values"] = interval(0, 3, "1")
        self.assert_class(value, "S")

    def test_boolean_and_enum_positive_negative(self):
        for kind, domain, left, right in (
            ("boolean", [False, True], [True], [True]),
            ("enum", ["red", "green"], ["red"], ["green"]),
        ):
            with self.subTest(kind=kind):
                value = request()
                value["model"]["domain"] = {"kind": kind, "allowed": domain}
                value["left"]["values"] = {"kind": kind, "allowed": left}
                value["right"]["values"] = {"kind": kind, "allowed": right}
                self.assert_class(value, "S" if left == right else "K")
                value["left"]["values"]["allowed"] = [1] if kind == "boolean" else ["blue"]
                self.assert_error(
                    value, "invalid_input" if kind == "boolean" else "invalid_formalization"
                )

    def test_unknown_is_not_universal(self):
        value = request()
        value["left"]["conditions"] = None
        self.assert_error(value, "incomplete_omega", "unknown_requires_omega")
        value = uncertain()
        value["omega"]["complete"] = False
        self.assert_error(value, "incomplete_omega", "omega_not_declared_complete")

    def test_unknown_values_and_correlated_variants(self):
        value = request()
        value["omega"] = {"complete": True, "variants": []}
        for allowed in (interval(1, 3), interval(5, 6)):
            variant = {side: completion(value[side]) for side in ("left", "right")}
            variant["left"]["values"] = allowed
            value["omega"]["variants"].append(variant)
        value["left"]["values"] = None
        self.assert_class(value, "U")

    def test_invalid_refinement_is_not_discarded(self):
        for field, bad in (("conditions", ["maintenance"]), ("values", interval(2, 3))):
            value = uncertain()
            value["omega"]["variants"][1]["right"][field] = bad
            result = self.assert_error(
                value, "invalid_formalization", "refinement_changes_known_data"
            )
            self.assertEqual(result.checks, ())
        value = uncertain()
        value["omega"]["variants"][1]["left"]["conditions"] = ["unmodeled"]
        self.assert_error(value, "invalid_formalization", "outside_situation_domain")

    def test_refinement_normalizes_equivalent_units(self):
        value = uncertain()
        value["omega"]["variants"][0]["right"]["values"] = interval(5000, 10000, "ms")
        self.assert_class(value, "U")

    def test_nonempty_omega_subsets_preserve_unique_class(self):
        for base_class in ("D", "K", "S"):
            value = uncertain()
            for variant in value["omega"]["variants"]:
                variant["left"]["conditions"] = ["online"]
                if base_class == "D":
                    variant["left"]["conditions"] = ["offline"]
                elif base_class == "S":
                    variant["left"]["values"] = interval(5, 6)
            if base_class == "S":
                value["left"]["values"] = None
            self.assert_class(value, base_class)
            for subset in ([0], [1], [0, 1]):
                narrowed = deepcopy(value)
                narrowed["omega"]["variants"] = [value["omega"]["variants"][i] for i in subset]
                self.assert_class(narrowed, base_class)

    def test_ambiguous_omega_can_become_unique_after_new_information(self):
        value = uncertain()
        self.assert_class(value, "U")
        value["omega"]["variants"] = value["omega"]["variants"][:1]
        self.assert_class(value, "K")

    def test_symmetry_all_saved_successes(self):
        for case in catalog():
            if case["expected_class"] is None:
                continue
            value = deepcopy(case["input"])
            before = self.assert_class(value, case["expected_class"])
            value["left"], value["right"] = value["right"], value["left"]
            for variant in value.get("omega", {}).get("variants", []):
                variant["left"], variant["right"] = variant["right"], variant["left"]
            after = self.assert_class(value, before.classification)
            self.assertEqual(before.observed_classes, after.observed_classes)

    def test_fixed_seed_intervals_against_set_oracle(self):
        rng = random.Random(410936)
        for _ in range(100):
            value = request()
            a, b = sorted(rng.sample(range(0, 101), 2))
            c, d = sorted(rng.sample(range(0, 101), 2))
            value["left"]["values"] = interval(a, b)
            value["right"]["values"] = interval(c, d)
            value["left"]["conditions"] = rng.sample(
                value["model"]["situations"], rng.randint(1, 3)
            )
            value["right"]["conditions"] = rng.sample(
                value["model"]["situations"], rng.randint(1, 3)
            )
            common = set(value["left"]["conditions"]) & set(value["right"]["conditions"])
            expected = "D" if not common else "K" if max(a, c) > min(b, d) else "S"
            self.assert_class(value, expected)
            value["left"], value["right"] = value["right"], value["left"]
            self.assert_class(value, expected)

    def test_pairwise_does_not_prove_global_compatibility(self):
        value = deepcopy(catalog()[-1]["input"])
        sets = [{"a", "b"}, {"b", "c"}, {"a", "c"}]
        for left, right in itertools.combinations(sets, 2):
            value["left"]["values"]["allowed"] = sorted(left)
            value["right"]["values"]["allowed"] = sorted(right)
            self.assert_class(value, "S")
        self.assertFalse(set.intersection(*sets))

    def test_fixed_seed_omega_and_all_nonempty_subsets(self):
        rng = random.Random(410936)
        for _ in range(20):
            value = request()
            variants, classes = [], set()
            for _ in range(3):
                variant = {}
                endpoints = []
                for side in ("left", "right"):
                    lo, hi = sorted(rng.choices(range(0, 11), k=2))
                    endpoints.append((lo, hi))
                    variant[side] = {
                        "conditions": rng.sample(["online", "offline"], rng.randint(1, 2)),
                        "values": interval(lo, hi),
                    }
                common = set(variant["left"]["conditions"]) & set(variant["right"]["conditions"])
                (a, b), (c, d) = endpoints
                classes.add("D" if not common else "K" if max(a, c) > min(b, d) else "S")
                variants.append(variant)
            for side in ("left", "right"):
                value[side]["conditions"] = value[side]["values"] = None
            value["omega"] = {"complete": True, "variants": variants}
            expected = next(iter(classes)) if len(classes) == 1 else "U"
            result = self.assert_class(value, expected)
            self.assertEqual(result.observed_classes, tuple(sorted(classes)))
            swapped = deepcopy(value)
            swapped["left"], swapped["right"] = swapped["right"], swapped["left"]
            for variant in swapped["omega"]["variants"]:
                variant["left"], variant["right"] = variant["right"], variant["left"]
            self.assert_class(swapped, expected)
            if expected != "U":
                for size in range(1, len(variants) + 1):
                    for subset in itertools.combinations(variants, size):
                        narrowed = deepcopy(value)
                        narrowed["omega"]["variants"] = list(subset)
                        self.assert_class(narrowed, expected)

    def test_input_is_not_mutated(self):
        value = uncertain()
        original = deepcopy(value)
        self.assert_class(value, "U")
        self.assertEqual(value, original)

    def test_cli_examples_and_failures(self):
        for relation in "DKSU":
            with self.subTest(relation=relation):
                path = ROOT / "examples" / f"{relation}.json"
                result = subprocess.run(
                    [sys.executable, "-m", "ai.formal_expectations", str(path)],
                    capture_output=True,
                    text=True,
                    timeout=15,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(result.stdout)["classification"], relation)
        for raw, expected in ((json.dumps(uncertain()), "U"), ("not json", None)):
            result = subprocess.run(
                [sys.executable, "-m", "ai.formal_expectations", "-"],
                input=raw,
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            self.assertEqual(result.returncode, 0 if expected else 2)
            self.assertEqual(json.loads(result.stdout)["classification"], expected)


if __name__ == "__main__":
    unittest.main()
