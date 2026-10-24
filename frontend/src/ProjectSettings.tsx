import { useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { ApiClient, ApiError, errorMessage } from './api';
import type { Project } from './api';
import { ErrorNotice, Loading } from './ui';

export function ProjectSettings({ api, project, refreshToken, onUpdated, onUnavailable, onForbidden }: {
  api: ApiClient; project: Project; refreshToken: string; onUpdated: (project: Project) => void;
  onUnavailable: () => void; onForbidden: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState('');
  const [baseline, setBaseline] = useState('');
  const [conflict, setConflict] = useState<string | null>(null);
  const [busy, setBusy] = useState<'save' | 'verify' | null>(null);
  const [uncertain, setUncertain] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const active = useRef<{ controller: AbortController; sent: boolean } | null>(null);
  const editButton = useRef<HTMLButtonElement>(null);
  const path = `/projects/${project.id}`;

  useEffect(() => {
    // A focus/access recheck may interrupt a PATCH after its commit.
    const previous = active.current;
    if (previous?.sent) setUncertain(true);
    previous?.controller.abort(); active.current = null; setBusy(null);
    return () => { active.current?.controller.abort(); };
  }, [api, project.id, refreshToken]);

  function begin(work: 'save' | 'verify') {
    if (active.current) return null;
    const controller = new AbortController();
    const pending = { controller, sent: false };
    active.current = pending;
    setBusy(work); setError(''); setNotice('');
    return pending;
  }

  function finish(controller: AbortController) {
    if (!controller.signal.aborted && active.current?.controller === controller) {
      active.current = null; setBusy(null);
    }
  }

  function failed(cause: unknown, controller: AbortController) {
    if (controller.signal.aborted) return;
    setError(errorMessage(cause));
    if (cause instanceof ApiError && cause.status === 404) onUnavailable();
    if (cause instanceof ApiError && cause.status === 403 && cause.code === 'forbidden') onForbidden();
  }

  async function read(controller: AbortController) {
    const current = await api.request<Project>(path, { signal: controller.signal });
    if (controller.signal.aborted) return;
    if (current.id !== project.id || typeof current.name !== 'string') throw new Error('Unconfirmed project response');
    if (!current.permissions.is_owner) {
      onUpdated(current); onForbidden(); return;
    }
    return current;
  }

  async function save(event: FormEvent) {
    event.preventDefault();
    if (uncertain || active.current) return;
    if (!name.trim()) { setError('Введите непустое название проекта.'); return; }
    const pending = begin('save');
    if (!pending) return;
    const { controller } = pending;
    try {
      const current = await read(controller);
      if (!current || controller.signal.aborted) return;
      if (current.name !== baseline) {
        onUpdated(current); setBaseline(current.name); setConflict(current.name);
        return;
      }
      pending.sent = true;
      const saved = await api.request<Project>(path, {
        method: 'PATCH', body: { name }, signal: controller.signal,
      });
      if (controller.signal.aborted) return;
      if (saved.id !== project.id || typeof saved.name !== 'string') throw new Error('Unconfirmed rename response');
      pending.sent = false;
      onUpdated(saved); setEditing(false); setConflict(null);
      setNotice('Название проекта сохранено.'); requestAnimationFrame(() => editButton.current?.focus());
    } catch (cause) {
      if (!controller.signal.aborted && pending.sent && (!(cause instanceof ApiError) || cause.status >= 500)) {
        setUncertain(true);
      }
      failed(cause, controller);
    } finally { finish(controller); }
  }

  async function verify() {
    const pending = begin('verify');
    if (!pending) return;
    const { controller } = pending;
    try {
      const current = await read(controller);
      if (!current || controller.signal.aborted) return;
      onUpdated(current); setBaseline(current.name); setConflict(null); setUncertain(false);
      setNotice(`Текущее название: ${current.name}. Это состояние на момент проверки, а не подтверждение результата предыдущего запроса.`);
    } catch (cause) { failed(cause, controller); }
    finally { finish(controller); }
  }

  return <section className="panel project-settings stack" aria-labelledby="project-settings-heading">
    <h2 id="project-settings-heading">Настройки проекта</h2>
    <p className="muted">Название проекта</p>
    {!editing && <button ref={editButton} className="secondary" onClick={() => {
      setName(project.name); setBaseline(project.name); setConflict(null);
      setError(''); setNotice(''); setEditing(true);
    }}>Изменить название</button>}
    {editing && <form className="stack" aria-label="Переименование проекта" onSubmit={save}>
      <label>Новое название проекта<input autoFocus required autoComplete="off" name="project_name"
        value={name} disabled={busy !== null || uncertain} onChange={event => setName(event.target.value)} /></label>
      <p className="muted small">До 200 символов. Пробелы по краям не сохраняются.</p>
      {conflict !== null && <div className="uncertain-notice stack" role="group" aria-label="Конкурентное изменение названия">
        <p>Название изменено в другой сессии: <span className="project-name">{conflict}</span>.
          Ваш вариант сохранён в форме. Выберите текущее название или явно сохраните своё.</p>
        <button type="button" className="secondary" disabled={busy !== null || uncertain} onClick={() => {
          setName(conflict); setBaseline(conflict); setConflict(null); setError('');
        }}>Использовать текущее название</button>
      </div>}
      <p className="muted small">Если название изменят одновременно после проверки, сохранение заменит его вашим вариантом.</p>
      <div className="actions">
        <button className="primary" disabled={busy !== null || uncertain}>{conflict !== null ? 'Сохранить моё название' : 'Сохранить название'}</button>
        <button type="button" className="secondary" disabled={busy !== null || uncertain} onClick={() => {
          setEditing(false); setConflict(null); setError(''); requestAnimationFrame(() => editButton.current?.focus());
        }}>Отменить переименование</button>
      </div>
    </form>}
    {error && <ErrorNotice message={error} />}
    {notice && <p className="success-notice" role="status">{notice}</p>}
    {uncertain && <div className="uncertain-notice stack" role="group" aria-label="Неизвестный результат переименования">
      <p>Результат переименования неизвестен: сервер мог сохранить название.
        Автоматического повтора нет. Проверьте текущее название перед новым действием.</p>
      <button className="secondary" disabled={busy !== null} onClick={verify}>Проверить текущее название</button>
    </div>}
    {busy && <Loading>{busy === 'save' ? 'Проверяем и сохраняем название…' : 'Проверяем текущее название…'}</Loading>}
  </section>;
}
