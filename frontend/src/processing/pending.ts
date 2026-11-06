import type { InputRef, StartCommand } from './dto';
import { INPUT_LIMIT, uuidPattern } from './dto';

const prefix = 'f2r.pending-run/';
export type PendingCommand = { key: string; createdAt: string } & (
  { kind: 'start'; body: StartCommand } | { kind: 'retry'; unitId: string; expectedAttemptId: string }
);
const keyFor = (userId: string, projectId: string) => `${prefix}${encodeURIComponent(userId)}/${projectId}`;
function record(value: unknown): value is Record<string, unknown> { return typeof value === 'object' && value !== null; }
function input(value: unknown): value is InputRef {
  return record(value) && (value.kind === 'source' || value.kind === 'document')
    && typeof value.id === 'string' && uuidPattern.test(value.id) && typeof value.state_id === 'string' && uuidPattern.test(value.state_id);
}
function valid(value: unknown): value is PendingCommand {
  if (!record(value) || typeof value.key !== 'string' || !uuidPattern.test(value.key) || typeof value.createdAt !== 'string') return false;
  if (value.kind === 'retry') return typeof value.unitId === 'string' && uuidPattern.test(value.unitId)
    && typeof value.expectedAttemptId === 'string' && uuidPattern.test(value.expectedAttemptId);
  if (value.kind !== 'start' || !record(value.body) || !['inspect_text', 'extract_feedback'].includes(String(value.body.operation))) return false;
  const inputs = value.body.inputs;
  return Array.isArray(inputs) && inputs.length > 0 && inputs.length <= INPUT_LIMIT && inputs.every(input)
    && (value.body.operation !== 'extract_feedback' || inputs.every(ref => ref.kind === 'source'))
    && new Set(inputs.map(ref => `${ref.kind}/${ref.id}`)).size === inputs.length;
}
export function readPending(userId: string, projectId: string): { command: PendingCommand | null; warning: string } {
  try {
    const raw = sessionStorage.getItem(keyFor(userId, projectId));
    if (!raw) return { command: null, warning: '' };
    const value: unknown = JSON.parse(raw);
    if (!valid(value)) return { command: null, warning: 'Сохранённое намерение повреждено. Проверьте историю перед новым запуском.' };
    return { command: value, warning: '' };
  } catch { return { command: null, warning: 'Хранилище вкладки недоступно. Сохранение ключа после перезагрузки не гарантируется.' }; }
}
export function writePending(userId: string, projectId: string, command: PendingCommand | null): boolean {
  try {
    if (command) sessionStorage.setItem(keyFor(userId, projectId), JSON.stringify(command));
    else sessionStorage.removeItem(keyFor(userId, projectId));
    return true;
  } catch { return false; }
}
export function clearPendingCommands() {
  try { for (const key of Object.keys(sessionStorage)) if (key.startsWith(prefix)) sessionStorage.removeItem(key); } catch { /* No text or credentials are stored. */ }
}
