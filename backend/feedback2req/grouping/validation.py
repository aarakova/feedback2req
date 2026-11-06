"""Deterministic contract acceptance, not proof of a semantic contradiction."""

from feedback2req.processing.validation import InvalidResponse, schema


def strings(value):
    if isinstance(value, str):
        if "\x00" in value or len(value) > 32768:
            raise InvalidResponse()
        value.encode("utf-8", "strict")
    elif isinstance(value, dict):
        for item in value.values():
            strings(item)
    elif isinstance(value, list):
        for item in value:
            strings(item)


def accept(request, response):
    try:
        schema("group_findings.request").validate(request)
        schema("group_findings.response").validate(response)
        strings(response)
        data = request["input"]
        findings = {item["key"] for item in data["findings"]}
        previous_groups = {item["key"] for item in data.get("previous_groups", [])}
        documents = {item["key"] for item in data["documents"]}
        input_keys = [v["key"] for items in data.values() for v in items]
        if len(input_keys) != len(set(input_keys)):
            raise InvalidResponse()
        groups = response["result"]["groups"]
        local_ids = [
            v["local_id"] for v in groups + response["questions"] + response["uncertainties"]
        ]
        local_ids += [c["local_id"] for g in groups for c in g["conflicts"]]
        if len(local_ids) != len(set(local_ids)) or any(len(v) > 256 for v in local_ids):
            raise InvalidResponse()
        coverage = {item["input_key"]: item for item in response["coverage"]}
        if len(coverage) != len(response["coverage"]) or coverage.keys() != findings:
            raise InvalidResponse()
        if any(c["disposition"] == "partially_processed" for c in coverage.values()):
            raise InvalidResponse()
        reviewed = {key for key, c in coverage.items() if c["reviewed"]}
        completed = {key for key, c in coverage.items() if c["disposition"] == "completed"}
        grouped = set()
        for group in groups:
            members, considered = set(group["finding_keys"]), set(group["considered_keys"])
            if not members <= considered <= reviewed or not set(group["context_keys"]) <= documents:
                raise InvalidResponse()
            grouped.update(members)
            for conflict in group["conflicts"]:
                positions = set()
                for position in conflict["positions"]:
                    if not set(position["finding_keys"]) <= members:
                        raise InvalidResponse()
                    key = (position["description"], tuple(sorted(position["finding_keys"])))
                    if key in positions:
                        raise InvalidResponse()
                    positions.add(key)
        ungrouped = set(response["result"]["ungrouped_finding_keys"])
        if grouped & ungrouped or not ungrouped <= reviewed or not completed <= grouped | ungrouped:
            raise InvalidResponse()
        # Explicit ungrouped membership is itself a substantive classification.
        # It does not require an extra reason for an allegedly empty result.
        outputs = {group["local_id"] for group in groups}
        for item in response["questions"] + response["uncertainties"]:
            for link in item["related"]:
                allowed = findings | previous_groups if link["origin"] == "input" else outputs
                if link["key"] not in allowed:
                    raise InvalidResponse()
    except InvalidResponse:
        raise
    except Exception as exc:
        raise InvalidResponse() from exc
