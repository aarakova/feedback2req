import type { Project } from './api';

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
  const { is_owner, is_member, can_approve } = project.permissions;
  return <div className="badges" aria-label="Полномочия в проекте">
    {is_owner && <span className="badge owner">Владелец</span>}
    {is_member && <span className="badge">Участник</span>}
    {can_approve && <span className="badge">Право утверждения · Approver</span>}
  </div>;
}
