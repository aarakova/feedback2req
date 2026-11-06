"""Explicit disposable synthetic scenarios; no default real provider or fallback."""

import json

from ai.group_findings.validation import GroupingError


class UnconfiguredGrouping:
    name, model, synthetic = "unconfigured", "none", False

    def group(self, request):
        raise GroupingError("provider_error", "provider_not_configured")


class SyntheticGrouping:
    name, synthetic = "synthetic-grouping-fixture", True

    def __init__(self, scenario):
        self.scenario = scenario
        self.model = "fixture-" + scenario

    def group(self, request):
        if self.scenario == "error":
            raise GroupingError("provider_error", "provider_transport")
        if self.scenario == "invalid":
            return "{invalid"
        keys = [item["key"] for item in request["input"]["findings"]]
        groups = []
        if self.scenario != "ungrouped":
            group = {
                "local_id": "g1",
                "title": "Synthetic fixture",
                "summary": "No semantic inference",
                "finding_keys": keys,
                "considered_keys": keys,
                "context_keys": [],
                "conflicts": [],
            }
            if len(keys) >= 2:
                group["conflicts"] = [
                    {
                        "local_id": "c1",
                        "description": "Synthetic opposed positions",
                        "positions": [
                            {"description": "Position A", "finding_keys": [keys[0]]},
                            {"description": "Position B", "finding_keys": [keys[1]]},
                        ],
                    }
                ]
            groups.append(group)
            if self.scenario == "many":
                groups.append(dict(group, local_id="g2", conflicts=[], finding_keys=keys[:1]))
        return json.dumps(
            {
                "coverage": [
                    {"input_key": key, "reviewed": True, "disposition": "completed"} for key in keys
                ],
                "questions": [],
                "uncertainties": [],
                "result": {"groups": groups, "ungrouped_finding_keys": keys if not groups else []},
            }
        )


def grouping_provider(settings):
    # Future approved real configuration belongs here, never in an exception fallback.
    if settings.grouping_synthetic_scenario is not None:
        return SyntheticGrouping(settings.grouping_synthetic_scenario)
    return UnconfiguredGrouping()
