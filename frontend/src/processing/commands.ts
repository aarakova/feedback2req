import { useEffect, useRef, useState } from 'react';
import { ApiClient, ApiError, errorMessage } from '../api';
import { reasonMessage } from './adapters';
import type { RunDTO, StartCommand } from './dto';
import { uuidPattern } from './dto';
import { readPending, writePending } from './pending';
import type { PendingCommand } from './pending';
import { checkProject } from './reads';

// The only persisted data are command UUIDs/input refs, scoped by user and project.
// Neither original text nor credentials/CSRF/Run results are stored here.
export function useCommand(api: ApiClient, userId: string, projectId: string, onMissing: () => void) {
  const [restored] = useState(() => readPending(userId, projectId));
  const [command, setCommand] = useState<PendingCommand | null>(restored.command);
  const [warning, setWarning] = useState(restored.warning);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [code, setCode] = useState('');
  const controller = useRef<AbortController | null>(null);
  const locked = useRef(restored.command);
  useEffect(() => () => controller.current?.abort(), []);

  async function send(intent: PendingCommand): Promise<RunDTO | undefined> {
    if (controller.current) return;
    const current = new AbortController(); controller.current = current;
    locked.current = intent; setCommand(intent); setBusy(true); setError(''); setCode('');
    if (!writePending(userId, projectId, intent)) setWarning('Ключ доступен только в памяти. Хранилище вкладки недоступно; после reload восстановите историю перед новым действием.');
    try {
      const path = `/projects/${projectId}/${intent.kind === 'start' ? 'runs' : `units/${intent.unitId}/retries`}`;
      const result = await api.request<RunDTO>(path, { method: 'POST',
        body: intent.kind === 'start' ? intent.body : { expected_attempt_id: intent.expectedAttemptId },
        idempotencyKey: intent.key, expectedStatus: 202, signal: current.signal });
      if (current.signal.aborted) return;
      if (!uuidPattern.test(result.id) || !Array.isArray(result.units)) throw new Error('Unconfirmed command response');
      locked.current = null; setCommand(null); writePending(userId, projectId, null);
      return result;
    } catch (cause) {
      if (current.signal.aborted) return;
      const knownRejection = cause instanceof ApiError && [400, 401, 403, 404, 409, 413, 422, 429].includes(cause.status)
        && cause.code !== 'idempotency_conflict';
      if (knownRejection) {
        locked.current = null; setCommand(null); writePending(userId, projectId, null);
      }
      const reason = cause instanceof ApiError ? cause.code : '';
      setCode(reason);
      setError(['input_changed', 'invalid_input', 'idempotency_conflict', 'retry_not_allowed', 'retry_already_requested'].includes(reason)
        ? reasonMessage(reason) : errorMessage(cause));
      checkProject(cause, onMissing);
    } finally {
      if (controller.current === current) controller.current = null;
      if (!current.signal.aborted) setBusy(false);
    }
  }
  return { command, busy, error, code, warning,
    start: (body: StartCommand) => locked.current ? Promise.resolve(undefined) : send({ kind: 'start', body, key: crypto.randomUUID(), createdAt: new Date().toISOString() }),
    retry: (unitId: string, expectedAttemptId: string) => locked.current ? Promise.resolve(undefined)
      : send({ kind: 'retry', unitId, expectedAttemptId, key: crypto.randomUUID(), createdAt: new Date().toISOString() }),
    replay: () => locked.current ? send(locked.current) : Promise.resolve(undefined),
  };
}
