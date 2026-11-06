"""Upgrade real pre-F2 rows without using the new ORM to seed the old schema."""

from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from .conftest import isolated_database


def test_m02b_upgrade_preserves_complete_extraction_graph():
    with isolated_database("m02b") as url:
        engine = create_engine(url, hide_parameters=True)
        ids = {
            k: uuid4()
            for k in (
                "user",
                "project",
                "source",
                "source_state",
                "run",
                "unit",
                "attempt",
                "fragment",
                "finding",
                "key",
                "request",
            )
        }
        statements = [
            "INSERT INTO users(id,login,password_hash) VALUES(:user,'legacy','test-placeholder')",
            "INSERT INTO projects(id,owner_id,name,execution_mode) "
            "VALUES(:project,:user,'legacy','mock')",
            """INSERT INTO feedback_sources(id,project_id,current_state_id,kind,availability)
               VALUES(:source,:project,:source_state,'text','available')""",
            """INSERT INTO source_text_states(id,project_id,source_id,text,author_id,origin)
               VALUES(:source_state,:project,:source,'ё🙂',:user,'human')""",
            """INSERT INTO processing_runs(id,project_id,initiated_by,operation,command_kind,
               idempotency_key,fingerprint)
               VALUES(:run,:project,:user,'extract_feedback','start',:key,repeat('a',64))""",
            """INSERT INTO processing_units(id,project_id,run_id,source_id,source_state_id,state)
               VALUES(:unit,:project,:run,:source,:source_state,'completed')""",
            """INSERT INTO stage_attempts(id,project_id,unit_id,request_id,state,started_at,
               deadline_at,finished_at,provider,model,synthetic,ai_performed,coverage,annotations)
               VALUES(:attempt,:project,:unit,:request,'completed',now(),
               now()+interval '120 seconds',now(),'test','legacy',true,false,'[]','{}')""",
            """INSERT INTO feedback_fragments(id,project_id,attempt_id,local_id,source_id,
               source_state_id,quote,start,"end",reliability)
               VALUES(:fragment,:project,:attempt,'fragment',:source,:source_state,'ё🙂',0,2,'usable')""",
            """INSERT INTO findings(id,project_id,attempt_id,local_id,text,types,mode)
               VALUES(:finding,:project,:attempt,'finding','legacy finding','["need"]','direct')""",
            """INSERT INTO finding_evidence(project_id,finding_id,fragment_id)
               VALUES(:project,:finding,:fragment)""",
        ]
        tables = [
            "users",
            "projects",
            "feedback_sources",
            "source_text_states",
            "processing_runs",
            "processing_units",
            "stage_attempts",
            "feedback_fragments",
            "findings",
            "finding_evidence",
        ]
        try:
            with engine.begin() as conn:
                for sql in statements:
                    conn.execute(text(sql), ids)
                before = {
                    table: [
                        dict(row) for row in conn.execute(text(f"SELECT * FROM {table}")).mappings()
                    ]
                    for table in tables
                }
            cfg = Config(str(Path(__file__).parents[1] / "alembic.ini"))
            cfg.attributes["database_url"] = url
            command.upgrade(cfg, "head")
            with engine.begin() as conn:
                for table in tables:
                    after = [
                        dict(row) for row in conn.execute(text(f"SELECT * FROM {table}")).mappings()
                    ]
                    original_columns = before[table][0].keys()
                    assert [{k: row[k] for k in original_columns} for row in after] == before[table]
                assert conn.scalar(text("SELECT input_kind FROM processing_units")) == "source"
                assert conn.scalar(text("SELECT count(*) FROM finding_groups")) == 0
                assert conn.scalar(text("SELECT version_num FROM alembic_version")) == "m03"
                assert "grouping_owner_hash" in {
                    c["name"] for c in inspect(conn).get_columns("stage_attempts")
                }
        finally:
            engine.dispose()
