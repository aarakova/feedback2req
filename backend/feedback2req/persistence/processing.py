"""Immutable accepted extraction outputs and durable, single-attempt work units."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from feedback2req.persistence.models import Base


class Run(Base):
    __tablename__ = "processing_runs"
    __table_args__ = (
        UniqueConstraint("project_id", "id"),
        UniqueConstraint("project_id", "initiated_by", "command_kind", "idempotency_key"),
        CheckConstraint("operation IN ('inspect_text','extract_feedback')"),
        CheckConstraint("command_kind IN ('start','retry')"),
        CheckConstraint("length(fingerprint) = 64"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"))
    initiated_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    operation: Mapped[str] = mapped_column(String(32))
    command_kind: Mapped[str] = mapped_column(String(8))
    idempotency_key: Mapped[UUID]
    fingerprint: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Unit(Base):
    __tablename__ = "processing_units"
    __table_args__ = (
        UniqueConstraint("project_id", "id"),
        UniqueConstraint("run_id", "source_id"),
        UniqueConstraint("run_id", "document_id"),
        UniqueConstraint("retry_of_attempt_id"),
        ForeignKeyConstraint(
            ["project_id", "run_id"], ["processing_runs.project_id", "processing_runs.id"]
        ),
        ForeignKeyConstraint(
            ["project_id", "source_id", "source_state_id"],
            [
                "source_text_states.project_id",
                "source_text_states.source_id",
                "source_text_states.id",
            ],
        ),
        ForeignKeyConstraint(
            ["project_id", "document_id", "document_state_id"],
            ["document_states.project_id", "document_states.document_id", "document_states.id"],
        ),
        ForeignKeyConstraint(
            ["project_id", "retry_of_attempt_id"],
            ["stage_attempts.project_id", "stage_attempts.id"],
            use_alter=True,
            name="fk_unit_retry",
        ),
        CheckConstraint(
            "(source_id IS NOT NULL AND source_state_id IS NOT NULL "
            "AND document_id IS NULL AND document_state_id IS NULL) OR "
            "(document_id IS NOT NULL AND document_state_id IS NOT NULL "
            "AND source_id IS NULL AND source_state_id IS NULL)"
        ),
        CheckConstraint("state IN ('queued','running','completed','failed','cancelled')"),
        Index("ix_units_queue", "state", "created_at", "id"),
        Index("ix_units_run", "project_id", "run_id", "id"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"))
    run_id: Mapped[UUID]
    source_id: Mapped[UUID | None]
    source_state_id: Mapped[UUID | None]
    document_id: Mapped[UUID | None]
    document_state_id: Mapped[UUID | None]
    retry_of_attempt_id: Mapped[UUID | None]
    state: Mapped[str] = mapped_column(String(16), default="queued")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Attempt(Base):
    __tablename__ = "stage_attempts"
    __table_args__ = (
        UniqueConstraint("project_id", "id"),
        UniqueConstraint("unit_id"),
        ForeignKeyConstraint(
            ["project_id", "unit_id"], ["processing_units.project_id", "processing_units.id"]
        ),
        CheckConstraint("state IN ('running','completed','failed','cancelled')"),
        CheckConstraint("deadline_at > started_at"),
        CheckConstraint("finished_at IS NULL OR finished_at >= started_at"),
        CheckConstraint("character_count IS NULL OR character_count > 0"),
        CheckConstraint("utf8_byte_count IS NULL OR utf8_byte_count >= character_count"),
        CheckConstraint(
            "(state='running' AND owner_token IS NOT NULL AND lease_expires_at IS NOT NULL "
            "AND finished_at IS NULL AND reason_code IS NULL) OR "
            "(state<>'running' AND owner_token IS NULL AND lease_expires_at IS NULL "
            "AND finished_at IS NOT NULL)"
        ),
        CheckConstraint("lease_expires_at IS NULL OR lease_expires_at <= deadline_at"),
        CheckConstraint(
            "(state='completed' AND reason_code IS NULL) OR state='running' OR "
            "(state IN ('failed','cancelled') AND reason_code IS NOT NULL)"
        ),
        Index("ix_attempts_lease", "lease_expires_at"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"))
    unit_id: Mapped[UUID]
    request_id: Mapped[UUID] = mapped_column(unique=True, default=uuid4)
    state: Mapped[str] = mapped_column(String(16))
    owner_token: Mapped[UUID | None]
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    deadline_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reason_code: Mapped[str | None] = mapped_column(String(32))
    provider: Mapped[str | None] = mapped_column(String(64))
    model: Mapped[str | None] = mapped_column(String(128))
    synthetic: Mapped[bool] = mapped_column(Boolean, default=False)
    ai_performed: Mapped[bool | None] = mapped_column(Boolean, default=False)
    coverage: Mapped[list | None] = mapped_column(JSONB)
    annotations: Mapped[dict | None] = mapped_column(JSONB)
    character_count: Mapped[int | None] = mapped_column(BigInteger)
    utf8_byte_count: Mapped[int | None] = mapped_column(BigInteger)


class Fragment(Base):
    __tablename__ = "feedback_fragments"
    __table_args__ = (
        UniqueConstraint("project_id", "id"),
        UniqueConstraint("attempt_id", "local_id"),
        ForeignKeyConstraint(
            ["project_id", "attempt_id"], ["stage_attempts.project_id", "stage_attempts.id"]
        ),
        ForeignKeyConstraint(
            ["project_id", "source_id", "source_state_id"],
            [
                "source_text_states.project_id",
                "source_text_states.source_id",
                "source_text_states.id",
            ],
        ),
        CheckConstraint('start >= 0 AND "end" > start'),
        CheckConstraint("reliability IN ('usable','uncertain')"),
        CheckConstraint('length(quote) = "end" - start'),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"))
    attempt_id: Mapped[UUID]
    local_id: Mapped[str] = mapped_column(String(256))
    source_id: Mapped[UUID]
    source_state_id: Mapped[UUID]
    quote: Mapped[str] = mapped_column(Text)
    start: Mapped[int] = mapped_column(BigInteger)
    end: Mapped[int] = mapped_column(BigInteger)
    reliability: Mapped[str] = mapped_column(String(16))


class Finding(Base):
    __tablename__ = "findings"
    __table_args__ = (
        UniqueConstraint("project_id", "id"),
        UniqueConstraint("attempt_id", "local_id"),
        ForeignKeyConstraint(
            ["project_id", "attempt_id"], ["stage_attempts.project_id", "stage_attempts.id"]
        ),
        CheckConstraint("mode IN ('direct','inferred')"),
        CheckConstraint("length(text) > 0"),
        CheckConstraint(
            "jsonb_typeof(types)='array' AND jsonb_array_length(types)>0 AND "
            "types <@ '[\"problem\",\"request\",\"observation\",\"need\"]'::jsonb"
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"))
    attempt_id: Mapped[UUID]
    local_id: Mapped[str] = mapped_column(String(256))
    text: Mapped[str] = mapped_column(Text)
    types: Mapped[list] = mapped_column(JSONB)
    mode: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class FindingEvidence(Base):
    __tablename__ = "finding_evidence"
    __table_args__ = (
        ForeignKeyConstraint(["project_id", "finding_id"], ["findings.project_id", "findings.id"]),
        ForeignKeyConstraint(
            ["project_id", "fragment_id"],
            ["feedback_fragments.project_id", "feedback_fragments.id"],
        ),
    )
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"), primary_key=True)
    finding_id: Mapped[UUID] = mapped_column(primary_key=True)
    fragment_id: Mapped[UUID] = mapped_column(primary_key=True)
