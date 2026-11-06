"""Prepare owned PostgreSQL fixtures for stale-state/error UI tests, never production.

Commands use the real API; synthetic execution and terminal fault preparation are
test setup, not evidence that a real provider/lease/deadline fault occurred.
"""
import json
import os
from pathlib import Path
from uuid import UUID, uuid4

import httpx
from sqlalchemy import create_engine, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from backend.tests.test_processing import Synthetic
from feedback2req.config import Settings
from feedback2req.persistence.models import FeedbackSource, SourceTextState
from feedback2req.persistence.processing import Attempt, Unit
from feedback2req.processing import service
from feedback2req.processing.provider import ProviderError

raw = os.environ['F2R_DATABASE_URL']
assert make_url(raw).database == 'feedback2req_processing_f1_test'
engine = create_engine(raw, hide_parameters=True)
sessions = sessionmaker(engine, expire_on_commit=False)
settings = Settings(database_url=raw, local_http=True, processing_test_mode=True)


class Failed(Synthetic):
    def __init__(self, reason='provider_error'):
        self.reason = reason

    def extract(self, _request):
        raise ProviderError(self.reason)


with httpx.Client(base_url=os.environ['F1_TEST_API'], headers={'Origin': 'http://localhost:5173'}, trust_env=False) as client:
    login = 'f1-fixture-' + uuid4().hex
    credentials = {'login': login, 'password': 'frontend-test-only-2026'}
    assert client.post('/api/v1/auth/register', json=credentials).status_code == 201
    session = client.post('/api/v1/auth/session', json=credentials).json()
    client.headers['X-CSRF-Token'] = session['csrf_token']
    project = client.post('/api/v1/projects', json={'name': 'Синтетические состояния F1'}).json()
    root = '/api/v1/projects/' + project['id']
    source = client.post(root + '/sources', json={'kind': 'text', 'text': 'Историческая цитата ё🙂\r\n'}).json()

    def run(ref, provider):
        result = client.post(root + '/runs', headers={'Idempotency-Key': str(uuid4())}, json={
            'operation': 'extract_feedback', 'inputs': [{'kind': 'source', 'id': ref['id'], 'state_id': ref['state_id']}]})
        assert result.status_code == 202, result.status_code
        assert service.execute_one(sessions, settings, provider)
        return client.get(root + '/runs/' + result.json()['id']).json()

    completed = run(source, Synthetic())
    finding_id = completed['units'][0]['attempt']['finding_ids'][0]
    failed = run(source, Failed())
    with sessions.begin() as tx:
        header = tx.get(FeedbackSource, UUID(source['id']))
        assert header.project_id == UUID(project['id'])
        state = SourceTextState(id=uuid4(), project_id=header.project_id, source_id=header.id,
                                text='Новое состояние источника 🧭', author_id=UUID(session['user']['id']))
        tx.add(state)
        header.current_state_id = state.id
    cases = {}
    current = client.get(root + '/sources/' + source['id']).json()
    for reason in ['provider_not_configured', 'provider_error', 'invalid_response', 'execution_error',
                   'lease_expired', 'deadline_exceeded', 'input_changed', 'access_revoked']:
        value = run(current, Failed(reason))
        if reason in {'input_changed', 'access_revoked'}:
            with sessions.begin() as tx:
                unit = tx.get(Unit, UUID(value['units'][0]['id']))
                attempt = tx.scalar(select(Attempt).where(Attempt.unit_id == unit.id))
                service.end(tx, unit, attempt, 'cancelled', reason)
        cases[reason] = value['id']
    result = {'login': login, 'projectId': project['id'], 'source': source, 'current': current,
              'completedRunId': completed['id'], 'failedRunId': failed['id'], 'findingId': finding_id, 'reasons': cases}
    target = Path('/workspace/.local/frontend-f1/seed-manifest.json')
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, ensure_ascii=False), encoding='utf-8')
engine.dispose()
print('Prepared isolated synthetic stale-state and terminal-reason fixtures; no external AI calls.')
