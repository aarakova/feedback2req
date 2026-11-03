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
export const requirementFilters = ['all', 'draft', 'approved', 'rejected', 'blocker', 'issues', 'lost', 'approved_all', 'approved_partial', 'approved_lost'] as const;
export type RequirementFilter = typeof requirementFilters[number];
export const requirementsFilterHref = (projectId: string, filter: RequirementFilter) => `${projectHref(projectId, 'requirements')}?filter=${filter}`;

type Route = { kind: 'projects' } | { kind: 'missing' } | {
  kind: 'project'; id: string; section: ProjectSection; selected?: MaterialSelection;
  requirementId?: string; groupId?: string; requirementFilter?: RequirementFilter;
};

export function parseRoute(hash: string): Route {
  const queryStart = hash.indexOf('?');
  if (queryStart >= 0) {
    const params = new URLSearchParams(hash.slice(queryStart + 1));
    const filter = params.get('filter');
    if (params.getAll('filter').length !== 1 || [...params.keys()].some(key => key !== 'filter')
      || !requirementFilters.some(value => value === filter)) return { kind: 'missing' };
    const route = parseRoute(hash.slice(0, queryStart));
    return route.kind === 'project' && route.section === 'requirements'
      ? { ...route, requirementFilter: filter as RequirementFilter } : { kind: 'missing' };
  }
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
