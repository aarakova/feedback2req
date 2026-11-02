import type { Project } from './api';
import { Permissions } from './ui';
import { projectHref, groupHref, requirementHref } from './routes';
import { MissingData, PageHeading, Panel, RequirementBadges, ViewNotice } from './observer/ui';
import { inProject, unavailable, viewData } from './observer/viewModels';
import type { OverviewView, ViewState } from './observer/viewModels';

const count = (value: number | null | undefined) => value != null && Number.isFinite(value) && value >= 0 ? value.toLocaleString('ru-RU') : '—';

function DecisionChart({ decisions }: { decisions?: OverviewView['decisions'] }) {
  const values = decisions ? [decisions.draft, decisions.approved, decisions.rejected] : null;
  const known = values?.every(value => Number.isFinite(value) && value >= 0);
  const total = known ? values!.reduce((sum, value) => sum + value, 0) : null;
  const colors = ['var(--draft)', 'var(--approved)', 'var(--rejected)'];
  const circumference = 2 * Math.PI * 62;
  let offset = 0;
  return <div className="panel-body">
    <div className="decision-donut" role="img" aria-label={total === null ? 'Распределение решений: данные пока недоступны'
      : `Решения человека: черновиков ${values![0]}, утверждено ${values![1]}, отклонено ${values![2]}`}>
      <svg viewBox="0 0 170 170" aria-hidden="true"><circle cx="85" cy="85" r="62" className="donut-track" />
        {total !== null && total > 0 && values!.map((value, index) => {
          const length = value / total * circumference;
          const start = offset; offset += length;
          return <circle key={index} cx="85" cy="85" r="62" fill="none" stroke={colors[index]} strokeWidth="23"
            strokeDasharray={`${length} ${circumference - length}`} strokeDashoffset={-start} transform="rotate(-90 85 85)" />;
        })}</svg>
      <div className="donut-center"><strong>{count(total)}</strong><span>{total === null ? 'нет данных' : 'требований'}</span></div>
    </div>
    <div className="decision-legend">{['Черновик', 'Утверждено', 'Отклонено'].map((label, index) =>
      <div key={label}><i style={{ background: colors[index] }} /><span>{label}</span><b>{known ? count(values![index]) : '—'}</b></div>)}</div>
    <p className="small muted observer-space">Три категории человеческого решения. Предложения изменений не считаются отдельными требованиями.</p>
  </div>;
}

export function ProjectOverview({ project, state }: { project: Project; state?: ViewState<OverviewView> }) {
  const current = inProject(state ?? unavailable<OverviewView>(project.id, 'Сводные данные анализа пока недоступны. Материалы и доступ уже работают.'), project.id);
  const data = viewData(current);
  const aggregates = data?.aggregatesAuthoritative ? data : undefined;
  const metrics = [
    ['Требований', aggregates?.metrics.requirements, 'По устойчивой идентичности'],
    ['Утверждено', aggregates?.metrics.approved, 'Человеческое решение'],
    ['Открытых блокеров', aggregates?.metrics.blockers, 'Требуют уточнения'],
    ['Утверждено без всех оснований', aggregates?.metrics.lostEvidence, 'Решение сохранено'],
  ] as const;
  return <div className="observer-overview">
    <PageHeading title="Обзор проекта" description="Обратная связь, требования и вопросы, которые требуют вашего внимания." />
    <ViewNotice state={current} feature={false} />
    <div className="metric-grid" role="group" aria-label="Показатели проекта">{metrics.map(([label, value, hint]) =>
      <article className="panel metric" key={label}><span className="metric-label">{label}</span>
        <strong className="metric-value">{count(value)}</strong><span className="metric-hint">{value == null ? 'Данные пока недоступны' : hint}</span></article>)}</div>
    <div className="observer-twos">
      <Panel title="Группы обратной связи" extra={<span className="small muted">Состав и связи</span>}>
        <div className="panel-body groups-body">{data?.groups.length ? data.groups.map(group =>
          <a key={group.id} className="group-summary" href={groupHref(project.id, group.id)}><strong>{group.title}<span aria-hidden="true"> →</span></strong>
            <span className="group-counts">Находок: {count(group.findings)} · Требований: {count(group.requirements)}</span></a>)
          : <MissingData loading={current.status === 'loading'} empty={!!data || current.status === 'empty'} />}
          <p className="small muted observer-space">Количество находок, а не уникальных участников. Противоположные позиции сохраняются отдельно.</p></div>
      </Panel>
      <Panel title="Решения по требованиям" extra={<span className="small muted">Решение человека</span>}><DecisionChart decisions={aggregates?.decisions} /></Panel>
    </div>
    <div className="observer-twos observer-space">
      <Panel title="Нуждается во внимании" extra={<span aria-hidden="true">◇</span>}>
        {data?.attention.length ? data.attention.map(item => <a className="req-row" key={item.id} href={requirementHref(project.id, item.id)}>
          <span className="mono muted">{item.id}</span><strong>{item.title}</strong><RequirementBadges item={item} /></a>)
          : <MissingData loading={current.status === 'loading'} empty={!!data || current.status === 'empty'} />}
      </Panel>
      <Panel title="Основания утверждённых требований"><div className="panel-body">
        {(['available', 'partial', 'lost'] as const).map((key, index) => <div className="availability-row" key={key}>
          <span>{['Доступны все основания', 'Частичная утрата', 'Полная утрата'][index]}</span>
          <span className={`badge ${['good', 'warn', 'bad'][index]}`}>{count(aggregates?.approvedEvidence[key])}</span></div>)}
        <p className="notice warn observer-space">Утрата источника не отменяет историческое утверждение.
          Доступность и смысловая достаточность оснований оцениваются отдельно.</p>
      </div></Panel>
    </div>
    <p className="small muted observer-space">{data?.coverage ?? 'Показатели не вычисляются по частично загруженным страницам материалов.'}</p>
    <details className="observer-live-tools observer-space" open><summary>Поддерживаемые операции и ваши полномочия</summary>
      <div className="observer-twos observer-space"><section className="panel overview-panel stack" aria-label="Возможности проекта">
        <h3>Доступные действия</h3><div className="live-capabilities">
          <p>Текстовые отзывы <span className="capability-state">Доступно</span></p>
          <p>Документация <span className="capability-state">Доступно</span></p>
          <p>Семантический анализ <span className="capability-state">Не подключено</span></p>
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
