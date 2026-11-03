import { useEffect, useRef, useState } from 'react';
import type { Project, User } from './api';

export function Brand() {
  return <a className="brand" href="#/projects" aria-label="feedback2req — проекты">
    <span className="logo-mark" aria-hidden="true">f</span><span>feedback<span className="accent">2</span>req</span>
  </a>;
}

export function ErrorNotice({ message }: { message: string }) {
  return <p className="error-notice" role="alert">{message}</p>;
}

export function Loading({ children = 'Загрузка…' }: { children?: string }) {
  return <p className="loading" role="status"><span className="spinner" aria-hidden="true" />{children}</p>;
}

export function Permissions({ project }: { project: Project }) {
  return <PermissionBadges permissions={project.permissions} />;
}

export function PermissionBadges({ permissions }: { permissions: Project['permissions'] }) {
  const { is_owner, is_member, can_approve } = permissions;
  return <div className="badges" aria-label="Полномочия в проекте">
    {is_owner && <span className="badge owner">Владелец</span>}
    {is_member && <span className="badge">Участник</span>}
    {can_approve && <span className="badge">Право утверждения · Approver</span>}
  </div>;
}

export function OwnId({ user }: { user: User }) {
  const [copying, setCopying] = useState(false);
  const [result, setResult] = useState('');
  const alive = useRef(true);
  const sending = useRef(false);
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  async function copy() {
    if (sending.current) return;
    sending.current = true; setCopying(true); setResult('');
    try {
      await navigator.clipboard.writeText(user.id);
      if (alive.current) setResult('ID скопирован.');
    } catch {
      if (alive.current) setResult('Не удалось скопировать ID. Выделите и скопируйте его вручную.');
    } finally {
      sending.current = false;
      if (alive.current) setCopying(false);
    }
  }
  return <div className="own-id">
    <span className="user-login">{user.login}</span>
    <details><summary>Мой ID</summary>
      <p className="mono" aria-label="Мой ID пользователя">{user.id}</p>
      <button className="secondary" disabled={copying} onClick={copy}>Копировать ID</button>
      {result && <p className="small" role="status">{result}</p>}
    </details>
  </div>;
}
