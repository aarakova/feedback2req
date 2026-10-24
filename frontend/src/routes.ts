import type { MaterialSelection } from './Materials';

export type ProjectSection = 'overview' | 'materials' | 'findings' | 'requirements' | 'processing' | 'access';
export const sectionNames: Record<ProjectSection, string> = {
  overview: 'Обзор', materials: 'Материалы', findings: 'Находки',
  requirements: 'Требования', processing: 'Обработка', access: 'Доступ',
};
export const projectSections = Object.keys(sectionNames) as ProjectSection[];
export const projectHref = (id: string, section: ProjectSection = 'overview') =>
  `#/projects/${id}${section === 'overview' ? '' : `/${section}`}`;

type Route = { kind: 'projects' } | { kind: 'missing' } | {
  kind: 'project'; id: string; section: ProjectSection; selected?: MaterialSelection;
};

export function parseRoute(hash: string): Route {
  if (['', '#', '#/', '#/projects'].includes(hash)) return { kind: 'projects' };
  const id = '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}';
  const material = new RegExp(`^#/projects/(${id})/materials/(sources|documents)/(${id})$`, 'i').exec(hash);
  if (material) return {
    kind: 'project', id: material[1].toLowerCase(), section: 'materials',
    selected: { kind: material[2].toLowerCase() as MaterialSelection['kind'], id: material[3].toLowerCase() },
  };
  const project = new RegExp(`^#/projects/(${id})(?:/(materials|findings|requirements|processing|access))?$`, 'i').exec(hash);
  return project ? { kind: 'project', id: project[1].toLowerCase(),
    section: (project[2]?.toLowerCase() ?? 'overview') as ProjectSection } : { kind: 'missing' };
}
