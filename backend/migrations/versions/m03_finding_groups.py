"""M03: project-scoped finding groups; preserve all M02b extraction data."""

import sqlalchemy as sa
from alembic import op

revision = "m03"
down_revision = "m02b"
branch_labels = None
depends_on = None

DDL = (
    """CREATE TABLE finding_groups (
    id UUID NOT NULL,
    project_id UUID NOT NULL,
    current_state_id UUID NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    UNIQUE (project_id, id),
    FOREIGN KEY(project_id) REFERENCES projects (id)
    )
    """,
    """CREATE TABLE group_states (
    id UUID NOT NULL,
    project_id UUID NOT NULL,
    group_id UUID NOT NULL,
    previous_state_id UUID,
    title TEXT NOT NULL,
    summary TEXT NOT NULL,
    authorship VARCHAR(16) NOT NULL,
    author_id UUID,
    attempt_id UUID,
    local_id VARCHAR(256),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    UNIQUE (project_id, id),
    UNIQUE (project_id, group_id, id),
    UNIQUE (project_id, id, attempt_id),
    UNIQUE (attempt_id, local_id),
    FOREIGN KEY(project_id, group_id) REFERENCES finding_groups (project_id, id),
    FOREIGN KEY(project_id, group_id, previous_state_id) REFERENCES group_states
    (project_id, group_id, id),
    FOREIGN KEY(project_id, attempt_id) REFERENCES stage_attempts (project_id, id),
    CHECK (previous_state_id IS NULL OR previous_state_id <> id),
    CHECK (length(title)>0 AND length(summary)>0),
    CHECK ((authorship='ai' AND attempt_id IS NOT NULL AND local_id IS NOT NULL AND
    author_id IS NULL) OR (authorship='human' AND author_id IS NOT NULL AND
    previous_state_id IS NOT NULL) OR (authorship='ai_and_human' AND author_id IS NOT NULL
    AND attempt_id IS NOT NULL AND previous_state_id IS NOT NULL)),
    FOREIGN KEY(project_id) REFERENCES projects (id),
    FOREIGN KEY(author_id) REFERENCES users (id)
    )
    """,
    """CREATE TABLE group_scope (
    project_id UUID NOT NULL,
    group_state_id UUID NOT NULL,
    finding_id UUID NOT NULL,
    finding_state_id UUID NOT NULL,
    PRIMARY KEY (project_id, group_state_id, finding_id),
    UNIQUE (project_id, group_state_id, finding_id, finding_state_id),
    FOREIGN KEY(project_id, group_state_id) REFERENCES group_states (project_id, id),
    FOREIGN KEY(project_id, finding_id) REFERENCES findings (project_id, id),
    CHECK (finding_state_id=finding_id)
    )
    """,
    """CREATE TABLE group_members (
    project_id UUID NOT NULL,
    group_state_id UUID NOT NULL,
    finding_id UUID NOT NULL,
    finding_state_id UUID NOT NULL,
    PRIMARY KEY (project_id, group_state_id, finding_id),
    UNIQUE (project_id, group_state_id, finding_id, finding_state_id),
    FOREIGN KEY(project_id, group_state_id) REFERENCES group_states (project_id, id),
    FOREIGN KEY(project_id, finding_id) REFERENCES findings (project_id, id),
    FOREIGN KEY(project_id, group_state_id, finding_id, finding_state_id) REFERENCES
    group_scope (project_id, group_state_id, finding_id, finding_state_id),
    CHECK (finding_state_id=finding_id)
    )
    """,
    """CREATE TABLE group_context (
    project_id UUID NOT NULL,
    group_state_id UUID NOT NULL,
    document_id UUID NOT NULL,
    document_state_id UUID NOT NULL,
    start BIGINT NOT NULL,
    "end" BIGINT NOT NULL,
    PRIMARY KEY (project_id, group_state_id, document_id, document_state_id, start, "end"),
    FOREIGN KEY(project_id, group_state_id) REFERENCES group_states (project_id, id),
    FOREIGN KEY(project_id, document_id, document_state_id) REFERENCES document_states
    (project_id, document_id, id),
    CHECK (start >= 0 AND "end" > start)
    )
    """,
    """CREATE TABLE group_conflicts (
    id UUID NOT NULL,
    project_id UUID NOT NULL,
    group_state_id UUID NOT NULL,
    attempt_id UUID NOT NULL,
    local_id VARCHAR(256) NOT NULL,
    description TEXT NOT NULL,
    PRIMARY KEY (id),
    UNIQUE (project_id, group_state_id, id),
    UNIQUE (attempt_id, local_id),
    FOREIGN KEY(project_id, group_state_id, attempt_id) REFERENCES group_states (project_id,
    id, attempt_id),
    CHECK (length(description)>0)
    )
    """,
    """CREATE TABLE conflict_positions (
    id UUID NOT NULL,
    project_id UUID NOT NULL,
    group_state_id UUID NOT NULL,
    conflict_id UUID NOT NULL,
    ordinal INTEGER NOT NULL,
    description TEXT NOT NULL,
    PRIMARY KEY (id),
    UNIQUE (project_id, group_state_id, id),
    UNIQUE (project_id, group_state_id, conflict_id, ordinal),
    FOREIGN KEY(project_id, group_state_id, conflict_id) REFERENCES group_conflicts
    (project_id, group_state_id, id),
    CHECK (ordinal>=0 AND length(description)>0)
    )
    """,
    """CREATE TABLE position_members (
    project_id UUID NOT NULL,
    position_id UUID NOT NULL,
    finding_id UUID NOT NULL,
    group_state_id UUID NOT NULL,
    finding_state_id UUID NOT NULL,
    PRIMARY KEY (project_id, position_id, finding_id),
    FOREIGN KEY(project_id, group_state_id, position_id) REFERENCES conflict_positions
    (project_id, group_state_id, id),
    FOREIGN KEY(project_id, group_state_id, finding_id, finding_state_id) REFERENCES
    group_members (project_id, group_state_id, finding_id, finding_state_id)
    )
    """,
    """CREATE TABLE grouping_inputs (
    project_id UUID NOT NULL,
    unit_id UUID NOT NULL,
    key VARCHAR(256) NOT NULL,
    finding_id UUID NOT NULL,
    finding_state_id UUID NOT NULL,
    PRIMARY KEY (project_id, unit_id, key),
    UNIQUE (project_id, unit_id, finding_id),
    FOREIGN KEY(project_id, unit_id) REFERENCES processing_units (project_id, id),
    FOREIGN KEY(project_id, finding_id) REFERENCES findings (project_id, id),
    CHECK (finding_state_id=finding_id)
    )
    """,
    """CREATE TABLE grouping_documents (
    project_id UUID NOT NULL,
    unit_id UUID NOT NULL,
    key VARCHAR(256) NOT NULL,
    document_id UUID NOT NULL,
    document_state_id UUID NOT NULL,
    start BIGINT NOT NULL,
    "end" BIGINT NOT NULL,
    PRIMARY KEY (project_id, unit_id, key),
    FOREIGN KEY(project_id, unit_id) REFERENCES processing_units (project_id, id),
    FOREIGN KEY(project_id, document_id, document_state_id) REFERENCES document_states
    (project_id, document_id, id),
    UNIQUE (project_id, unit_id, document_id, document_state_id, start, "end"),
    CHECK (start >= 0 AND "end" > start)
    )
    """,
    """CREATE TABLE grouping_previous_groups (
    project_id UUID NOT NULL,
    unit_id UUID NOT NULL,
    key VARCHAR(256) NOT NULL,
    group_id UUID NOT NULL,
    group_state_id UUID NOT NULL,
    PRIMARY KEY (project_id, unit_id, key),
    FOREIGN KEY(project_id, unit_id) REFERENCES processing_units (project_id, id),
    FOREIGN KEY(project_id, group_id, group_state_id) REFERENCES group_states (project_id,
    group_id, id),
    UNIQUE (project_id, unit_id, group_id)
    )
    """,
    """ALTER TABLE finding_groups ADD CONSTRAINT fk_group_current FOREIGN KEY(project_id, id,
    current_state_id) REFERENCES group_states (project_id, group_id, id) DEFERRABLE
    INITIALLY DEFERRED
    """,
)


def upgrade():
    # M02b used unnamed CHECKs. Resolve their names by expression instead of
    # assuming PostgreSQL's generated name (which may differ after restoration).
    bind = op.get_bind()
    for table, needle in (("processing_runs", "operation"), ("processing_units", "source_id")):
        checks = sa.inspect(bind).get_check_constraints(table)
        for check in checks:
            if needle in check["sqltext"]:
                op.drop_constraint(check["name"], table, type_="check")
    op.add_column("processing_units", sa.Column("input_kind", sa.String(16), nullable=True))
    op.execute(
        "UPDATE processing_units SET input_kind=CASE WHEN source_id IS NOT NULL "
        "THEN 'source' ELSE 'document' END"
    )
    op.alter_column("processing_units", "input_kind", nullable=False)
    op.add_column(
        "stage_attempts",
        sa.Column("ungrouped_findings", sa.dialects.postgresql.JSONB(), nullable=True),
    )
    op.add_column("stage_attempts", sa.Column("grouping_owner_hash", sa.String(64), nullable=True))
    op.create_check_constraint(
        "ck_run_operation_f2",
        "processing_runs",
        "operation IN ('inspect_text','extract_feedback','group_findings')",
    )
    op.create_check_constraint(
        "ck_unit_input_f2",
        "processing_units",
        "(input_kind='source' AND source_id IS NOT NULL AND source_state_id IS NOT NULL "
        "AND document_id IS NULL AND document_state_id IS NULL) OR "
        "(input_kind='document' AND document_id IS NOT NULL AND document_state_id IS NOT NULL "
        "AND source_id IS NULL AND source_state_id IS NULL) OR "
        "(input_kind='finding_set' AND source_id IS NULL AND source_state_id IS NULL "
        "AND document_id IS NULL AND document_state_id IS NULL)",
    )
    for statement in DDL:
        op.execute(statement)
    # Cross-row cardinalities cannot be expressed as CHECK or ordinary FK.
    # Defer them so a whole accepted state can be built in one transaction.
    op.execute("""
        CREATE FUNCTION check_group_structure() RETURNS trigger
        LANGUAGE plpgsql SET search_path FROM CURRENT AS $$
        DECLARE sid uuid;
        BEGIN
          FOREACH sid IN ARRAY ARRAY[
            COALESCE(to_jsonb(NEW)->>'group_state_id',to_jsonb(NEW)->>'id')::uuid,
            COALESCE(to_jsonb(OLD)->>'group_state_id',to_jsonb(OLD)->>'id')::uuid
          ] LOOP
            IF sid IS NULL OR NOT EXISTS(SELECT 1 FROM group_states WHERE id=sid) THEN
              CONTINUE;
            END IF;
            PERFORM 1 FROM group_states WHERE id=sid FOR UPDATE;
            IF NOT EXISTS(SELECT 1 FROM group_members WHERE group_state_id=sid) THEN
              RAISE EXCEPTION 'Group requires members' USING ERRCODE='23514';
            END IF;
            IF EXISTS(
              SELECT 1 FROM group_conflicts c WHERE c.group_state_id=sid AND
              (SELECT count(*) FROM conflict_positions p
               WHERE p.group_state_id=sid AND p.conflict_id=c.id)<2
            ) THEN
              RAISE EXCEPTION 'Conflict requires positions' USING ERRCODE='23514';
            END IF;
            IF EXISTS(
              SELECT 1 FROM conflict_positions p WHERE p.group_state_id=sid AND
              NOT EXISTS(SELECT 1 FROM position_members m
                         WHERE m.group_state_id=sid AND m.position_id=p.id)
            ) THEN
              RAISE EXCEPTION 'Position requires members' USING ERRCODE='23514';
            END IF;
          END LOOP;
          RETURN NULL;
        END $$
    """)
    for table in (
        "group_states",
        "group_members",
        "group_scope",
        "group_conflicts",
        "conflict_positions",
        "position_members",
    ):
        op.execute(f"""
            CREATE CONSTRAINT TRIGGER ck_{table}_structure
            AFTER INSERT OR UPDATE OR DELETE ON {table}
            DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
            EXECUTE FUNCTION check_group_structure()
        """)
    op.execute("""
        CREATE FUNCTION check_grouping_input() RETURNS trigger
        LANGUAGE plpgsql SET search_path FROM CURRENT AS $$
        DECLARE uid uuid;
        BEGIN
          FOREACH uid IN ARRAY ARRAY[
            COALESCE(to_jsonb(NEW)->>'unit_id',to_jsonb(NEW)->>'id')::uuid,
            COALESCE(to_jsonb(OLD)->>'unit_id',to_jsonb(OLD)->>'id')::uuid
          ] LOOP
            IF EXISTS(SELECT 1 FROM processing_units u JOIN processing_runs r
              ON r.project_id=u.project_id AND r.id=u.run_id WHERE u.id=uid AND
              ((u.input_kind='finding_set' AND
                (r.operation<>'group_findings' OR NOT EXISTS(
                   SELECT 1 FROM grouping_inputs i WHERE i.unit_id=uid))) OR
               (u.input_kind<>'finding_set' AND r.operation='group_findings')))
            THEN
              RAISE EXCEPTION 'Invalid grouping input set' USING ERRCODE='23514';
            END IF;
          END LOOP;
          RETURN NULL;
        END $$
    """)
    for table in ("processing_units", "grouping_inputs"):
        op.execute(f"""
            CREATE CONSTRAINT TRIGGER ck_{table}_grouping_input
            AFTER INSERT OR UPDATE OR DELETE ON {table}
            DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
            EXECUTE FUNCTION check_grouping_input()
        """)


def downgrade():
    raise RuntimeError("F2 downgrade is intentionally unsupported: preserve accepted groups")
