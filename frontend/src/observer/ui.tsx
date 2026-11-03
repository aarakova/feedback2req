import { useId, useRef } from 'react';
import type { ReactNode } from 'react';
import { Loading } from '../ui';
import type { Decision, EvidenceState, EvidenceView, IssueView, RequirementSummary, VerificationState, ViewState } from './viewModels';
import { projectHref } from '../routes';

export function Panel({ title, children, extra, className = '' }: {
  title: string; children: ReactNode; extra?: ReactNode; className?: string;
}) {
  const id = useId();
  return <section className={`panel observer-panel ${className}`} aria-labelledby={id}>
    <div className="panel-head"><h3 id={id}>{title}</h3>{extra}</div>{children}
  </section>;
}
export function PageHeading({ title, description, children, label }: {
  title: string; description: string; children?: ReactNode; label?: string;
}) {
  return <div className="observer-heading"><div><h2 aria-label={label}>{title}</h2><p>{description}</p></div>{children}</div>;
}
export function ViewNotice<T>({ state, feature = true }: { state: ViewState<T>; feature?: boolean }) {
  if (state.status === 'ready' || state.status === 'empty') return null;
  if (state.status === 'loading') return <Loading>Загружаем данные раздела…</Loading>;
  return <div className={`view-notice notice ${state.status === 'error' ? 'bad' : state.status === 'partial' ? 'warn' : ''}`}
    role={state.status === 'error' ? 'alert' : 'status'}>
    {state.status === 'unavailable' && feature && <span className="badge">Функция не подключена</span>}
    <p>{state.message}</p>
  </div>;
}
export function MissingData({ loading = false, empty = false, children }: { loading?: boolean; empty?: boolean; children?: ReactNode }) {
  return <div className="observer-empty"><span aria-hidden="true" className="empty-glyph">{loading ? '◌' : '—'}</span>
    <p>{children ?? (loading ? 'Данные загружаются' : empty ? 'В загруженном наборе нет записей' : 'Данные пока недоступны')}</p></div>;
}
export const decisionName = (decision: Decision | null) => decision === 'Approved' ? 'Утверждено'
  : decision === 'Rejected' ? 'Отклонено' : decision === 'Draft' ? 'Черновик' : 'Нет данных';
export function DecisionBadge({ decision }: { decision: Decision | null }) {
  return <span className={`badge decision-${decision?.toLowerCase() ?? 'unknown'}`}>{decisionName(decision)}</span>;
}
export const evidenceName = (state: EvidenceState) => ({ available: 'Основания доступны', partial: 'Частичная утрата', lost: 'Полная утрата', unknown: 'Нет данных об основаниях' })[state];
export const verificationName = (state: VerificationState) => ({ current: 'Актуальна', stale: 'Требует актуализации', not_checked: 'Не проверена', unavailable: 'Нет данных о проверке' })[state];
export function RequirementBadges({ item }: { item: RequirementSummary }) {
  return <div className="observer-badges"><DecisionBadge decision={item.decision} />
    <span className={`badge ${item.evidenceState === 'available' ? 'good' : item.evidenceState === 'lost' ? 'bad' : 'warn'}`}>{evidenceName(item.evidenceState)}</span>
    {item.openBlockingIssues && <span className="badge warn">Открыт блокер</span>}
    {item.verificationState !== 'current' && <span className="badge warn">{verificationName(item.verificationState)}</span>}
  </div>;
}
export function EvidenceCard({ evidence, projectId, context = false }: { evidence: EvidenceView; projectId: string; context?: boolean }) {
  const productContext = context || evidence.source?.kind === 'documents';
  return <article className="basis-evidence" aria-label={`${productContext ? 'Контекст' : 'Свидетельство'}: ${evidence.sourceLabel}`}>
    <div className="observer-row between"><strong>{evidence.sourceLabel}</strong><span className="badge">{productContext ? 'Контекст продукта' : 'Исходное свидетельство'}</span></div>
    {evidence.interpretation && <p>{evidence.interpretation}</p>}
    {productContext && <p className="small muted">Документация не является самостоятельным основанием потребности.</p>}
    {evidence.state === 'available' ? <>
      {evidence.quote && <blockquote className="quote"><p>«{evidence.quote}»</p></blockquote>}
      {evidence.position && <p className="small muted">{evidence.position}</p>}
      {evidence.source ? <a className="source-link" href={`${projectHref(projectId, 'materials')}/${evidence.source.kind}/${encodeURIComponent(evidence.source.id)}`}>Открыть источник ↗</a>
        : <p className="small muted">Переход к источнику пока недоступен.</p>}
    </> : <p className={`notice ${evidence.state === 'deleted' ? 'bad' : 'warn'}`}>
      {evidence.state === 'deleted' ? 'Источник удалён. Исходный фрагмент недоступен; историческая связь не заменяет подтверждение.' : 'Исходное свидетельство сейчас недоступно.'}
    </p>}
  </article>;
}
export function VerificationIssue({ issue }: { issue: IssueView }) {
  return <article className="verification-issue">
    <div className="observer-badges"><span className="badge">Серьёзность: {issue.severity}</span>
      <span className={`badge ${issue.blocking ? 'bad' : ''}`}>{issue.blocking ? 'Блокирует новое утверждение' : 'Неблокирующее'}</span>
      <span className={`badge ${issue.open ? 'warn' : 'good'}`}>{issue.open ? 'Открыто' : issue.resolution ? 'Явно разрешено' : 'Нет данных об обосновании закрытия'}</span></div>
    <h4>{issue.title}</h4><p>{issue.text}</p>
    {issue.positions && <div className="conflict-pair">{issue.positions.map(position => <div key={position.label} className="notice warn">
      <strong>{position.label}</strong><p>{position.text}</p></div>)}</div>}
    {issue.resolution && <p className="notice good">Обоснование решения человека: {issue.resolution}</p>}
  </article>;
}
export function Tabs({ tabs, selected, onSelect, label, children }: {
  tabs: readonly { id: string; label: string }[]; selected: string; onSelect: (id: string) => void;
  label: string; children: ReactNode;
}) {
  const prefix = useId();
  const buttons = useRef<(HTMLButtonElement | null)[]>([]);
  return <><div className="observer-tabs" role="tablist" aria-label={label}>
    {tabs.map((tab, index) => <button type="button" key={tab.id} ref={node => { buttons.current[index] = node; }}
      role="tab" id={`${prefix}-${tab.id}`} aria-controls={`${prefix}-panel`} aria-selected={selected === tab.id}
      tabIndex={selected === tab.id ? 0 : -1} onClick={() => onSelect(tab.id)} onKeyDown={event => {
        const next = event.key === 'ArrowRight' ? (index + 1) % tabs.length : event.key === 'ArrowLeft'
          ? (index - 1 + tabs.length) % tabs.length : event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 : -1;
        if (next >= 0) { event.preventDefault(); onSelect(tabs[next].id); buttons.current[next]?.focus(); }
      }}>{tab.label}</button>)}
  </div><div role="tabpanel" id={`${prefix}-panel`} aria-labelledby={`${prefix}-${selected}`} tabIndex={0}
    className="panel-body observer-tabpanel">{children}</div></>;
}
