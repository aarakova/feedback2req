import type { ReactNode } from 'react';
import type { Project, User } from './api';
import { Brand, OwnId } from './ui';
import { ProjectHeader, ProjectNavigation } from './ProjectNavigation';
import type { ProjectSection } from './routes';

function Sidebar({ user, project, section, listRoute }: {
  user: User; project?: Project; section?: ProjectSection; listRoute: boolean;
}) {
  return <aside className="sidebar"><Brand />
    {section && <div className="project-identity">
      <a className="back-link" href="#/projects">← Все проекты</a>
      {project && <><p className="eyebrow">Текущий проект</p><p className="sidebar-project-name">{project.name}</p></>}
    </div>}
    {project && section ? <ProjectNavigation project={project} section={section} />
      : !section && <nav aria-label="Основная навигация"><p className="eyebrow">Рабочее пространство</p>
        <a className={`nav-link${listRoute ? ' active' : ''}`} href="#/projects" aria-current={listRoute ? 'page' : undefined}>
          <span aria-hidden="true">▤</span> Проекты</a></nav>}
    <div className="side-foot"><span className="avatar" aria-hidden="true">{user.login.slice(0, 1).toUpperCase()}</span>
      <OwnId key={user.id} user={user} /></div>
  </aside>;
}

export function AppLayout({ user, onLogout, children, project, section, onRefresh, listRoute = false }: {
  user: User; onLogout: () => void; children: ReactNode; project?: Project;
  section?: ProjectSection; onRefresh?: () => void; listRoute?: boolean;
}) {
  return <div className={`workspace app-shell${section ? ' project-workspace' : ''}`}>
    <a className="skip-link" href="#main-content" onClick={event => {
      event.preventDefault(); document.getElementById('main-content')?.focus();
    }}>К содержимому</a>
    <Sidebar user={user} project={project} section={section} listRoute={listRoute} />
    <div className="main-area"><header className="app-header">
      {project && section ? <ProjectHeader project={project} section={section} />
        : <span className="muted">{section ? 'Рабочая область проекта' : 'Рабочее пространство'}</span>}
      <div className="actions header-actions">
        {project && <button className="secondary" onClick={onRefresh}>Обновить проект</button>}
        <button className="secondary" onClick={onLogout}>Выйти</button>
      </div>
    </header><main id="main-content" className="content" tabIndex={-1}>{children}</main></div>
  </div>;
}
