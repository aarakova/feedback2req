import { useEffect, useState } from 'react';
import { ApiClient, errorMessage } from '../api';
import { activeRun } from './dto';
import type { RunDTO } from './dto';
import { checkProject } from './reads';

const POLL_LIMIT = 60;
const POLL_INTERVAL_MS = 2000;
export function useRun(api: ApiClient, projectId: string, runId: string | undefined, onMissing: () => void) {
  const key = `${projectId}/${runId ?? ''}`;
  const [revision, setRevision] = useState(0);
  const [result, setResult] = useState<{ key: string; run?: RunDTO; loading: boolean; error: string; paused: boolean }>({ key, loading: !!runId, error: '', paused: false });
  useEffect(() => {
    const controller = new AbortController(); let timer: ReturnType<typeof setTimeout> | undefined;
    let polls = 0; let failures = 0;
    setResult({ key, loading: !!runId, error: '', paused: false });
    async function read() {
      if (!runId || controller.signal.aborted) return;
      try {
        const run = await api.request<RunDTO>(`/projects/${projectId}/runs/${runId}`, { signal: controller.signal });
        if (controller.signal.aborted) return;
        if (run.id !== runId) throw new Error('Unexpected run response');
        failures = 0; polls++;
        const paused = activeRun(run) && polls >= POLL_LIMIT;
        setResult({ key, run, loading: false, error: '', paused });
        if (activeRun(run) && !paused) timer = setTimeout(read, POLL_INTERVAL_MS);
      } catch (cause) {
        if (controller.signal.aborted) return;
        failures++;
        setResult(previous => ({ key, run: previous.key === key ? previous.run : undefined, loading: false,
          error: errorMessage(cause), paused: failures >= 3 }));
        checkProject(cause, onMissing);
        // Temporary server/network failures get a bounded backoff; 401/404 do not loop.
        const status = typeof cause === 'object' && cause && 'status' in cause ? Number(cause.status) : 0;
        if (failures < 3 && (status === 0 || status >= 500)) timer = setTimeout(read, failures * 5000);
      }
    }
    void read();
    return () => { controller.abort(); if (timer) clearTimeout(timer); };
  }, [api, projectId, runId, revision, key, onMissing]);
  return { run: result.key === key ? result.run : undefined, loading: !!runId && (result.key !== key || result.loading),
    error: result.key === key ? result.error : '', paused: result.key === key && result.paused,
    refresh: () => setRevision(value => value + 1) };
}
