import type { Project } from './api';
import { Permissions } from './ui';
import { projectHref, groupHref, requirementHref, requirementsFilterHref } from './routes';
import type { RequirementFilter } from './routes';
import type { ReactNode } from 'react';
import { DecisionBadge, MissingData, PageHeading, Panel, ViewNotice, evidenceName, verificationName } from './observer/ui';
import { inProject, unavailable, viewData } from './observer/viewModels';
import type { OverviewView, ViewState } from './observer/viewModels';

const isCount = (value: number | null | undefined): value is number => value != null && Number.isSafeInteger(value) && value >= 0;
const count = (value: number | null | undefined) => isCount(value) ? value.toLocaleString('ru-RU') : '—';
const unknownReason = 'Переход недоступен: подтверждённые данные этой выборки пока не получены.';

function FilterLink({ projectId, filter, enabled, className, children }: {
  projectId: string; filter: RequirementFilter; enabled: boolean; className: string; children: ReactNode;
}) {
  return enabled ? <a className={className} href={requirementsFilterHref(projectId, filter)}>{children}</a>
    : <div className={className} aria-disabled="true" title={unknownReason}>{children}</div>;
}

function DecisionChart({ decisions, projectId }: { decisions?: OverviewView['decisions']; projectId: string }) {
  const values = decisions ? [decisions.draft, decisions.approved, decisions.rejected] : null;
  const sum = values?.every(isCount) ? values.reduce((result, value) => result + value, 0) : null;
  const known = isCount(sum);
  const total = known ? sum : null;
  const colors = ['var(--draft)', 'var(--approved)', 'var(--rejected)'];
  const circumference = 2 * Math.PI * 75.5;
  let offset = 0;
  return <div className="panel-body">
    <div className="decision-donut" role="img" aria-label={total === null ? 'Распределение решений: данные пока недоступны'
      : `Решения человека: черновиков ${values![0]}, утверждено ${values![1]}, отклонено ${values![2]}`}>
      <svg viewBox="0 0 170 170" aria-hidden="true"><circle cx="85" cy="85" r="75.5" className="donut-track" />
        {total !== null && total > 0 && values!.map((value, index) => {
          const length = value / total * circumference;
          const start = offset; offset += length;
          return <circle key={index} cx="85" cy="85" r="75.5" fill="none" stroke={colors[index]} strokeWidth="19"
            strokeDasharray={`${length} ${circumference - length}`} strokeDashoffset={-start} transform="rotate(-90 85 85)" />;
        })}</svg>
      <div className="donut-center"><strong>{count(total)}</strong><span>{total === null ? 'нет данных' : 'требований'}</span></div>
    </div>
    <div className="decision-legend">{(['draft', 'approved', 'rejected'] as const).map((filter, index) =>
      <FilterLink key={filter} className="decision-category" projectId={projectId} filter={filter} enabled={known}>
        <i style={{ background: colors[index] }} /><span>{['Черновик', 'Утверждено', 'Отклонено'][index]}</span><b>{known ? count(values![index]) : '—'}</b></FilterLink>)}</div>
    {!known && <p className="small muted overview-unavailable">{unknownReason}</p>}
    <p className="small muted observer-space">Три категории человеческого решения. Предложения изменений не считаются отдельными требованиями.</p>
  </div>;
}

export function ProjectOverview({ project, state, runtime, processingAvailable = false }: { project: Project; state?: ViewState<OverviewView>; runtime?: ReactNode; processingAvailable?: boolean }) {
  const current = inProject(state ?? unavailable<OverviewView>(project.id, 'Сводные данные анализа пока недоступны. Материалы и доступ уже работают.'), project.id);
  const data = viewData(current);
  const aggregates = data?.aggregatesAuthoritative ? data : undefined;
  const empty = current.status === 'empty' || current.status === 'ready';
  const metrics = [
    ['Требований', aggregates?.metrics.requirements, 'По устойчивой идентичности', 'all'],
    ['Утверждено', aggregates?.metrics.approved, 'Человеческое решение', 'approved'],
    ['Открытых блокеров', aggregates?.metrics.blockers, 'Требуют уточнения', 'blocker'],
    ['Утверждено без всех оснований', aggregates?.metrics.lostEvidence, 'Решение сохранено', 'lost'],
  ] as const;
  return <div className="observer-overview">
    <PageHeading title="Обзор проекта" description="Обратная связь, требования и вопросы, которые требуют вашего внимания." />
    <ViewNotice state={current} feature={false} />
    <div className="metric-grid" role="group" aria-label="Показатели проекта">{metrics.map(([label, value, hint, filter]) =>
      <FilterLink className="panel metric" key={label} projectId={project.id} filter={filter} enabled={isCount(value)}><span className="metric-label">{label}</span>
        <strong className="metric-value">{count(value)}</strong><span className="metric-hint">{isCount(value) ? hint : 'Данные пока недоступны · переход недоступен'}</span></FilterLink>)}</div>
    <div className="observer-twos">
      <Panel title="Группы обратной связи" extra={<span className="small muted">Нажмите на группу, чтобы открыть связи</span>} className="overview-groups">
        <div className="panel-body groups-body">{data?.groups.length ? data.groups.map(group =>
          <a key={group.id} className="group-summary" href={groupHref(project.id, group.id)}><strong>{group.title}<span aria-hidden="true"> →</span></strong>
            <div className="group-bar" role="img" aria-label={isCount(group.findings) && isCount(data.groupScaleMaximum) && group.findings <= data.groupScaleMaximum
              ? `Относительное количество находок: ${count(group.findings)} из ${count(data.groupScaleMaximum)}` : 'Относительное количество находок неизвестно'}>
              {isCount(group.findings) && isCount(data.groupScaleMaximum) && group.findings <= data.groupScaleMaximum
                ? <span style={{ width: `${data.groupScaleMaximum ? group.findings / data.groupScaleMaximum * 100 : 0}%` }} />
                : <span className="group-bar-unknown" />}</div>
            <span className="group-counts"><span>Находок: {count(group.findings)}</span><span>Требований: {count(group.requirements)}</span><span>Открытых замечаний: {count(group.openIssues)}</span></span></a>)
          : <MissingData loading={current.status === 'loading'} empty={empty}>{empty ? 'Групп в полученной выборке нет.' : 'Сведения о группах пока не получены.'}</MissingData>}
          <p className="small muted observer-space">Количество находок, а не уникальных участников. Замечания относятся к связанным требованиям.
            {data?.groups.length ? ' Полосы используют переданный масштаб; неизвестное соотношение обозначено пунктиром.' : ''}</p></div>
      </Panel>
      <Panel title="Решения по требованиям" extra={<span className="small muted">Решение человека</span>}><DecisionChart projectId={project.id} decisions={aggregates?.decisions} /></Panel>
    </div>
    <div className="observer-twos observer-space">
      <Panel title="Нуждается во внимании" extra={<span aria-hidden="true">◇</span>}>
        {data?.attention.length ? data.attention.map(item => <a className="req-row" key={item.id} href={requirementHref(project.id, item.id)}>
          <div className="observer-row between"><span className="mono muted">{item.id}</span><DecisionBadge decision={item.decision} /></div><strong>{item.title}</strong>
          <div className="observer-badges"><span className={`badge ${item.evidenceState === 'available' ? 'good' : item.evidenceState === 'lost' ? 'bad' : 'warn'}`}>{evidenceName(item.evidenceState)}</span>
            <span className={`badge ${item.openBlockingIssues ? 'warn' : ''}`}>{item.openBlockingIssues == null ? 'Блокеры: —' : item.openBlockingIssues ? 'Открыт блокер' : 'Открытых блокеров нет'}</span>
            <span className={`badge ${isCount(item.openIssues) && item.openIssues > 0 ? 'warn' : ''}`}>Открытых замечаний: {count(item.openIssues)}</span>
            {item.verificationState !== 'unavailable' && <span className={`badge ${item.verificationState === 'current' ? 'good' : 'warn'}`}>Проверка: {verificationName(item.verificationState)}</span>}</div></a>)
          : <MissingData loading={current.status === 'loading'} empty={empty}>{empty ? 'Открытых случаев в полученной выборке нет.' : 'Сведения об открытых случаях пока не получены.'}</MissingData>}
      </Panel>
      <Panel title="Основания утверждённых требований"><div className="panel-body">
        {(['available', 'partial', 'lost'] as const).map((key, index) => <FilterLink className="availability-row" key={key} projectId={project.id}
          filter={(['approved_all', 'approved_partial', 'approved_lost'] as const)[index]} enabled={isCount(aggregates?.approvedEvidence[key])}>
          <span>{['Доступны все основания', 'Частичная утрата', 'Полная утрата'][index]}</span>
          <span className="observer-row"><span className={`badge ${['good', 'warn', 'bad'][index]}`}>{count(aggregates?.approvedEvidence[key])}</span><span aria-hidden="true">→</span></span></FilterLink>)}
        <p className="small muted observer-space">{aggregates ? 'Каждая известная категория открывает свою выборку, в том числе пустую.' : unknownReason}</p>
        <p className="notice warn observer-space">Утрата источника не отменяет историческое утверждение.
          Доступность и смысловая достаточность оснований оцениваются отдельно.</p>
      </div></Panel>
    </div>
    <p className="small muted observer-space">{data?.coverage ?? 'Показатели не вычисляются по частично загруженным страницам материалов.'}</p>
    <details className="observer-live-tools observer-space" open><summary>Поддерживаемые операции и ваши полномочия</summary>
      {runtime}
      <div className="observer-twos observer-space"><section className="panel overview-panel stack" aria-label="Возможности проекта">
        <h3>Доступные действия</h3><div className="live-capabilities">
          <p>Текстовые отзывы <span className="capability-state">Доступно</span></p>
          <p>Документация <span className="capability-state">Доступно</span></p>
          <p>{processingAvailable ? 'Обработка сохранённых текстов' : 'Семантический анализ'} <span className="capability-state">{processingAvailable ? 'Доступно' : 'Не подключено'}</span></p>
        </div><a className="primary action-link" href={projectHref(project.id, 'materials')}>Открыть материалы →</a>
        {project.permissions.is_owner && <a className="secondary action-link" href={projectHref(project.id, 'access')}>Управлять доступом</a>}
      </section><section className="panel overview-panel stack"><h3>Ваши полномочия</h3><Permissions project={project} />
        <p className="muted">{project.permissions.is_owner ? 'Вы — владелец этого проекта с правами участника и утверждения.'
          : project.permissions.can_approve ? 'Вы — участник с дополнительным правом утверждения.' : 'Вы — участник этого проекта.'}</p>
        <dl><dt>Идентификатор проекта</dt><dd className="mono">{project.id}</dd></dl>
      </section></div>
    </details>
  </div>;
}
