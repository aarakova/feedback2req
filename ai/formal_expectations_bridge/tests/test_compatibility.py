"""Mechanical comparison only: all DTOs here are explicitly synthetic fixtures."""

import json
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from ai.formal_expectations import Limits
from ai.formal_expectations_bridge import check_pair
from ai.formal_expectations_bridge.compatibility import audit_saved_inputs
from ai.formal_expectations_bridge.synthetic import base, catalog


def saved_fixture(data):
    """Test-only construction with known local/persistent associations, not an exporter."""
    request, response = data["grouping_request"], data["grouping_response"]
    fragments = {f["key"]: f for f in request["input"]["fragments"]}
    findings, sources = {}, {}
    for finding in request["input"]["findings"]:
        row = {k: deepcopy(finding[k]) for k in ("text", "types", "mode", "authorship")}
        row.update(
            id=finding["ref"]["id"],
            state_id=finding["ref"]["state_id"],
            freshness="current",
            evidence=[],
        )
        for link in finding["evidence"]:
            if link["kind"] != "available":
                continue
            fragment = fragments[link["fragment_key"]]
            value = {
                k: deepcopy(fragment[k])
                for k in ("source_ref", "text_ref", "quote", "locator", "reliability")
            }
            value.update(id=fragment["ref"]["id"], state_id=fragment["ref"]["state_id"])
            row["evidence"].append(value)
            ref = fragment["text_ref"]
            sources[ref["id"], ref["state_id"]] = {
                "id": ref["id"],
                "state_id": ref["state_id"],
                "text": fragment["quote"],
                "kind": "text",
            }
        findings[finding["key"]] = row
    groups, bindings = [], []
    for i, group in enumerate(response["result"]["groups"]):
        ref = {"kind": "finding_group", "id": f"saved-group-{i}", "state_id": f"saved-state-{i}"}
        conflicts, links = [], []
        for j, conflict in enumerate(group["conflicts"]):
            identity = f"saved-conflict-{i}-{j}"
            links.append({"local_id": conflict["local_id"], "id": identity})
            conflicts.append(
                {
                    "id": identity,
                    "description": conflict["description"],
                    "positions": [
                        {
                            "id": f"p-{i}-{j}-{n}",
                            "description": p["description"],
                            "findings": [
                                deepcopy(
                                    next(
                                        f["ref"]
                                        for f in request["input"]["findings"]
                                        if f["key"] == k
                                    )
                                )
                                for k in p["finding_keys"]
                            ],
                        }
                        for n, p in enumerate(conflict["positions"])
                    ],
                }
            )

        def refs(keys):
            return [
                deepcopy(next(f["ref"] for f in request["input"]["findings"] if f["key"] == k))
                for k in keys
            ]

        groups.append(
            {
                "id": ref["id"],
                "state_id": ref["state_id"],
                "title": group["title"],
                "summary": group["summary"],
                "members": [
                    {"ref": r, "finding": deepcopy(findings[k])}
                    for r, k in zip(refs(group["finding_keys"]), group["finding_keys"], strict=True)
                ],
                "considered_findings": refs(group["considered_keys"]),
                "conflicts": conflicts,
                "context": [],
                "freshness": "current",
            }
        )
        bindings.append({"local_id": group["local_id"], "ref": ref, "conflicts": links})
    return {
        "findings": list(findings.values()),
        "groups": groups,
        "sources": list(sources.values()),
        "group_bindings": bindings,
    }


class CompatibilityTests(unittest.TestCase):
    def test_matched_is_not_trusted_and_does_not_call_solver(self):
        data = base()
        saved = saved_fixture(data)
        original = deepcopy(saved)
        with patch("ai.formal_expectations_bridge.service.analyze") as solver:
            result = audit_saved_inputs(data, saved)
            self.assertEqual(result.status, "matched", result.to_dict())
            self.assertIsNone(result.classification)
            self.assertFalse(result.verification_created)
            self.assertTrue(result.outstanding_gates)
            self.assertEqual(check_pair(data, verify=None).status, "verification_required")
            solver.assert_not_called()
        self.assertEqual(saved, original)

    def test_exact_states_quotes_reliability_and_membership(self):
        data = base()
        for change in (
            "finding_state",
            "source_state",
            "quote",
            "mode",
            "reliability",
            "fragment_owner",
            "embedded_state",
            "position",
        ):
            saved = saved_fixture(data)
            if change == "finding_state":
                saved["findings"][0]["state_id"] = "newer-finding"
            elif change == "source_state":
                saved["sources"][0]["state_id"] = "newer-source"
            elif change == "quote":
                saved["sources"][0]["text"] = "x" * len(saved["sources"][0]["text"])
            elif change == "mode":
                saved["findings"][0]["mode"] = "inferred"
            elif change == "reliability":
                saved["findings"][0]["evidence"][0]["reliability"] = "uncertain"
            elif change == "fragment_owner":
                saved["findings"][0]["evidence"] = saved["findings"][1]["evidence"]
            elif change == "embedded_state":
                saved["groups"][0]["members"][0]["finding"]["state_id"] = "wrong"
            else:
                positions = saved["groups"][0]["conflicts"][0]["positions"]
                positions[0]["findings"] = deepcopy(positions[1]["findings"])
            with self.subTest(change=change):
                result = audit_saved_inputs(data, saved)
                self.assertIn(result.status, ("missing", "mismatch"), result.to_dict())
                self.assertIsNone(result.classification)

    def test_full_multi_finding_position_not_first_member(self):
        data = next(c["input"] for c in catalog() if c["id"] == "15-multiple-position-findings")
        saved = saved_fixture(data)
        self.assertEqual(audit_saved_inputs(data, saved).status, "matched")
        pos = next(
            p for p in saved["groups"][0]["conflicts"][0]["positions"] if len(p["findings"]) > 1
        )
        pos["findings"] = pos["findings"][:1]
        result = audit_saved_inputs(data, saved)
        self.assertEqual(result.status, "mismatch")
        self.assertIn("full_position_members", [d["rule"] for d in result.diagnostics])

    def test_mapping_is_never_inferred_and_groupdetail_not_reconstructed(self):
        data = base()
        saved = saved_fixture(data)
        saved["group_bindings"] = []
        self.assertEqual(audit_saved_inputs(data, saved).status, "missing")
        self.assertEqual(
            audit_saved_inputs(saved["groups"][0], saved).status, "preparation_required"
        )
        saved = saved_fixture(data)
        saved["group_bindings"][0]["ref"]["state_id"] = "current-instead-of-selected"
        self.assertEqual(audit_saved_inputs(data, saved).status, "missing")

    def test_duplicate_bad_shape_and_resource_limit_are_not_U(self):
        data = base()
        saved = saved_fixture(data)
        saved["findings"].append(deepcopy(saved["findings"][0]))
        self.assertEqual(audit_saved_inputs(data, saved).status, "invalid_input")
        self.assertEqual(audit_saved_inputs(data, b'{"broken"').status, "invalid_input")
        result = audit_saved_inputs(data, saved_fixture(data), limits=Limits(max_input_bytes=1))
        self.assertEqual(result.status, "technical_error")
        self.assertIsNone(result.classification)

    def test_cli_audit_is_offline_and_safe(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = base()
            (root / "input.json").write_text(json.dumps(data), encoding="utf-8")
            (root / "saved.json").write_text(json.dumps(saved_fixture(data)), encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    "-m",
                    "ai.formal_expectations_bridge",
                    "audit",
                    str(root / "input.json"),
                    "--saved",
                    str(root / "saved.json"),
                ],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["status"], "matched")
            self.assertNotIn("quote", result.stdout)
