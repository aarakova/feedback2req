import type { Project } from './api';
import { projectHref, projectSections, sectionNames } from './routes';
import type { ProjectSection } from './routes';

const icons: Record<ProjectSection, string> = {
  overview: 'M3 13h7v8H3z M14 3h7v18h-7z M3 3h7v6H3z',
  materials: 'M6 3h8l4 4v14H6z M14 3v5h4 M9 12h6 M9 16h6',
  findings: 'M9 18h6 M10 21h4 M8 14a6 6 0 1 1 8 0l-1 2H9z',
  requirements: 'M8 5h13 M8 12h13 M8 19h13 M3 5h1 M3 12h1 M3 19h1',
  processing: 'm12 3 9 5-9 5-9-5z M3 12l9 5 9-5 M3 16l9 5 9-5',
  access: 'M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2 M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8 M18 8h4 M20 6v4',
};
export const futureSection = (section: ProjectSection) =>
  section === 'findings' || section === 'requirements' || section === 'processing';

export function ProjectNavigation({ project, section }: { project: Project; section: ProjectSection }) {
  return <nav className="project-navigation" aria-label="Разделы проекта">
    <p className="eyebrow">Рабочая область</p>
    {projectSections.filter(item => item !== 'access' || project.permissions.is_owner).map(item =>
      <a key={item} className={`nav-link${section === item ? ' active' : ''}`}
        href={projectHref(project.id, item)} aria-current={section === item ? 'page' : undefined}
        aria-label={item === 'overview' ? 'Обзор проекта' : sectionNames[item]}>
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d={icons[item]} /></svg>
        <span>{sectionNames[item]}</span>
        {futureSection(item) && <span className="nav-status" aria-hidden="true">Позже</span>}
      </a>)}
  </nav>;
}

export function ProjectHeader({ project, section }: { project: Project; section: ProjectSection }) {
  return <div className="project-header">
    <p className="eyebrow">Проект <span aria-hidden="true">/</span> {sectionNames[section]}</p>
    <h1>{project.name}</h1>
    <p className="project-role">{project.permissions.is_owner ? 'Владелец проекта'
      : project.permissions.can_approve ? 'Участник проекта · Approver' : 'Участник проекта'}</p>
  </div>;
}
