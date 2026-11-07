import type { MaterialSelection } from './Materials';
import type { InputRef } from './processing/dto';

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
export const groupStateHref = (projectId: string, id: string, state: string) => `${groupHref(projectId, id)}/states/${encodeURIComponent(state)}`;
export const runHref = (projectId: string, id: string) => `${projectHref(projectId, 'processing')}/runs/${encodeURIComponent(id)}`;
export const findingHref = (projectId: string, id: string) => `${projectHref(projectId, 'findings')}/${encodeURIComponent(id)}`;
export const findingsAttemptHref = (projectId: string, id: string) => `${projectHref(projectId, 'findings')}?attempt_id=${encodeURIComponent(id)}`;
export const fragmentHref = (projectId: string, id: string, state: string) => `${projectHref(projectId, 'findings')}/fragments/${encodeURIComponent(id)}/states/${encodeURIComponent(state)}`;
export const materialStateHref = (projectId: string, kind: 'sources' | 'documents', id: string, state: string) =>
  `${projectHref(projectId, 'materials')}/${kind}/${encodeURIComponent(id)}/states/${encodeURIComponent(state)}`;
export const processingInputHref = (projectId: string, input: InputRef) => `${projectHref(projectId, 'processing')}?${new URLSearchParams({ kind: input.kind, id: input.id, state_id: input.state_id })}`;
export const requirementFilters = ['all', 'draft', 'approved', 'rejected', 'blocker', 'issues', 'lost', 'approved_all', 'approved_partial', 'approved_lost'] as const;
export type RequirementFilter = typeof requirementFilters[number];
export const requirementsFilterHref = (projectId: string, filter: RequirementFilter) => `${projectHref(projectId, 'requirements')}?filter=${filter}`;

type Route = { kind: 'projects' } | { kind: 'missing' } | {
  kind: 'project'; id: string; section: ProjectSection; selected?: MaterialSelection;
  requirementId?: string; groupId?: string; groupStateId?: string; requirementFilter?: RequirementFilter;
  runId?: string; findingId?: string; fragment?: { id: string; stateId: string }; attemptId?: string; processingInput?: InputRef;
};

export function parseRoute(hash: string): Route {
  const queryStart = hash.indexOf('?');
  if (queryStart >= 0) {
    const params = new URLSearchParams(hash.slice(queryStart + 1));
    const route = parseRoute(hash.slice(0, queryStart));
    if (route.kind !== 'project') return { kind: 'missing' };
    const unique = (keys: string[]) => [...params.keys()].every(key => keys.includes(key)) && keys.every(key => params.getAll(key).length === 1);
    const uuid = (value: string | null): value is string => value !== null && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value);
    if (route.section === 'processing' && !route.runId && unique(['kind', 'id', 'state_id'])) {
      const kind = params.get('kind'), id = params.get('id'), state = params.get('state_id');
      return (kind === 'source' || kind === 'document') && uuid(id) && uuid(state)
        ? { ...route, processingInput: { kind, id: id.toLowerCase(), state_id: state.toLowerCase() } } : { kind: 'missing' };
    }
    if (route.section === 'findings' && !route.groupId && unique(['attempt_id'])) {
      const attemptId = params.get('attempt_id');
      return uuid(attemptId) ? { ...route, attemptId: attemptId.toLowerCase() } : { kind: 'missing' };
    }
    const filter = params.get('filter');
    if (params.getAll('filter').length !== 1 || [...params.keys()].some(key => key !== 'filter')
      || !requirementFilters.some(value => value === filter)) return { kind: 'missing' };
    return route.section === 'requirements'
      ? { ...route, requirementFilter: filter as RequirementFilter } : { kind: 'missing' };
  }
  if (['', '#', '#/', '#/projects'].includes(hash)) return { kind: 'projects' };
  const id = '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}';
  const groupState = new RegExp(`^#/projects/(${id})/findings/groups/(${id})/states/(${id})$`, 'i').exec(hash);
  if (groupState) return { kind: 'project', id: groupState[1].toLowerCase(), section: 'findings', groupId: groupState[2].toLowerCase(), groupStateId: groupState[3].toLowerCase() };
  const fragment = new RegExp(`^#/projects/(${id})/findings/fragments/(${id})/states/(${id})$`, 'i').exec(hash);
  if (fragment) return { kind: 'project', id: fragment[1].toLowerCase(), section: 'findings', fragment: { id: fragment[2].toLowerCase(), stateId: fragment[3].toLowerCase() } };
  const result = new RegExp(`^#/projects/(${id})/(processing/runs|findings)/(${id})$`, 'i').exec(hash);
  if (result) return { kind: 'project', id: result[1].toLowerCase(), section: result[2].toLowerCase() === 'findings' ? 'findings' : 'processing',
    ...(result[2].toLowerCase() === 'findings' ? { findingId: result[3].toLowerCase() } : { runId: result[3].toLowerCase() }) };
  const materialState = new RegExp(`^#/projects/(${id})/materials/(sources|documents)/(${id})/states/(${id})$`, 'i').exec(hash);
  if (materialState) return { kind: 'project', id: materialState[1].toLowerCase(), section: 'materials',
    selected: { kind: materialState[2].toLowerCase() as MaterialSelection['kind'], id: materialState[3].toLowerCase(), stateId: materialState[4].toLowerCase() } };
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
