"""Shared exact extraction read models for F1 and F2."""

from sqlalchemy import select

from feedback2req.persistence.models import FeedbackSource
from feedback2req.persistence.processing import Attempt, FindingEvidence, Fragment


def fragment_view(row):
    ref = {"kind": "feedback_source", "id": row.source_id, "state_id": row.source_state_id}
    return {
        "id": row.id,
        "state_id": row.id,
        "attempt_id": row.attempt_id,
        "source_ref": ref,
        "text_ref": dict(ref),
        "quote": row.quote,
        "locator": {"start": row.start, "end": row.end},
        "reliability": row.reliability,
    }


def finding_view(tx, row):
    attempt = tx.get(Attempt, row.attempt_id)
    fragments = tx.scalars(
        select(Fragment)
        .join(FindingEvidence, FindingEvidence.fragment_id == Fragment.id)
        .where(FindingEvidence.finding_id == row.id, FindingEvidence.project_id == row.project_id)
    ).all()
    current = all(
        tx.scalar(
            select(FeedbackSource.current_state_id).where(
                FeedbackSource.project_id == row.project_id,
                FeedbackSource.id == fragment.source_id,
                FeedbackSource.availability == "available",
            )
        )
        == fragment.source_state_id
        for fragment in fragments
    )
    return {
        "id": row.id,
        "state_id": row.id,
        "text": row.text,
        "types": row.types,
        "mode": row.mode,
        "authorship": "ai",
        "synthetic": attempt.synthetic,
        "attempt_id": attempt.id,
        "created_at": row.created_at,
        "freshness": "current" if current else "requires_update",
        "evidence": [fragment_view(fragment) for fragment in fragments],
        "coverage": attempt.coverage,
        "annotations": attempt.annotations,
        "provider": attempt.provider,
        "model": attempt.model,
        "ai_performed": attempt.ai_performed,
    }
