"""Project-scoped groups and typed immutable grouping dependencies (DEC-016)."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from feedback2req.persistence.models import Base


def fk(local, target, remote=None, **kwargs):
    """All dependency keys include their project; never a UUID-only link."""
    return ForeignKeyConstraint(
        ["project_id", *local],
        [f"{target}.{key}" for key in ["project_id", *(remote or local)]],
        **kwargs,
    )


class FindingGroup(Base):
    __tablename__ = "finding_groups"
    __table_args__ = (
        UniqueConstraint("project_id", "id"),
        fk(
            ["id", "current_state_id"],
            "group_states",
            ["group_id", "id"],
            name="fk_group_current",
            deferrable=True,
            initially="DEFERRED",
            use_alter=True,
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"))
    current_state_id: Mapped[UUID]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class GroupState(Base):
    __tablename__ = "group_states"
    __table_args__ = (
        UniqueConstraint("project_id", "id"),
        UniqueConstraint("project_id", "group_id", "id"),
        UniqueConstraint("project_id", "id", "attempt_id"),
        UniqueConstraint("attempt_id", "local_id"),
        fk(["group_id"], "finding_groups", ["id"]),
        fk(["group_id", "previous_state_id"], "group_states", ["group_id", "id"]),
        fk(["attempt_id"], "stage_attempts", ["id"]),
        CheckConstraint("previous_state_id IS NULL OR previous_state_id <> id"),
        CheckConstraint("length(title)>0 AND length(summary)>0"),
        CheckConstraint(
            "(authorship='ai' AND attempt_id IS NOT NULL AND local_id IS NOT NULL "
            "AND author_id IS NULL) OR (authorship='human' AND author_id IS NOT NULL "
            "AND previous_state_id IS NOT NULL) OR (authorship='ai_and_human' "
            "AND author_id IS NOT NULL AND attempt_id IS NOT NULL "
            "AND previous_state_id IS NOT NULL)"
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"))
    group_id: Mapped[UUID]
    previous_state_id: Mapped[UUID | None]
    title: Mapped[str] = mapped_column(Text)
    summary: Mapped[str] = mapped_column(Text)
    authorship: Mapped[str] = mapped_column(String(16))
    author_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    attempt_id: Mapped[UUID | None]
    local_id: Mapped[str | None] = mapped_column(String(256))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class GroupMember(Base):
    __tablename__ = "group_members"
    __table_args__ = (
        UniqueConstraint("project_id", "group_state_id", "finding_id", "finding_state_id"),
        fk(["group_state_id"], "group_states", ["id"]),
        fk(["finding_id"], "findings", ["id"]),
        fk(["group_state_id", "finding_id", "finding_state_id"], "group_scope"),
        CheckConstraint("finding_state_id=finding_id"),
    )
    project_id: Mapped[UUID] = mapped_column(primary_key=True)
    group_state_id: Mapped[UUID] = mapped_column(primary_key=True)
    finding_id: Mapped[UUID] = mapped_column(primary_key=True)
    finding_state_id: Mapped[UUID]


class GroupScope(Base):
    __tablename__ = "group_scope"
    __table_args__ = (
        UniqueConstraint("project_id", "group_state_id", "finding_id", "finding_state_id"),
        fk(["group_state_id"], "group_states", ["id"]),
        fk(["finding_id"], "findings", ["id"]),
        CheckConstraint("finding_state_id=finding_id"),
    )
    project_id: Mapped[UUID] = mapped_column(primary_key=True)
    group_state_id: Mapped[UUID] = mapped_column(primary_key=True)
    finding_id: Mapped[UUID] = mapped_column(primary_key=True)
    finding_state_id: Mapped[UUID]


class DocumentDependency:
    document_id: Mapped[UUID] = mapped_column(primary_key=True)
    document_state_id: Mapped[UUID] = mapped_column(primary_key=True)
    start: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    end: Mapped[int] = mapped_column(BigInteger, primary_key=True)


def document_fk():
    return fk(["document_id", "document_state_id"], "document_states", ["document_id", "id"])


class GroupContext(DocumentDependency, Base):
    __tablename__ = "group_context"
    __table_args__ = (
        fk(["group_state_id"], "group_states", ["id"]),
        document_fk(),
        CheckConstraint('start >= 0 AND "end" > start'),
    )
    project_id: Mapped[UUID] = mapped_column(primary_key=True)
    group_state_id: Mapped[UUID] = mapped_column(primary_key=True)


class GroupConflict(Base):
    __tablename__ = "group_conflicts"
    __table_args__ = (
        UniqueConstraint("project_id", "group_state_id", "id"),
        UniqueConstraint("attempt_id", "local_id"),
        fk(["group_state_id", "attempt_id"], "group_states", ["id", "attempt_id"]),
        CheckConstraint("length(description)>0"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    project_id: Mapped[UUID]
    group_state_id: Mapped[UUID]
    attempt_id: Mapped[UUID]
    local_id: Mapped[str] = mapped_column(String(256))
    description: Mapped[str] = mapped_column(Text)


class ConflictPosition(Base):
    __tablename__ = "conflict_positions"
    __table_args__ = (
        UniqueConstraint("project_id", "group_state_id", "id"),
        UniqueConstraint("project_id", "group_state_id", "conflict_id", "ordinal"),
        fk(["group_state_id", "conflict_id"], "group_conflicts", ["group_state_id", "id"]),
        CheckConstraint("ordinal>=0 AND length(description)>0"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    project_id: Mapped[UUID]
    group_state_id: Mapped[UUID]
    conflict_id: Mapped[UUID]
    ordinal: Mapped[int] = mapped_column(Integer)
    description: Mapped[str] = mapped_column(Text)


class PositionMember(Base):
    __tablename__ = "position_members"
    __table_args__ = (
        fk(["group_state_id", "position_id"], "conflict_positions", ["group_state_id", "id"]),
        fk(["group_state_id", "finding_id", "finding_state_id"], "group_members"),
    )
    project_id: Mapped[UUID] = mapped_column(primary_key=True)
    position_id: Mapped[UUID] = mapped_column(primary_key=True)
    finding_id: Mapped[UUID] = mapped_column(primary_key=True)
    group_state_id: Mapped[UUID]
    finding_state_id: Mapped[UUID]


class GroupingInput(Base):
    __tablename__ = "grouping_inputs"
    __table_args__ = (
        UniqueConstraint("project_id", "unit_id", "finding_id"),
        fk(["unit_id"], "processing_units", ["id"]),
        fk(["finding_id"], "findings", ["id"]),
        CheckConstraint("finding_state_id=finding_id"),
    )
    project_id: Mapped[UUID] = mapped_column(primary_key=True)
    unit_id: Mapped[UUID] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(256), primary_key=True)
    finding_id: Mapped[UUID]
    finding_state_id: Mapped[UUID]


class GroupingDocument(Base):
    __tablename__ = "grouping_documents"
    __table_args__ = (
        fk(["unit_id"], "processing_units", ["id"]),
        document_fk(),
        UniqueConstraint(
            "project_id", "unit_id", "document_id", "document_state_id", "start", "end"
        ),
        CheckConstraint('start >= 0 AND "end" > start'),
    )
    project_id: Mapped[UUID] = mapped_column(primary_key=True)
    unit_id: Mapped[UUID] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(256), primary_key=True)
    document_id: Mapped[UUID]
    document_state_id: Mapped[UUID]
    start: Mapped[int] = mapped_column(BigInteger)
    end: Mapped[int] = mapped_column(BigInteger)


class GroupingPreviousGroup(Base):
    __tablename__ = "grouping_previous_groups"
    __table_args__ = (
        fk(["unit_id"], "processing_units", ["id"]),
        fk(["group_id", "group_state_id"], "group_states", ["group_id", "id"]),
        UniqueConstraint("project_id", "unit_id", "group_id"),
    )
    project_id: Mapped[UUID] = mapped_column(primary_key=True)
    unit_id: Mapped[UUID] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(256), primary_key=True)
    group_id: Mapped[UUID]
    group_state_id: Mapped[UUID]
