import { useCallback, useEffect, useState } from 'react';
import { ApiClient, errorMessage } from './api';
import type { Project, User } from './api';
import { AppLayout } from './Layout';
import { ErrorNotice, Loading } from './ui';
import { Materials } from './Materials';
import type { MaterialSelection } from './Materials';
import { ProjectAccess } from './Access';
import { ProjectSettings } from './ProjectSettings';
import { ProjectOverview } from './ProjectOverview';
import { FindingsScreen } from './observer/Findings';
import { RequirementsScreen } from './observer/Requirements';
import { ProcessingScreen } from './observer/Processing';
import { groupHref, projectHref, requirementHref, requirementsFilterHref } from './routes';
import type { ProjectSection, RequirementFilter } from './routes';

export function ProjectLayout({ api, user, onLogout, id, section, selected, accessRevision, requirementId, groupId, requirementFilter }: {
  api: ApiClient; user: User; onLogout: () => void; id: string; section: ProjectSection;
  selected?: MaterialSelection; accessRevision: number;
  requirementId?: string; groupId?: string; requirementFilter?: RequirementFilter;
}) {
  const [project, setProject] = useState<Project | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [revision, setRevision] = useState(0);
  const [checkedAccess, setCheckedAccess] = useState(-1);
  const unavailable = useCallback(() => {
    setProject(null); setError('Проект или материал недоступен. Доступ мог быть отозван. Повторите проверку проекта.');
  }, []);
  const recheckProject = useCallback(() => setRevision(n => n + 1), []);
  const updatedProject = useCallback((updated: Project) => {
    setProject(current => current?.id === updated.id ? updated : current);
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true); setError('');
    api.request<Project>(`/projects/${encodeURIComponent(id)}`, { signal: controller.signal })
      .then(project => {
        if (!controller.signal.aborted) { setProject(project); setCheckedAccess(accessRevision); }
      })
      .catch(error => {
        if (!controller.signal.aborted) { setProject(null); setError(errorMessage(error)); }
      })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [api, id, revision, accessRevision]);

  const checking = loading || checkedAccess !== accessRevision;
  return <AppLayout user={user} onLogout={onLogout} section={section}
    project={project && !checking ? project : undefined} onRefresh={recheckProject}>
    {(loading || (project && checking)) && <Loading>Открываем проект…</Loading>}
    {error && <div className="stack"><ErrorNotice message={error} />
      <button className="secondary retry" onClick={recheckProject}>Повторить запрос</button></div>}
    {project && <div className="project-section" style={{ display: checking ? 'none' : undefined }}>
      {section === 'access' ? project.permissions.is_owner
        ? <div className="observer-access">
            <ProjectAccess api={api} projectId={id} ownerId={project.owner_id}
              refreshToken={`${accessRevision}/${revision}`} onUnavailable={unavailable} onForbidden={recheckProject} />
            <ProjectSettings api={api} project={project} refreshToken={`${accessRevision}/${revision}`}
              onUpdated={updatedProject} onUnavailable={unavailable} onForbidden={recheckProject} />
          </div>
        : <section className="panel detail-panel"><h2>Участники</h2>
            <p>Просмотр и управление участниками доступны только владельцу проекта.</p>
            <a href={projectHref(id)}>Вернуться к обзору проекта</a></section>
        : section === 'materials' ? <Materials api={api} projectId={id} selected={selected} onUnavailable={unavailable} />
        : section === 'findings' ? <FindingsScreen project={project} selectedGroupId={groupId}
            onSelectGroup={group => { window.location.hash = group ? groupHref(id, group) : projectHref(id, 'findings'); }} />
        : section === 'requirements' ? <RequirementsScreen project={project} selectedId={requirementId} filter={requirementFilter ?? 'all'}
            onFilterChange={filter => { window.location.hash = requirementsFilterHref(id, filter); }}
            onSelect={requirement => { window.location.hash = `${requirementHref(id, requirement)}?filter=${requirementFilter ?? 'all'}`; }} />
        : section === 'processing' ? <ProcessingScreen projectId={id} />
        : <ProjectOverview project={project} />}
    </div>}
  </AppLayout>;
}
