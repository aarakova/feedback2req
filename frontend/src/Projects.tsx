import { useCallback, useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { ApiClient, errorMessage } from './api';
import type { Page, Project } from './api';
import { ErrorNotice, Loading, Permissions } from './ui';
import { Materials } from './Materials';
import type { MaterialSelection } from './Materials';
import { ProjectAccess } from './Access';

export function ProjectList({ api }: { api: ApiClient }) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [pageCursor, setPageCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [revision, setRevision] = useState(0);
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true); setError('');
    api.request<Page<Project>>(`/projects${pageCursor ? `?cursor=${encodeURIComponent(pageCursor)}` : ''}`,
      { signal: controller.signal }).then(page => {
      if (controller.signal.aborted) return;
      setProjects(previous => pageCursor ? [...previous, ...page.items.filter(item =>
        !previous.some(existing => existing.id === item.id))] : page.items);
      setCursor(page.next_cursor);
    }).catch(error => {
      if (!controller.signal.aborted) setError(errorMessage(error));
    }).finally(() => {
      if (!controller.signal.aborted) setLoading(false);
    });
    return () => controller.abort();
  }, [api, pageCursor, revision]);

  return <>
    <div className="page-heading">
      <div><p className="eyebrow">Рабочее пространство</p><h1>Ваши проекты</h1>
        <p className="muted">Выберите проект или создайте новый.</p></div>
      <button className="primary" onClick={() => setCreating(!creating)} aria-expanded={creating}>
        {creating ? 'Закрыть форму' : '+ Создать проект'}</button>
    </div>
    {creating && <CreateProject api={api} onCancel={() => setCreating(false)} />}
    <div className="section-heading"><h2>Доступные проекты</h2>
      <button className="secondary" disabled={loading} onClick={() => {
        setProjects([]); setCursor(null); setPageCursor(null); setRevision(n => n + 1);
      }}>Обновить список</button></div>
    {error && <div className="stack"><ErrorNotice message={error} />
      <button className="secondary retry" onClick={() => setRevision(n => n + 1)}>Повторить запрос</button></div>}
    {projects.length > 0 && <div className="project-grid">{projects.map(project =>
      <a key={project.id} href={`#/projects/${project.id}`} className="project-card panel">
        <div className="card-top"><span className="project-icon" aria-hidden="true">▤</span><span className="open-arrow" aria-hidden="true">↗</span></div>
        <h3>{project.name}</h3><Permissions project={project} />
        <span className="card-bottom">Открыть проект <span aria-hidden="true">→</span></span>
      </a>)}</div>}
    {loading && <Loading>Загружаем проекты…</Loading>}
    {!loading && !error && projects.length === 0 && <section className="empty panel">
      <span className="empty-icon" aria-hidden="true">▤</span><h2>Пока нет доступных проектов</h2>
      <p className="muted">Создайте свой проект. Для доступа к чужому проекту обратитесь к его владельцу.</p>
      <button className="primary" onClick={() => setCreating(true)}>Создать первый проект</button>
    </section>}
    {!loading && !error && cursor && <button className="secondary load-more" onClick={() => setPageCursor(cursor)}>Показать ещё</button>}
  </>;
}

function CreateProject({ api, onCancel }: { api: ApiClient; onCancel: () => void }) {
  const [name, setName] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const pending = useRef<AbortController | null>(null);
  useEffect(() => () => pending.current?.abort(), []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    if (!name.trim()) { setError('Введите название проекта.'); return; }
    const controller = new AbortController();
    pending.current = controller;
    setBusy(true); setError('');
    try {
      const project = await api.request<Project>('/projects', {
        method: 'POST', body: { name }, signal: controller.signal,
      });
      if (!controller.signal.aborted) window.location.hash = `/projects/${project.id}`;
    } catch (error) {
      if (!controller.signal.aborted) setError(`${errorMessage(error)} Если ответ потерян, обновите список перед повторным созданием.`);
    } finally { if (!controller.signal.aborted) setBusy(false); }
  }

  return <section className="create-panel panel" aria-labelledby="create-title">
    <h2 id="create-title">Новый проект</h2><p className="muted">Вы станете владельцем созданного проекта.</p>
    <form className="stack" onSubmit={submit}>
      <label>Название проекта<input autoFocus name="name" required maxLength={200}
        value={name} onChange={e => setName(e.target.value)} disabled={busy} /></label>
      {error && <ErrorNotice message={error} />}
      <div className="actions"><button className="primary" disabled={busy}>{busy ? 'Создаём…' : 'Создать'}</button>
        <button type="button" className="secondary" disabled={busy} onClick={onCancel}>Отмена</button></div>
    </form>
  </section>;
}

export function ProjectDetail({ api, id, section = 'overview', selected, accessRevision = 0 }: {
  api: ApiClient; id: string; section?: 'overview' | 'materials' | 'access'; selected?: MaterialSelection; accessRevision?: number;
}) {
  const [project, setProject] = useState<Project | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [revision, setRevision] = useState(0);
  const [checkedAccess, setCheckedAccess] = useState(-1);
  const unavailable = useCallback(() => {
    setProject(null); setError('Проект или материал недоступен. Доступ мог быть отозван. Повторите проверку проекта.');
  }, []);
  const recheckProject = useCallback(() => setRevision(n => n + 1), []);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true); setError('');
    api.request<Project>(`/projects/${encodeURIComponent(id)}`, { signal: controller.signal })
      .then(project => {
        if (!controller.signal.aborted) { setProject(project); setCheckedAccess(accessRevision); }
      })
      .catch(error => {
        if (!controller.signal.aborted) { setProject(null); setError(errorMessage(error)); }
      })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [api, id, revision, accessRevision]);

  const checking = loading || checkedAccess !== accessRevision;

  return <>
    <a className="back-link" href="#/projects">← Все проекты</a>
    {(loading || (project && checking)) && <Loading>Открываем проект…</Loading>}
    {error && <div className="stack"><ErrorNotice message={error} />
      <button className="secondary retry" onClick={() => setRevision(n => n + 1)}>Повторить запрос</button></div>}
    {project && <div style={{ display: checking ? 'none' : undefined }}>
      <div className="page-heading"><div><p className="eyebrow">Проект</p><h1>{project.name}</h1></div>
        <button className="secondary" onClick={() => setRevision(n => n + 1)}>Обновить проект</button></div>
      <nav className="project-tabs" aria-label="Разделы проекта">
        <a href={`#/projects/${id}`} aria-current={section === 'overview' ? 'page' : undefined}>Обзор проекта</a>
        <a href={`#/projects/${id}/materials`} aria-current={section === 'materials' ? 'page' : undefined}>Материалы</a>
        {project.permissions.is_owner && <a href={`#/projects/${id}/access`}
          aria-current={section === 'access' ? 'page' : undefined}>Участники</a>}
      </nav>
      {section === 'access' ? project.permissions.is_owner
        ? <ProjectAccess api={api} projectId={id} ownerId={project.owner_id}
            refreshToken={`${accessRevision}/${revision}`} onUnavailable={unavailable} onForbidden={recheckProject} />
        : <section className="panel detail-panel"><h2>Участники</h2>
            <p>Просмотр и управление участниками доступны только владельцу проекта.</p>
            <a href={`#/projects/${id}`}>Вернуться к обзору проекта</a></section>
        : section === 'materials' ? <Materials api={api} projectId={id} selected={selected} onUnavailable={unavailable} />
        : <section className="panel detail-panel"><h2>Ваши полномочия</h2><Permissions project={project} />
        <p className="muted">{project.permissions.is_owner
          ? 'Вы — владелец этого проекта с правами участника и утверждения.'
          : project.permissions.can_approve ? 'Вы — участник с дополнительным правом утверждения.' : 'Вы — участник этого проекта.'}</p>
        <dl><dt>Идентификатор проекта</dt><dd className="mono">{project.id}</dd></dl>
      </section>}
    </div>}
  </>;
}
