import { ApiClient } from '../api';
import { FindingCard } from '../observer/Findings';
import { Panel } from '../observer/ui';
import { ErrorNotice, Loading } from '../ui';
import { findingHref, groupHref, groupStateHref, materialStateHref, projectHref } from '../routes';
import { aiLabel, coverageLines, dateLabel, findingsView, reasonMessage, stateName, stateTone } from '../processing/adapters';
import type { AnnotationsDTO, CoverageDTO, FindingDTO, StateRefDTO, UnitDTO } from '../processing/dto';
import { usePages, useRead } from '../processing/reads';

// Published FINDING_GROUPS_API transport, never a reconstructed canonical AI response.
export interface GroupSummaryDTO {
  id: string; state_id: string; title: string; summary: string; authorship: string;
  synthetic: boolean; attempt_id: string | null; created_at: string; freshness: 'current' | 'requires_update';
}
export interface GroupDetailDTO extends GroupSummaryDTO {
  previous_state_id: string | null; author_id: string | null;
  members: { ref: StateRefDTO; finding: FindingDTO }[];
  considered_findings: StateRefDTO[];
  context: { ref: StateRefDTO; locator: { start: number; end: number } }[];
  conflicts: { id: string; description: string; positions: { id: string; description: string; findings: StateRefDTO[] }[] }[];
  coverage: CoverageDTO[] | null; annotations: AnnotationsDTO | null;
  provider: string | null; model: string | null; ai_performed: boolean | null;
}
export function ExactRef({ projectId, value }: { projectId: string; value: StateRefDTO }) {
  const href = value.kind === 'finding_group' ? groupStateHref(projectId, value.id, value.state_id)
    : value.kind === 'finding' && value.id === value.state_id ? findingHref(projectId, value.id)
      : value.kind === 'product_document' ? materialStateHref(projectId, 'documents', value.id, value.state_id) : undefined;
  const label = `${value.kind}: ${value.id} / ${value.state_id}`;
  return href ? <a className="source-link mono small" href={href}>{label} ↗</a> : <span className="mono small">{label}</span>;
}
export function GroupOutcome({ projectId, value, published = true }: { projectId: string; published?: boolean; value: {
  synthetic: boolean; ai_performed: boolean | null; provider: string | null; model: string | null;
  coverage: CoverageDTO[] | null; annotations: AnnotationsDTO | null;
} }) {
  return <div className="stack">
    {value.synthetic && <p className="notice warn synthetic-result"><strong>{published ? 'Синтетический результат группировки' : 'Синтетический тестовый режим группировки'}</strong> · тестовые сведения, не смысловой вывод модели.</p>}
    <p className="small muted">{aiLabel(value.ai_performed)}</p>
    <dl className="processing-facts"><div><dt>Провайдер</dt><dd>{value.provider ?? 'Не указан'}</dd></div><div><dt>Модель</dt><dd>{value.model ?? 'Не указана'}</dd></div></dl>
    <div><h4>Охват группировки</h4><ul>{coverageLines(value.coverage).map((line, index) => <li key={index}>{line}</li>)}</ul>
      <p className="small muted">Охват выбранных находок не является анализом всего проекта или оценкой достаточности оснований.</p></div>
    {(['questions', 'uncertainties'] as const).map(kind => value.annotations?.[kind].map(item => <article key={`${kind}/${item.local_id}`} className="notice warn stack">
      <strong>{kind === 'questions' ? 'Вопрос группировки' : 'Неопределённость группировки'}</strong>
      {'text' in item && <p>{String(item.text)}</p>}<p>{item.reason}</p>
      {'blocking' in item && <p>{item.blocking ? 'Блокирующий вопрос' : 'Информационный вопрос'}</p>}
      {item.related.map((link, index) => <div key={index}><span className="mono small">{link.origin}/{link.key} · </span>
        {link.kind && link.state_id ? <ExactRef projectId={projectId} value={{ kind: link.kind, id: link.id, state_id: link.state_id }} /> : <span className="mono small">{link.id}</span>}</div>)}
    </article>))}
  </div>;
}
export function GroupingRunUnit({ projectId, unit }: { projectId: string; unit: UnitDTO }) {
  if (unit.input.kind !== 'finding_set') return null;
  const attempt = unit.attempt;
  const result = attempt?.grouping_result;
  return <section className="processing-unit stack" aria-label={`Группировка задания ${unit.id}`}>
    <div className="observer-row between"><strong>Набор находок</strong><span className={`badge ${stateTone(unit.state)}`}>{stateName(unit.state)}</span></div>
    <p className="mono small">Unit: {unit.id}</p>
    <details><summary>Точные входы группировки</summary><div className="stack">
      {[...unit.input.findings, ...unit.input.documents, ...unit.input.previous_groups].map((ref, index) => <ExactRef key={index} projectId={projectId} value={ref} />)}
    </div></details>
    {attempt ? <>
      <p className="mono small">Попытка: {attempt.id}<br />Начало: {dateLabel(attempt.started_at)}<br />Окончание: {dateLabel(attempt.finished_at)}</p>
      {attempt.reason_code && <p className="notice bad">{attempt.reason_code === 'provider_not_configured' ? 'Провайдер группировки не настроен; операция не выполнена.' : reasonMessage(attempt.reason_code)} ({attempt.reason_code})</p>}
      <GroupOutcome projectId={projectId} value={attempt} published={unit.state === 'completed' && !!result} />
      {result && <>
        <h4>Группы принятого результата</h4>
        {result.group_ids.map(id => <a className="source-link mono small" key={id} href={groupHref(projectId, id)}>Текущее состояние группы {id} ↗</a>)}
        {!result.group_ids.length && <p className="notice">Попытка принята без групп. Это не техническая ошибка и не доказательство отсутствия находок.</p>}
        <h4>Негруппированные находки этой попытки</h4>
        {result.ungrouped_findings.map(ref => <ExactRef key={`${ref.id}/${ref.state_id}`} projectId={projectId} value={ref} />)}
        {!result.ungrouped_findings.length && <p className="small muted">В этом результате явно негруппированные находки не переданы.</p>}
        <details><summary>Соответствие ключей охвата точным находкам</summary><div className="stack">{result.input_findings.map(item => <div key={item.key}>
          <span className="mono small">{item.key} · </span><ExactRef projectId={projectId} value={item.ref} />
        </div>)}</div></details>
      </>}
    </> : <p className="small muted">Попытка ещё не назначена. Группировка ожидает worker.</p>}
    <p className="notice">Публичный запуск и retry группировки пока не подключены. Сохранённые исторические состояния открываются по точной ссылке из группы; ссылка выше явно ведёт к текущему состоянию.</p>
  </section>;
}
function GroupDetails({ projectId, group }: { projectId: string; group: GroupDetailDTO }) {
  const exactMembers = group.members.filter(member => member.ref.kind === 'finding'
    && member.ref.id === member.finding.id && member.ref.state_id === member.finding.state_id);
  const memberData = findingsView(exactMembers.map(member => member.finding));
  return <div className="panel-body stack">
    <h3>{group.title}</h3><p>{group.summary}</p>
    <p className={`notice ${group.freshness === 'current' ? '' : 'warn'}`}>{group.freshness === 'current' ? 'Зависимости группы актуальны' : 'Требует актуализации · зависимости изменились'}. Это не решение человека.</p>
    <p className="mono small">Группа: {group.id}<br />Состояние: {group.state_id}<br />Авторство: {group.authorship}<br />Попытка: {group.attempt_id ?? 'Не указана'}<br />Создано: {dateLabel(group.created_at)}</p>
    <a className="source-link" href={groupStateHref(projectId, group.id, group.state_id)}>Ссылка на это точное состояние →</a>
    {group.previous_state_id && <a className="source-link" href={groupStateHref(projectId, group.id, group.previous_state_id)}>Предыдущее состояние →</a>}
    <GroupOutcome projectId={projectId} value={group} />
    <section className="stack" aria-label="Конфликтующие позиции">
      <h4>Конфликтующие позиции</h4>
      {!group.conflicts.length && <p className="muted small">В этом состоянии группы конфликты не переданы. Это не доказывает их отсутствие в проекте.</p>}
      {group.conflicts.map(conflict => <article className="conflict-notice stack" key={conflict.id}>
        <strong>{conflict.description}</strong><p className="mono small">Конфликт: {conflict.id}</p>
        <div className="conflict-pair">{conflict.positions.map(position => <div className="notice warn stack" key={position.id}>
          <h4>{position.description}</h4><p className="mono small">Позиция: {position.id}</p>
          {position.findings.map(ref => {
            const member = exactMembers.find(item => item.ref.id === ref.id && item.ref.state_id === ref.state_id);
            return <div key={`${ref.id}/${ref.state_id}`}><ExactRef projectId={projectId} value={ref} />
              {member ? <><p>{member.finding.text}</p>{member.finding.evidence.map(evidence => <blockquote key={evidence.id}>{evidence.quote}</blockquote>)}</>
                : <p className="notice warn">Точный состав позиции не подтверждён загруженным состоянием.</p>}</div>;
          })}
        </div>)}</div>
        <p className="small muted">Позиции сохраняются раздельно. Формальная проверка Z3 требует согласованного обмена исходными данными и доверенной проверки формализации.</p>
      </article>)}
    </section>
    <section aria-label="Точные находки группы"><h4>Состав и исходные основания</h4>
      {exactMembers.length !== group.members.length && <p className="notice bad">Часть ссылок не соответствует переданным состояниям. Подмена текущими находками не выполняется.</p>}
      {memberData.findings.map(finding => <FindingCard key={finding.id} finding={finding} data={memberData} projectId={projectId} detail />)}
    </section>
    <details><summary>Рассмотренная область и контекст</summary><div className="stack">
      <p className="small muted">Рассмотренные находки могут отличаться от состава группы. Документы используются как контекст.</p>
      {group.considered_findings.map(ref => <ExactRef key={`${ref.id}/${ref.state_id}`} projectId={projectId} value={ref} />)}
      {group.context.map((item, index) => <div key={index}><ExactRef projectId={projectId} value={item.ref} /><p className="small mono">Контекст: Unicode [{item.locator.start}, {item.locator.end})</p></div>)}
    </div></details>
    <p className="notice">Связи с требованиями и человеческие решения по требованиям пока не подключены.</p>
  </div>;
}
export function ProjectGroups({ api, projectId, groupId, stateId, onRecheck }: {
  api: ApiClient; projectId: string; groupId?: string; stateId?: string; onRecheck: () => void;
}) {
  const root = `/projects/${projectId}/groups`;
  const groups = usePages<GroupSummaryDTO>(api, root, onRecheck);
  const path = groupId ? `${root}/${encodeURIComponent(groupId)}${stateId ? `/states/${encodeURIComponent(stateId)}` : ''}` : undefined;
  const detail = useRead<GroupDetailDTO>(api, path, onRecheck);
  const response = detail.data;
  const group = response && response.id === groupId && (!stateId || response.state_id === stateId) ? response : undefined;
  return <div className="stack observer-space">
    {groupId && <><a className="source-link" href={projectHref(projectId, 'findings')}>← Все находки и группы</a>
      <Panel title={stateId ? 'Точное состояние группы' : 'Выбранная группа'}>
        {detail.loading && <Loading>Загружаем сохранённое состояние группы…</Loading>}
        {detail.error && <div className="panel-body"><ErrorNotice message={detail.error} /><button className="secondary" onClick={detail.reload}>Повторить загрузку группы</button></div>}
        {group && <GroupDetails projectId={projectId} group={group} />}
        {detail.data && !group && <p className="notice bad">Ответ не соответствует выбранной группе и состоянию.</p>}
      </Panel></>}
    <Panel title="Группы находок" extra={<span className="small muted">Загружено {groups.items.length}</span>}>
      <div className="panel-body stack">
        <p className="small muted">Чтение сохранённых групп доступно. Запуск группировки требует утверждения публичного контракта.</p>
        {groups.loading && <Loading>Загружаем группы…</Loading>}
        {groups.error && <ErrorNotice message={groups.error} />}
        {!groups.loading && !groups.error && !groups.items.length && <p className="notice">Сохранённых групп в этой выборке нет. Это не означает отсутствия находок или конфликтов.</p>}
        <div className="group-grid">{groups.items.map(item => <a className="group-card" key={item.id} href={groupStateHref(projectId, item.id, item.state_id)}>
          <h3>{item.title}</h3><p>{item.summary}</p><p className="mono small">{item.id}<br />{item.state_id}</p>
          <span className={`badge ${item.freshness === 'current' ? '' : 'warn'}`}>{item.freshness === 'current' ? 'Зависимости актуальны' : 'Требует актуализации'}</span>
          {item.synthetic && <span className="badge warn">Синтетическая группа</span>}<span className="source-link">Открыть точное состояние →</span>
        </a>)}</div>
        <div className="observer-row"><button className="secondary" onClick={groups.reload} disabled={groups.loading}>Обновить группы</button>
          {groups.next && <button className="secondary" onClick={groups.more} disabled={groups.loading}>Показать ещё группы</button>}</div>
        {groups.next && <p className="notice">Показана часть списка. Число загруженных групп не является итогом проекта.</p>}
      </div>
    </Panel>
  </div>;
}
