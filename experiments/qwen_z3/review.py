"""Human-controlled review files; model replies cannot submit trust confirmations."""

from copy import deepcopy

from ai.formal_expectations_bridge import Verification, fingerprint

from .protocol import ExperimentError, canonical

CRITERIA = (
    "atoms",
    "conditions",
    "object_parameter",
    "values_grounded",
    "unknowns",
    "provenance",
    "contexts",
    "omega_completeness",
)
VERDICTS = ("pending", "accepted", "rejected", "uncertain")


def template(binding, case):
    return {
        "review_version": "1",
        "binding": deepcopy(binding),
        "reviewer": None,
        "reviewer_kind": "human",
        "reference_status": case["reference_status"],
        "questions": deepcopy(case["expert_questions"]),
        "criteria": {key: {"verdict": "pending", "rationale": ""} for key in CRITERIA},
        "comparison": {"false_K": None, "false_D": None, "missed_conflict": None, "rationale": ""},
    }


def validate_review(review, binding):
    if type(review) is not dict or set(review) != {
        "review_version",
        "binding",
        "reviewer",
        "reviewer_kind",
        "reference_status",
        "questions",
        "criteria",
        "comparison",
    }:
        raise ExperimentError("review_error", "review_shape")
    if (
        review["review_version"] != "1"
        or canonical(review["binding"]) != canonical(binding)
        or review["reviewer_kind"] != "human"
    ):
        raise ExperimentError("review_error", "review_snapshot_mismatch")
    criteria = review["criteria"]
    if review["reference_status"] != "PRELIMINARY_ENGINEERING_CONTROL":
        raise ExperimentError("review_error", "reference_not_semantic_gold")
    if (
        type(review["questions"]) is not list
        or len(review["questions"]) > 256
        or any(type(q) is not str or len(q) > 1024 for q in review["questions"])
    ):
        raise ExperimentError("review_error", "review_questions")
    if type(criteria) is not dict or set(criteria) != set(CRITERIA):
        raise ExperimentError("review_error", "review_criteria")
    for item in criteria.values():
        if (
            type(item) is not dict
            or set(item) != {"verdict", "rationale"}
            or item["verdict"] not in VERDICTS
            or type(item["rationale"]) is not str
        ):
            raise ExperimentError("review_error", "review_verdict")
        if item["verdict"] != "pending" and not item["rationale"].strip():
            raise ExperimentError("review_error", "review_rationale_required")
    if any(item["verdict"] != "pending" for item in criteria.values()):
        if type(review["reviewer"]) is not str or not review["reviewer"].strip():
            raise ExperimentError("review_error", "human_reviewer_required")
    comparison = review["comparison"]
    if type(comparison) is not dict or set(comparison) != {
        "false_K",
        "false_D",
        "missed_conflict",
        "rationale",
    }:
        raise ExperimentError("review_error", "comparison_shape")
    if (
        any(
            comparison[k] is not None and type(comparison[k]) is not bool
            for k in ("false_K", "false_D", "missed_conflict")
        )
        or type(comparison["rationale"]) is not str
    ):
        raise ExperimentError("review_error", "comparison_value")
    if any(comparison[k] is not None for k in ("false_K", "false_D", "missed_conflict")) and (
        not comparison["rationale"].strip()
        or any(c["verdict"] == "pending" for c in criteria.values())
    ):
        raise ExperimentError("review_error", "comparison_requires_completed_review")
    return deepcopy(review)


def verdict(review):
    items = review["criteria"]
    if any(v["verdict"] == "rejected" for v in items.values()):
        return "semantic_error"
    if items["omega_completeness"]["verdict"] == "uncertain":
        return "unconfirmed_omega"
    if any(v["verdict"] != "accepted" for v in items.values()):
        return "review_required"
    return "approved"


def verifier(packet, review):
    """Only a caller-selected, fully accepted, snapshot-bound human review qualifies."""
    if verdict(review) != "approved" or fingerprint(packet) != review["binding"]["packet_sha256"]:
        raise ExperimentError("review_error", "review_not_approved")
    saved = deepcopy(packet)

    def verify(candidate):
        if candidate != saved:
            raise ExperimentError("review_error", "packet_changed_after_review")
        return Verification(
            fingerprint(saved),
            review["reviewer"],
            "Accepted human review " + fingerprint(review),
            True,
            True,
            True,
            True,
            True,
        )

    return verify
