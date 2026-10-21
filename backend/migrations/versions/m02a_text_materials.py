"""M02a: only entered text materials and their initial states."""

import sqlalchemy as sa
from alembic import op

revision = "m02a"
down_revision = "m01"
branch_labels = None
depends_on = None


def upgrade():
    for table, prefix in [("feedback_sources", "source"), ("product_documents", "document")]:
        extra = []
        if prefix == "source":
            extra = [
                sa.Column("kind", sa.String(8), nullable=False),
                sa.Column("availability", sa.String(16), nullable=False),
                sa.CheckConstraint("kind = 'text'", name="source_kind"),
                sa.CheckConstraint("availability = 'available'", name="source_availability"),
            ]
        op.create_table(
            table,
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
            sa.Column("current_state_id", sa.Uuid(), nullable=False),
            sa.UniqueConstraint("project_id", "id", name=f"uq_{prefix}_project_id"),
            *extra,
        )
    for table, parent, prefix in [
        ("source_text_states", "feedback_sources", "source"),
        ("document_states", "product_documents", "document"),
    ]:
        extra = []
        if prefix == "document":
            extra = [
                sa.Column("title", sa.String(200), nullable=False),
                sa.CheckConstraint(
                    "length(trim(title)) BETWEEN 1 AND 200", name="document_title_length"
                ),
            ]
        op.create_table(
            table,
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
            sa.Column(f"{prefix}_id", sa.Uuid(), nullable=False),
            sa.Column("text", sa.Text(), nullable=False),
            sa.Column("author_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column("origin", sa.String(16), nullable=False),
            sa.UniqueConstraint("project_id", "id", name=f"uq_{prefix}_state_project_id"),
            sa.UniqueConstraint(
                "project_id", f"{prefix}_id", "id", name=f"uq_{prefix}_state_owner"
            ),
            sa.ForeignKeyConstraint(
                ["project_id", f"{prefix}_id"],
                [f"{parent}.project_id", f"{parent}.id"],
                name=f"fk_{prefix}_state_{prefix}",
            ),
            sa.CheckConstraint("length(text) > 0", name=f"{prefix}_text_nonempty"),
            sa.CheckConstraint("origin = 'human'", name=f"{prefix}_state_origin"),
            *extra,
        )
        op.create_foreign_key(
            f"fk_{prefix}_current_state",
            parent,
            table,
            ["project_id", "id", "current_state_id"],
            ["project_id", f"{prefix}_id", "id"],
            deferrable=True,
            initially="DEFERRED",
        )


def downgrade():
    raise RuntimeError("M02a downgrade is unavailable; use a disposable test database")
