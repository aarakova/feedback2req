import { ApiClient } from '../api';
import type { Page, Project, TextSource } from '../api';
import { FindingsScreen, FindingCard } from '../observer/Findings';
import { EvidenceCard, Panel } from '../observer/ui';
import type { ViewState } from '../observer/viewModels';
import { ErrorNotice, Loading } from '../ui';
import { findingsAttemptHref, materialStateHref, projectHref } from '../routes';
import { exactFragmentText, findingView, findingsView, fragmentEvidence, outcomeView } from './adapters';
import { ResultDetails } from './ResultDetails';
import type { FindingDTO, FragmentDTO } from './dto';
import { usePages, useRead } from './reads';

export function ProjectFindings({ api, project, findingId, fragment, attemptId, groupId, onRecheck, onSelectGroup }: {
  api: ApiClient; project: Project; findingId?: string; fragment?: { id: string; stateId: string }; attemptId?: string;
  groupId?: string; onRecheck: () => void; onSelectGroup: (id: string | undefined) => void;
}) {
  const root = `/projects/${project.id}`;
  const list = usePages<FindingDTO>(api, `${root}/findings${attemptId ? `?attempt_id=${encodeURIComponent(attemptId)}` : ''}`, onRecheck);
  const detail = useRead<FindingDTO>(api, findingId ? `${root}/findings/${findingId}` : undefined, onRecheck);
  const exact = useRead<FragmentDTO>(api, fragment ? `${root}/fragments/${fragment.id}/states/${fragment.stateId}` : undefined, onRecheck);
  const exactData = exact.data?.id === fragment?.id && exact.data?.state_id === fragment?.stateId ? exact.data : undefined;
  const source = useRead<TextSource>(api, exactData ? `${root}/sources/${exactData.source_ref.id}` : undefined, onRecheck);
  // All results of one attempt share its provenance. One exact-attempt row is
  // enough for this metadata, never for project counts or completeness claims.
  const provenance = useRead<Page<FindingDTO>>(api, exactData ? `${root}/findings?attempt_id=${exactData.attempt_id}` : undefined, onRecheck);
  const attemptResult = provenance.data?.items.find(item => item.attempt_id === exactData?.attempt_id);
  const detailData = detail.data?.id === findingId ? detail.data : undefined;
  const data = findingsView(list.items);
  let state: ViewState<typeof data> = { projectId: project.id, status: 'ready', data };
  if (list.loading && !list.items.length) state = { projectId: project.id, status: 'loading' };
  else if (list.error && !list.items.length) state = { projectId: project.id, status: 'error', message: list.error };
  else if (list.next || list.error) state = { projectId: project.id, status: 'partial', data,
    message: list.error || 'Загружена часть списка находок. Число загруженных записей не является общим итогом проекта.' };
  const runtime = <div className="stack observer-space">
    {(findingId || fragment) && <a className="source-link" href={attemptId ? findingsAttemptHref(project.id, attemptId) : projectHref(project.id, 'findings')}>← Вернуться к списку находок</a>}
    <p className="notice">Находки относятся к сохранённым попыткам. Они не доказывают полноту анализа проекта. Группировка, конфликты между находками и связи с требованиями ожидают F2.</p>
    {attemptId && <div className="notice"><p className="mono">Выбрана попытка: {attemptId}</p><a className="source-link" href={projectHref(project.id, 'findings')}>Все доступные находки →</a></div>}
    {findingId && <Panel title="Выбранная находка">
      {detail.loading && <Loading>Загружаем находку…</Loading>}
      {detail.error && <div className="panel-body"><ErrorNotice message={detail.error} /><button className="secondary" onClick={detail.reload}>Повторить загрузку находки</button></div>}
      {detailData && <><FindingCard finding={findingView(detailData)} data={findingsView([detailData])} projectId={project.id} detail />
        <p className="panel-body"><a className="source-link" href={findingsAttemptHref(project.id, detailData.attempt_id)}>Все находки этой попытки →</a></p></>}
    </Panel>}
    {fragment && <Panel title="Точное состояние исходного фрагмента"><div className="panel-body stack">
      {exact.loading && <Loading>Читаем сохранённый фрагмент…</Loading>}
      {exact.error && <><ErrorNotice message={exact.error} /><button className="secondary" onClick={exact.reload}>Повторить загрузку фрагмента</button></>}
      {exactData && <>
        <p className="mono small">Фрагмент: {exactData.id}<br />Состояние фрагмента: {exactData.state_id}<br />Попытка: {exactData.attempt_id}</p>
        {attemptResult ? <ResultDetails value={outcomeView(attemptResult)} />
          : <p className="notice">Происхождение попытки пока не подтверждено. Сам фрагмент не доказывает выполнение реального AI-вызова.</p>}
        <EvidenceCard projectId={project.id} evidence={fragmentEvidence(exactData)} showFragmentLink={false} />
        <p className="small muted">Пригодность исходного текста: {exactData.reliability}. Позиции считаются в символах Unicode точного состояния; CR/LF не заменяются.</p>
        {source.loading && <Loading>Проверяем состояние источника…</Loading>}
        {source.error && <p className="notice warn">Текущее состояние источника проверить не удалось. Исходная ссылка не подменяется новым текстом.</p>}
        {source.data && (source.data.state_id !== exactData.source_ref.state_id ? <p className="notice warn">Источник изменился. Сохранённая цитата относится к состоянию {exactData.source_ref.state_id}, а не к текущему тексту.</p>
          : exactFragmentText(exactData, source.data) ? <p className="notice good">Цитата точно соответствует границам в указанном состоянии источника.</p>
            : <p className="notice bad">Соответствие границ цитаты не подтверждено. Поиск похожего текста не выполняется.</p>)}
        <a className="primary action-link" href={materialStateHref(project.id, 'sources', exactData.source_ref.id, exactData.source_ref.state_id)}>Перейти к исходному материалу</a>
        <a className="source-link" href={findingsAttemptHref(project.id, exactData.attempt_id)}>Вернуться к находкам этой попытки →</a>
      </>}
    </div></Panel>}
  </div>;
  const controls = <div className="observer-row observer-space">
    <button className="secondary" disabled={list.loading} onClick={list.reload}>Обновить находки</button>
    {list.next && <button className="secondary" disabled={list.loading} onClick={list.more}>Показать ещё находки</button>}
    <span className="small muted">Загружено: {list.items.length}. Это число находок, не независимых участников.</span>
    {list.loading && <Loading>Загружаем находки…</Loading>}
  </div>;
  return <FindingsScreen project={project} state={state} selectedGroupId={groupId} onSelectGroup={onSelectGroup} runtime={runtime}
    controls={findingId || fragment ? undefined : controls} detailMode={!!findingId || !!fragment} />;
}
