import { ApiClient } from '../api';
import type { Project } from '../api';
import { ProjectOverview } from '../ProjectOverview';
import { Panel } from '../observer/ui';
import { ErrorNotice, Loading } from '../ui';
import { projectHref, runHref } from '../routes';
import { dateLabel } from './adapters';
import type { OverviewDTO } from './dto';
import { useRead } from './reads';

export function ProjectOverviewData({ api, project, onRecheck }: { api: ApiClient; project: Project; onRecheck: () => void }) {
  const read = useRead<OverviewDTO>(api, `/projects/${project.id}/overview`, onRecheck);
  const overview = read.data?.project_id === project.id ? read.data : undefined;
  const runtime = <Panel title="Материалы и обработка" className="observer-space" extra={<button className="secondary" disabled={read.loading} onClick={read.reload}>Обновить сведения</button>}>
    <div className="panel-body stack">
      {read.loading && <Loading>Загружаем сведения проекта…</Loading>}
      {read.error && <ErrorNotice message={read.error} />}
      {read.data && !overview && <p className="notice bad">Ответ относится к другому проекту и не отображается.</p>}
      <dl className="processing-facts"><div><dt>Текстовые отзывы</dt><dd>{overview ? overview.material_counts.text_sources : '—'}</dd></div>
        <div><dt>Документы продукта</dt><dd>{overview ? overview.material_counts.product_documents : '—'}</dd></div>
        <div><dt>Сведения на</dt><dd>{overview ? <time dateTime={overview.calculated_at}>{dateLabel(overview.calculated_at)}</time> : '—'}</dd></div></dl>
      {overview && (overview.processing.latest_run_id ? <a className="source-link" href={runHref(project.id, overview.processing.latest_run_id)}>Последний запуск →</a>
        : <p className="small muted">Запусков пока нет.</p>)}
      <a className="source-link" href={projectHref(project.id, 'processing')}>Выбрать материалы и операцию →</a>
      <p className="small muted">Количество материалов предоставлено сервером, не рассчитано по загруженным страницам. Агрегаты требований, решений и блокеров пока недоступны.</p>
    </div></Panel>;
  return <ProjectOverview project={project} runtime={runtime} processingAvailable />;
}
