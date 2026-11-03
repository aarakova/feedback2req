"""M02b: durable processing and immutable accepted extraction outputs."""

from alembic import op

revision = "m02b"
down_revision = "m02a"
branch_labels = None
depends_on = None

DDL = (
    """CREATE TABLE processing_runs (
        id UUID NOT NULL,
        project_id UUID NOT NULL,
        initiated_by UUID NOT NULL,
        operation VARCHAR(32) NOT NULL,
        command_kind VARCHAR(8) NOT NULL,
        idempotency_key UUID NOT NULL,
        fingerprint VARCHAR(64) NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
        PRIMARY KEY (id),
        UNIQUE (project_id, id),
        UNIQUE (project_id, initiated_by, command_kind, idempotency_key),
        CHECK (operation IN ('inspect_text','extract_feedback')),
        CHECK (command_kind IN ('start','retry')),
        CHECK (length(fingerprint) = 64),
        FOREIGN KEY(project_id) REFERENCES projects (id),
        FOREIGN KEY(initiated_by) REFERENCES users (id)
)""",
    """CREATE TABLE processing_units (
        id UUID NOT NULL,
        project_id UUID NOT NULL,
        run_id UUID NOT NULL,
        source_id UUID,
        source_state_id UUID,
        document_id UUID,
        document_state_id UUID,
        retry_of_attempt_id UUID,
        state VARCHAR(16) NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
        PRIMARY KEY (id),
        UNIQUE (project_id, id),
        UNIQUE (run_id, source_id),
        UNIQUE (run_id, document_id),
        UNIQUE (retry_of_attempt_id),
        FOREIGN KEY(project_id, run_id) REFERENCES processing_runs (project_id, id),
        FOREIGN KEY(project_id, source_id, source_state_id) REFERENCES source_text_states
(project_id, source_id, id),
        FOREIGN KEY(project_id, document_id, document_state_id) REFERENCES document_states
(project_id, document_id, id),
        CHECK ((source_id IS NOT NULL AND source_state_id IS NOT NULL AND document_id IS NULL
AND document_state_id IS NULL) OR (document_id IS NOT NULL AND document_state_id IS NOT NULL
AND source_id IS NULL AND source_state_id IS NULL)),
        CHECK (state IN ('queued','running','completed','failed','cancelled')),
        FOREIGN KEY(project_id) REFERENCES projects (id)
)""",
    """CREATE INDEX ix_units_run ON processing_units (project_id, run_id, id)""",
    """CREATE INDEX ix_units_queue ON processing_units (state, created_at, id)""",
    """CREATE TABLE stage_attempts (
        id UUID NOT NULL,
        project_id UUID NOT NULL,
        unit_id UUID NOT NULL,
        request_id UUID NOT NULL,
        state VARCHAR(16) NOT NULL,
        owner_token UUID,
        started_at TIMESTAMP WITH TIME ZONE NOT NULL,
        deadline_at TIMESTAMP WITH TIME ZONE NOT NULL,
        lease_expires_at TIMESTAMP WITH TIME ZONE,
        finished_at TIMESTAMP WITH TIME ZONE,
        reason_code VARCHAR(32),
        provider VARCHAR(64),
        model VARCHAR(128),
        synthetic BOOLEAN NOT NULL,
        ai_performed BOOLEAN,
        coverage JSONB,
        annotations JSONB,
        character_count BIGINT,
        utf8_byte_count BIGINT,
        PRIMARY KEY (id),
        UNIQUE (project_id, id),
        UNIQUE (unit_id),
        FOREIGN KEY(project_id, unit_id) REFERENCES processing_units (project_id, id),
        CHECK (state IN ('running','completed','failed','cancelled')),
        CHECK (deadline_at > started_at),
        CHECK (finished_at IS NULL OR finished_at >= started_at),
        CHECK (character_count IS NULL OR character_count > 0),
        CHECK (utf8_byte_count IS NULL OR utf8_byte_count >= character_count),
        CHECK ((state='running' AND owner_token IS NOT NULL AND lease_expires_at IS NOT NULL
AND finished_at IS NULL AND reason_code IS NULL) OR (state<>'running' AND owner_token IS NULL
AND lease_expires_at IS NULL AND finished_at IS NOT NULL)),
        CHECK (lease_expires_at IS NULL OR lease_expires_at <= deadline_at),
        CHECK ((state='completed' AND reason_code IS NULL) OR state='running' OR (state IN
('failed','cancelled') AND reason_code IS NOT NULL)),
        FOREIGN KEY(project_id) REFERENCES projects (id),
        UNIQUE (request_id)
)""",
    """CREATE INDEX ix_attempts_lease ON stage_attempts (lease_expires_at)""",
    """CREATE TABLE feedback_fragments (
        id UUID NOT NULL,
        project_id UUID NOT NULL,
        attempt_id UUID NOT NULL,
        local_id VARCHAR(256) NOT NULL,
        source_id UUID NOT NULL,
        source_state_id UUID NOT NULL,
        quote TEXT NOT NULL,
        start BIGINT NOT NULL,
        "end" BIGINT NOT NULL,
        reliability VARCHAR(16) NOT NULL,
        PRIMARY KEY (id),
        UNIQUE (project_id, id),
        UNIQUE (attempt_id, local_id),
        FOREIGN KEY(project_id, attempt_id) REFERENCES stage_attempts (project_id, id),
        FOREIGN KEY(project_id, source_id, source_state_id) REFERENCES source_text_states
(project_id, source_id, id),
        CHECK (start >= 0 AND "end" > start),
        CHECK (reliability IN ('usable','uncertain')),
        CHECK (length(quote) = "end" - start),
        FOREIGN KEY(project_id) REFERENCES projects (id)
)""",
    """CREATE TABLE findings (
        id UUID NOT NULL,
        project_id UUID NOT NULL,
        attempt_id UUID NOT NULL,
        local_id VARCHAR(256) NOT NULL,
        text TEXT NOT NULL,
        types JSONB NOT NULL,
        mode VARCHAR(16) NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
        PRIMARY KEY (id),
        UNIQUE (project_id, id),
        UNIQUE (attempt_id, local_id),
        FOREIGN KEY(project_id, attempt_id) REFERENCES stage_attempts (project_id, id),
        CHECK (mode IN ('direct','inferred')),
        CHECK (length(text) > 0),
        CHECK (jsonb_typeof(types)='array' AND jsonb_array_length(types)>0 AND types <@
'["problem","request","observation","need"]'::jsonb),
        FOREIGN KEY(project_id) REFERENCES projects (id)
)""",
    """CREATE TABLE finding_evidence (
        project_id UUID NOT NULL,
        finding_id UUID NOT NULL,
        fragment_id UUID NOT NULL,
        PRIMARY KEY (project_id, finding_id, fragment_id),
        FOREIGN KEY(project_id, finding_id) REFERENCES findings (project_id, id),
        FOREIGN KEY(project_id, fragment_id) REFERENCES feedback_fragments (project_id, id),
        FOREIGN KEY(project_id) REFERENCES projects (id)
)""",
    """ALTER TABLE processing_units ADD CONSTRAINT fk_unit_retry FOREIGN KEY(project_id,
retry_of_attempt_id) REFERENCES stage_attempts (project_id, id)""",
)


def upgrade():
    for statement in DDL:
        op.execute(statement)


def downgrade():
    raise RuntimeError("M02b downgrade is unavailable; use a disposable test database")
