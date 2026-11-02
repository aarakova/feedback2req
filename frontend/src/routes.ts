import type { MaterialSelection } from './Materials';

export type ProjectSection = 'overview' | 'materials' | 'findings' | 'requirements' | 'processing' | 'access';
export const sectionNames: Record<ProjectSection, string> = {
  overview: 'Обзор', materials: 'Материалы', findings: 'Находки',
  requirements: 'Требования', processing: 'Обработка', access: 'Доступ',
};
export const projectSections = Object.keys(sectionNames) as ProjectSection[];
export const projectHref = (id: string, section: ProjectSection = 'overview') =>
  `#/projects/${id}${section === 'overview' ? '' : `/${section}`}`;
export const requirementHref = (projectId: string, id: string) => `${projectHref(projectId, 'requirements')}/${encodeURIComponent(id)}`;
export const groupHref = (projectId: string, id: string) => `${projectHref(projectId, 'findings')}/groups/${encodeURIComponent(id)}`;

type Route = { kind: 'projects' } | { kind: 'missing' } | {
  kind: 'project'; id: string; section: ProjectSection; selected?: MaterialSelection;
  requirementId?: string; groupId?: string;
};

export function parseRoute(hash: string): Route {
  if (['', '#', '#/', '#/projects'].includes(hash)) return { kind: 'projects' };
  const id = '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}';
  const detail = new RegExp(`^#/projects/(${id})/(requirements|findings/groups)/([^/?#]+)$`, 'i').exec(hash);
  if (detail) {
    try {
      const selected = decodeURIComponent(detail[3]);
      return detail[2].toLowerCase() === 'requirements'
        ? { kind: 'project', id: detail[1].toLowerCase(), section: 'requirements', requirementId: selected }
        : { kind: 'project', id: detail[1].toLowerCase(), section: 'findings', groupId: selected };
    } catch { return { kind: 'missing' }; }
  }
  const material = new RegExp(`^#/projects/(${id})/materials/(sources|documents)/(${id})$`, 'i').exec(hash);
  if (material) return {
    kind: 'project', id: material[1].toLowerCase(), section: 'materials',
    selected: { kind: material[2].toLowerCase() as MaterialSelection['kind'], id: material[3].toLowerCase() },
  };
  const project = new RegExp(`^#/projects/(${id})(?:/(materials|findings|requirements|processing|access))?$`, 'i').exec(hash);
  return project ? { kind: 'project', id: project[1].toLowerCase(),
    section: (project[2]?.toLowerCase() ?? 'overview') as ProjectSection } : { kind: 'missing' };
}
