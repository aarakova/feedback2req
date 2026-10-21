import { useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { ApiClient, ApiError, errorMessage, projectUnavailable } from './api';
import type { Material, MaterialKind, Page } from './api';
import { ErrorNotice, Loading } from './ui';

export interface MaterialSelection { kind: MaterialKind; id: string }
interface ProjectProps {
  api: ApiClient;
  projectId: string;
  onUnavailable: () => void;
}

const collectionName = (kind: MaterialKind) => kind === 'sources' ? 'Отзывы' : 'Документы продукта';
const materialPath = (projectId: string, kind: MaterialKind, id?: string) =>
  `/projects/${projectId}/${kind}${id ? `/${id}` : ''}`;
export const materialHref = (projectId: string, kind: MaterialKind, id?: string) =>
  `#/projects/${projectId}/materials${id ? `/${kind}/${id}` : ''}`;

export function Materials({ api, projectId, onUnavailable, selected }: ProjectProps & {
  selected?: MaterialSelection;
}) {
  return <div className="materials">
    <div><h2>Материалы</h2><p className="muted">Обратная связь и контекст продукта хранятся отдельно.</p></div>
    {selected && <MaterialDetail key={`${selected.kind}/${selected.id}`} api={api}
      projectId={projectId} onUnavailable={onUnavailable} selected={selected} />}
    <div className="material-columns">
      <MaterialCollection api={api} projectId={projectId} onUnavailable={onUnavailable} kind="sources" />
      <MaterialCollection api={api} projectId={projectId} onUnavailable={onUnavailable} kind="documents" />
    </div>
  </div>;
}

function MaterialCollection({ api, projectId, onUnavailable, kind }: ProjectProps & { kind: MaterialKind }) {
  const [items, setItems] = useState<Material[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [cursor, setCursor] = useState<string | null>(null);
  const [revision, setRevision] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [creating, setCreating] = useState(false);
  const [saved, setSaved] = useState<Material | null>(null);
  const isDocument = kind === 'documents';
  const headingId = `${kind}-heading`;

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true); setError('');
    const query = cursor ? `?cursor=${encodeURIComponent(cursor)}` : '';
    api.request<Page<Material>>(materialPath(projectId, kind) + query, { signal: controller.signal })
      .then(page => {
        if (controller.signal.aborted) return;
        setItems(previous => cursor ? [...previous, ...page.items.filter(item =>
          !previous.some(existing => existing.id === item.id))] : page.items);
        setNextCursor(page.next_cursor);
      }).catch(error => {
        if (controller.signal.aborted) return;
        if (projectUnavailable(error)) onUnavailable();
        else setError(errorMessage(error));
      }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [api, projectId, kind, cursor, revision, onUnavailable]);

  function refresh() {
    setItems([]); setCursor(null); setNextCursor(null); setRevision(n => n + 1);
  }

  return <section className="panel material-collection" aria-labelledby={headingId}>
    <div className="material-heading"><h3 id={headingId}>{collectionName(kind)}</h3>
      <button className="secondary" disabled={loading} onClick={refresh}>Обновить список</button></div>
    <p className="muted small">{isDocument
      ? 'Описание текущего продукта: контекст, а не отзыв пользователя.'
      : 'Текстовая обратная связь о продукте.'}</p>
    <button className="primary add-material" disabled={creating} onClick={() => { setCreating(true); setSaved(null); }}>
      {isDocument ? 'Добавить документацию' : 'Добавить обратную связь'}</button>
    {creating && <MaterialForm api={api} projectId={projectId} kind={kind} onUnavailable={onUnavailable}
      onRefresh={refresh} onCancel={() => setCreating(false)} onSaved={material => {
        setCreating(false); setSaved(material); refresh();
        window.location.hash = materialHref(projectId, kind, material.id).slice(1);
      }} />}
    {saved && <div className="success-notice" role="status">
      <p>{isDocument ? 'Документ сохранён.' : 'Обратная связь сохранена.'}</p>
      <a href={materialHref(projectId, kind, saved.id)}>Открыть сохранённый материал</a>
    </div>}
    {error && <div className="stack"><ErrorNotice message={error} />
      <button className="secondary retry" onClick={() => setRevision(n => n + 1)}>Повторить загрузку</button></div>}
    {items.length > 0 && <ul className="material-list">{items.map(item => <li key={item.id}>
      <a href={materialHref(projectId, kind, item.id)}>
        <span className="material-label">{'title' in item ? item.title : 'Текстовый отзыв'}</span>
        <span className="mono muted">ID: {item.id}</span>
        <span className="accent small">Открыть <span aria-hidden="true">→</span></span>
      </a>
    </li>)}</ul>}
    {loading && <Loading>{isDocument ? 'Загружаем документы…' : 'Загружаем отзывы…'}</Loading>}
    {!loading && !error && items.length === 0 && <p className="empty-materials muted">
      {isDocument ? 'Документов пока нет.' : 'Отзывов пока нет.'}</p>}
    {!loading && !error && nextCursor && <button className="secondary" onClick={() => setCursor(nextCursor)}>Показать ещё</button>}
  </section>;
}

function MaterialForm({ api, projectId, kind, onUnavailable, onSaved, onCancel, onRefresh }: ProjectProps & {
  kind: MaterialKind;
  onSaved: (material: Material) => void;
  onCancel: () => void;
  onRefresh: () => void;
}) {
  const [text, setText] = useState('');
  const [title, setTitle] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [uncertain, setUncertain] = useState(false);
  const pending = useRef<AbortController | null>(null);
  const sending = useRef(false);
  useEffect(() => () => pending.current?.abort(), []);
  const isDocument = kind === 'documents';

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (sending.current) return;
    if (!text.trim() || (isDocument && !title.trim())) {
      setError('Заполните непустой текст и название документа, если оно требуется.'); return;
    }
    const controller = new AbortController();
    pending.current = controller;
    sending.current = true;
    setBusy(true); setError(''); setUncertain(false);
    try {
      const material = await api.request<Material>(materialPath(projectId, kind), {
        method: 'POST', body: isDocument ? { title, text } : { kind: 'text', text },
        signal: controller.signal,
      });
      if (!controller.signal.aborted) onSaved(material);
    } catch (error) {
      if (controller.signal.aborted) return;
      if (projectUnavailable(error)) onUnavailable();
      else {
        setError(errorMessage(error));
        setUncertain(!(error instanceof ApiError) || error.status >= 500);
      }
    } finally {
      sending.current = false;
      if (!controller.signal.aborted) setBusy(false);
    }
  }

  return <form className="material-form stack" onSubmit={submit}
    aria-label={isDocument ? 'Новая документация' : 'Новая обратная связь'}>
    {isDocument && <label>Название документа<input name="title" required disabled={busy}
      value={title} onChange={event => setTitle(event.target.value)} /></label>}
    <div className="material-field"><label htmlFor={`${kind}-text`}>{isDocument ? 'Текст документа' : 'Текст отзыва'}</label>
      <textarea id={`${kind}-text`} name="text" required rows={8}
        disabled={busy} value={text} onChange={event => setText(event.target.value)} /></div>
    <p className="muted small">Символов: {[...text].length}. Допустимый объём проверяет сервер.</p>
    {error && <ErrorNotice message={error} />}
    {uncertain && <div className="uncertain-notice stack">
      <p>Результат сохранения неизвестен: сервер мог уже сохранить материал. Автоматического повтора нет.
        Обновите список и проверьте его перед повторной отправкой.</p>
      <button type="button" className="secondary" onClick={onRefresh}>Обновить список перед повтором</button>
    </div>}
    <div className="actions"><button className="primary" disabled={busy}>{busy ? 'Сохраняем…' : 'Сохранить'}</button>
      <button type="button" className="secondary" disabled={busy} onClick={onCancel}>Отмена</button></div>
  </form>;
}

function MaterialDetail({ api, projectId, selected, onUnavailable }: ProjectProps & { selected: MaterialSelection }) {
  const [material, setMaterial] = useState<Material | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [revision, setRevision] = useState(0);
  const { kind, id } = selected;

  useEffect(() => {
    const controller = new AbortController();
    setMaterial(null); setLoading(true); setError('');
    api.request<Material>(materialPath(projectId, kind, id), { signal: controller.signal })
      .then(material => { if (!controller.signal.aborted) setMaterial(material); })
      .catch(error => {
        if (controller.signal.aborted) return;
        if (projectUnavailable(error)) onUnavailable(); else setError(errorMessage(error));
      }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [api, projectId, kind, id, revision, onUnavailable]);

  return <section className="panel material-detail" aria-label="Просмотр материала">
    <div className="material-heading"><h3>{kind === 'documents' ? 'Документ продукта' : 'Текстовый отзыв'}</h3>
      <a href={materialHref(projectId, kind)}>Закрыть просмотр</a></div>
    {loading && <Loading>Загружаем сохранённый текст…</Loading>}
    {error && <><ErrorNotice message={error} />
      <button className="secondary retry" onClick={() => setRevision(n => n + 1)}>Повторить загрузку текста</button></>}
    {material && <>
      {'title' in material && <h4>{material.title}</h4>}
      <p className="mono muted">ID: {material.id}</p>
      <pre className="material-text" aria-label="Сохранённый текст">{material.text}</pre>
    </>}
  </section>;
}
