import { useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { ApiClient, ApiError, errorMessage } from './api';
import type { Access, Page } from './api';
import { ErrorNotice, Loading, PermissionBadges } from './ui';

type Change = { userId: string; canApprove: boolean } | { userId: string; remove: true };
type Work = 'list' | 'add' | 'permissions' | 'remove' | 'verify';
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function ProjectAccess({ api, projectId, ownerId, refreshToken, onUnavailable, onForbidden }: {
  api: ApiClient; projectId: string; ownerId: string; refreshToken: string;
  onUnavailable: () => void; onForbidden: () => void;
}) {
  const [items, setItems] = useState<Access[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [busy, setBusy] = useState<Work | null>('list');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [revision, setRevision] = useState(0);
  const [adding, setAdding] = useState(false);
  const [userId, setUserId] = useState('');
  const [canApprove, setCanApprove] = useState(false);
  const [existing, setExisting] = useState<Access | null>(null);
  const [removing, setRemoving] = useState<string | null>(null);
  const [uncertain, setUncertain] = useState<Change | null>(null);
  const restricted = useRef(false);
  const active = useRef<{ controller: AbortController; work: Work; change?: Change } | null>(null);
  const addButton = useRef<HTMLButtonElement>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  const path = `/projects/${projectId}/access`;

  function begin(work: Work) {
    if (active.current) return null;
    const controller = new AbortController();
    active.current = { controller, work };
    setBusy(work); setError('');
    return controller;
  }

  function finish(controller: AbortController) {
    if (active.current?.controller === controller && !controller.signal.aborted) {
      active.current = null; setBusy(null);
    }
  }

  function failed(cause: unknown, controller: AbortController) {
    if (controller.signal.aborted) return;
    setError(errorMessage(cause));
    if (cause instanceof ApiError && cause.status === 404) onUnavailable();
    if (cause instanceof ApiError && cause.status === 403 && cause.code === 'forbidden') {
      restricted.current = true;
      setItems([]); setNextCursor(null); setExisting(null); setRemoving(null); setLoaded(false);
      onForbidden();
    }
  }

  async function load(cursor: string | null = null) {
    const controller = begin('list');
    if (!controller) return;
    try {
      const page = await api.request<Page<Access>>(path + (cursor ? `?cursor=${encodeURIComponent(cursor)}` : ''),
        { signal: controller.signal });
      if (controller.signal.aborted) return;
      setItems(previous => cursor
        ? [...previous.filter(old => !page.items.some(row => row.user_id === old.user_id)), ...page.items]
        : page.items);
      setNextCursor(page.next_cursor); setLoaded(true);
    } catch (cause) { failed(cause, controller); }
    finally { finish(controller); }
  }

  useEffect(() => {
    // A context recheck can interrupt a mutation after the server committed it.
    const previous = active.current;
    if (previous?.change) setUncertain(previous.change);
    previous?.controller.abort(); active.current = null;
    setBusy(null); setItems([]); setNextCursor(null); setLoaded(false); setExisting(null); setRemoving(null);
    if (!restricted.current) void load();
    return () => { active.current?.controller.abort(); };
  }, [api, projectId, refreshToken, revision]);

  function refresh() {
    restricted.current = false;
    setRevision(value => value + 1);
  }

  // No single-user read exists. Absence requires reading to the last page.
  async function findAccess(id: string, controller: AbortController): Promise<Access | undefined> {
    let cursor: string | null = null;
    const cursors = new Set<string>();
    do {
      const page: Page<Access> = await api.request(path + (cursor ? `?cursor=${encodeURIComponent(cursor)}` : ''),
        { signal: controller.signal });
      if (controller.signal.aborted) throw new DOMException('Aborted', 'AbortError');
      const found = page.items.find(row => row.user_id === id);
      if (found) return found;
      cursor = page.next_cursor;
      if (cursor && cursors.has(cursor)) throw new Error('Repeated cursor');
      if (cursor) cursors.add(cursor);
    } while (cursor);
  }

  async function write(change: Change, controller: AbortController) {
    if (controller.signal.aborted || !active.current) return;
    active.current.change = change;
    try {
      if ('remove' in change) {
        await api.request<void>(`${path}/${change.userId}`, { method: 'DELETE', signal: controller.signal });
      } else {
        const result = await api.request<Access>(`${path}/${change.userId}`, {
          method: 'PUT', body: { can_approve: change.canApprove }, signal: controller.signal,
        });
        if (result.user_id !== change.userId || result.can_approve !== change.canApprove || !result.is_member) {
          throw new Error('Unconfirmed access response');
        }
      }
      if (controller.signal.aborted) return;
      setNotice('remove' in change ? `Доступ к проекту отсутствует: ${change.userId}.`
        : `Доступ сохранён: ${change.userId}. ${change.canApprove ? 'Право Approver назначено.' : 'Право Approver отсутствует.'}`);
      setExisting(null); setRemoving(null);
      if (active.current.work === 'add') { setAdding(false); setUserId(''); setCanApprove(false); }
      heading.current?.focus();
      // Refresh errors cannot turn the already confirmed mutation into a failure.
      active.current.change = undefined;
      refresh();
    } catch (cause) {
      if (controller.signal.aborted) return;
      if (!(cause instanceof ApiError) || cause.status >= 500) setUncertain(change);
      failed(cause, controller);
    }
  }

  async function add(event: FormEvent) {
    event.preventDefault();
    if (uncertain || restricted.current) return;
    const id = userId.trim().toLowerCase();
    if (!uuid.test(id)) { setError('Введите ID пользователя в формате UUID.'); return; }
    if (id === ownerId.toLowerCase()) { setError('Владелец уже участвует в проекте. Его доступ неизменяем.'); return; }
    const controller = begin('add');
    if (!controller) return;
    setNotice(''); setExisting(null);
    try {
      const found = await findAccess(id, controller);
      if (controller.signal.aborted) return;
      if (found) {
        setExisting(found);
        setNotice('Участник уже в проекте. Добавление не выполнено. Измените полномочия отдельным действием ниже.');
      } else await write({ userId: id, canApprove }, controller);
    } catch (cause) { failed(cause, controller); }
    finally { finish(controller); }
  }

  async function changePermissions(row: Access) {
    if (uncertain || restricted.current) return;
    const controller = begin('permissions');
    if (!controller) return;
    setNotice('');
    try {
      const current = await findAccess(row.user_id, controller);
      if (controller.signal.aborted) return;
      if (!current || current.can_approve !== row.can_approve) {
        setNotice('Доступ изменён в другой сессии. Изменение не отправлено; проверьте обновлённый список.');
        refresh();
      } else await write({ userId: row.user_id, canApprove: !row.can_approve }, controller);
    } catch (cause) { failed(cause, controller); }
    finally { finish(controller); }
  }

  async function remove(id: string) {
    if (uncertain || restricted.current) return;
    const controller = begin('remove');
    if (!controller) return;
    setNotice('');
    try { await write({ userId: id, remove: true }, controller); }
    finally { finish(controller); }
  }

  async function verify() {
    if (!uncertain) return;
    const controller = begin('verify');
    if (!controller) return;
    setNotice('');
    try {
      const current = await findAccess(uncertain.userId, controller);
      if (controller.signal.aborted) return;
      setUncertain(null); setExisting(current ?? null); setRemoving(null);
      setNotice(`Текущее состояние ${uncertain.userId}: ${current
        ? `участник${current.can_approve ? ' с правом Approver' : ' без права Approver'}` : 'доступ отсутствует'}. `
        + 'Это состояние на момент проверки, а не подтверждение результата предыдущего запроса.');
      refresh();
    } catch (cause) { failed(cause, controller); }
    finally { finish(controller); }
  }

  const disabled = busy !== null || uncertain !== null || restricted.current;
  function rowView(row: Access) {
    return <li key={row.user_id} className="access-row" aria-label={`Участник ${row.user_id}`}>
      <div className="stack"><span className="mono">{row.user_id}</span><PermissionBadges permissions={row} /></div>
      {row.is_owner ? <p className="muted small">Полномочия владельца неизменяемы.</p>
        : <div className="stack">
          <div className="actions">
            <button className="secondary" disabled={disabled} onClick={() => changePermissions(row)}>
              {row.can_approve ? 'Отозвать Approver' : 'Назначить Approver'}</button>
            <button className="secondary danger" disabled={disabled} onClick={() => setRemoving(row.user_id)}>
              Удалить участника</button>
          </div>
          {removing === row.user_id && <div className="delete-confirm stack" role="group" aria-label="Подтверждение удаления">
            <p>Удалить участника {row.user_id} из проекта? Доступ к проекту прекратится. Учётная запись сохранится.</p>
            <div className="actions">
              <button autoFocus className="secondary" disabled={disabled} onClick={() => {
                setRemoving(null); heading.current?.focus();
              }}>Отмена удаления</button>
              <button className="primary danger" disabled={disabled} onClick={() => remove(row.user_id)}>Удалить из проекта</button>
            </div>
          </div>}
        </div>}
    </li>;
  }

  return <section className="panel access-panel stack" aria-labelledby="access-heading">
    <div className="material-heading"><h2 id="access-heading" tabIndex={-1} ref={heading}>Участники</h2>
      <button className="secondary" disabled={busy !== null} onClick={refresh}>Обновить участников</button></div>
    <p className="muted">Управление доступом к этому проекту. Approver — дополнительное право утверждения.</p>
    <p className="muted small">Перед добавлением и изменением проверяем текущий доступ.
      Одновременное сохранение в другой сессии может заменить выбранные права; изменение полномочий
      может вернуть доступ, если участника удалили после проверки.</p>
    <button ref={addButton} className="primary add-material" disabled={disabled} aria-expanded={adding}
      onClick={() => { setAdding(!adding); setExisting(null); }}>Добавить участника</button>
    {adding && <form className="access-form stack" aria-label="Добавление участника" onSubmit={add}>
      <label>ID пользователя<input autoFocus name="user_id" required autoComplete="off" spellCheck={false}
        disabled={busy !== null || uncertain !== null} value={userId} onChange={event => {
          setUserId(event.target.value); setExisting(null);
        }} /></label>
      <p className="muted small">Попросите зарегистрированного пользователя передать свой ID из раздела «Мой ID».</p>
      <label className="checkbox-label"><input type="checkbox" checked={canApprove} disabled={disabled}
        onChange={event => setCanApprove(event.target.checked)} />Сразу назначить Approver</label>
      <p>Будет установлен доступ {canApprove ? 'с правом Approver' : 'без права Approver'}.
        Если пользователь уже участвует, предложим отдельное изменение.
        Если его добавят одновременно после проверки, выбранные права заменят существующие,
        включая {canApprove ? 'назначение' : 'отзыв'} Approver.</p>
      <div className="actions"><button className="primary" disabled={disabled}>Добавить в проект</button>
        <button type="button" className="secondary" disabled={busy !== null || uncertain !== null}
          onClick={() => { setAdding(false); setExisting(null); addButton.current?.focus(); }}>Закрыть форму</button></div>
    </form>}
    {error && <ErrorNotice message={error} />}
    {notice && <p className="success-notice" role="status">{notice}</p>}
    {uncertain && <div className="uncertain-notice stack" role="group" aria-label="Неопределённый результат">
      <p>Результат изменения неизвестен: {uncertain.userId}. Сервер мог выполнить запрос.
        Автоматического повтора нет. Проверьте текущее состояние перед новым действием.</p>
      <button className="secondary" disabled={busy !== null || restricted.current} onClick={verify}>Проверить текущее состояние</button>
    </div>}
    {busy && <Loading>{busy === 'list' ? 'Загружаем участников…' : busy === 'verify' ? 'Проверяем текущее состояние…'
      : busy === 'add' ? 'Проверяем и добавляем участника…' : busy === 'remove' ? 'Удаляем участника…' : 'Проверяем и изменяем Approver…'}</Loading>}
    {error && !busy && <button className="secondary retry" onClick={() => {
      if (restricted.current || !loaded) refresh(); else void load(nextCursor);
    }}>Повторить загрузку участников</button>}
    {existing && !items.some(row => row.user_id === existing.user_id) && <div className="stack">
      <h3>Существующий участник</h3><ul className="access-list">{rowView(existing)}</ul></div>}
    {items.length > 0 && <ul className="access-list" aria-label="Список участников">{items.map(rowView)}</ul>}
    {loaded && !error && !nextCursor && items.every(row => row.is_owner) && <p className="muted">Кроме владельца участников пока нет.</p>}
    {!busy && !error && nextCursor && <button className="secondary load-more" onClick={() => load(nextCursor)}>Показать ещё</button>}
  </section>;
}
