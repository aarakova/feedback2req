from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
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
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("length(login) BETWEEN 1 AND 128", name="login_length"),)
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    login: Mapped[str] = mapped_column(String(128), unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Session(Base):
    __tablename__ = "sessions"
    __table_args__ = (
        CheckConstraint("expires_at > created_at", name="session_expiry"),
        CheckConstraint("last_seen_at >= created_at", name="session_seen"),
        CheckConstraint("length(token_hash) = 64", name="session_hash_length"),
        Index("ix_sessions_user_id", "user_id"),
    )
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    csrf_secret: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = (
        CheckConstraint("length(trim(name)) BETWEEN 1 AND 200", name="project_name_length"),
        CheckConstraint("execution_mode IN ('mock', 'real')", name="project_execution_mode"),
        Index("ix_projects_owner_id", "owner_id"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(200))
    execution_mode: Mapped[str] = mapped_column(String(8), default="mock")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ProjectAccess(Base):
    __tablename__ = "project_access"
    __table_args__ = (Index("ix_project_access_user_id", "user_id"),)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), primary_key=True)
    can_approve: Mapped[bool] = mapped_column(Boolean, default=False)


class FeedbackSource(Base):
    __tablename__ = "feedback_sources"
    __table_args__ = (
        UniqueConstraint("project_id", "id", name="uq_source_project_id"),
        ForeignKeyConstraint(
            ["project_id", "id", "current_state_id"],
            [
                "source_text_states.project_id",
                "source_text_states.source_id",
                "source_text_states.id",
            ],
            name="fk_source_current_state",
            deferrable=True,
            initially="DEFERRED",
            use_alter=True,
        ),
        CheckConstraint("kind = 'text'", name="source_kind"),
        CheckConstraint("availability = 'available'", name="source_availability"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"))
    kind: Mapped[str] = mapped_column(String(8))
    current_state_id: Mapped[UUID] = mapped_column()
    availability: Mapped[str] = mapped_column(String(16), default="available")


class SourceTextState(Base):
    __tablename__ = "source_text_states"
    __table_args__ = (
        UniqueConstraint("project_id", "id", name="uq_source_state_project_id"),
        UniqueConstraint("project_id", "source_id", "id", name="uq_source_state_owner"),
        ForeignKeyConstraint(
            ["project_id", "source_id"],
            ["feedback_sources.project_id", "feedback_sources.id"],
            name="fk_source_state_source",
        ),
        CheckConstraint("length(text) > 0", name="source_text_nonempty"),
        CheckConstraint("origin = 'human'", name="source_state_origin"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"))
    source_id: Mapped[UUID] = mapped_column()
    text: Mapped[str] = mapped_column(Text)
    author_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    origin: Mapped[str] = mapped_column(String(16), default="human")


class ProductDocument(Base):
    __tablename__ = "product_documents"
    __table_args__ = (
        UniqueConstraint("project_id", "id", name="uq_document_project_id"),
        ForeignKeyConstraint(
            ["project_id", "id", "current_state_id"],
            ["document_states.project_id", "document_states.document_id", "document_states.id"],
            name="fk_document_current_state",
            deferrable=True,
            initially="DEFERRED",
            use_alter=True,
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"))
    current_state_id: Mapped[UUID] = mapped_column()


class DocumentState(Base):
    __tablename__ = "document_states"
    __table_args__ = (
        UniqueConstraint("project_id", "id", name="uq_document_state_project_id"),
        UniqueConstraint("project_id", "document_id", "id", name="uq_document_state_owner"),
        ForeignKeyConstraint(
            ["project_id", "document_id"],
            ["product_documents.project_id", "product_documents.id"],
            name="fk_document_state_document",
        ),
        CheckConstraint("length(text) > 0", name="document_text_nonempty"),
        CheckConstraint("length(trim(title)) BETWEEN 1 AND 200", name="document_title_length"),
        CheckConstraint("origin = 'human'", name="document_state_origin"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"))
    document_id: Mapped[UUID] = mapped_column()
    title: Mapped[str] = mapped_column(String(200))
    text: Mapped[str] = mapped_column(Text)
    author_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    origin: Mapped[str] = mapped_column(String(16), default="human")
