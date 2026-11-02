import { useId, useState } from 'react';
import type { Project } from '../api';
import { DecisionBadge, EvidenceCard, MissingData, PageHeading, Panel, RequirementBadges, Tabs, VerificationIssue, ViewNotice, evidenceName, verificationName } from './ui';
import { inProject, unavailable, viewData } from './viewModels';
import type { RequirementView, RequirementsView, ViewState } from './viewModels';

const tabs = [{ id: 'basis', label: 'Основания' }, { id: 'verification', label: 'Проверка' }, { id: 'history', label: 'История' }];
const filters = [
  ['all', 'Все требования'], ['draft', 'Черновики'], ['approved', 'Утверждённые'], ['rejected', 'Отклонённые'],
  ['blocker', 'Открытые блокеры'], ['issues', 'Все замечания'], ['lost', 'Утрата основания'],
  ['approved_all', 'Утверждённые · все основания'], ['approved_partial', 'Утверждённые · частичная утрата'], ['approved_lost', 'Утверждённые · полная утрата'],
];

function Inspector({ project, item }: { project: Project; item?: RequirementView }) {
  const draftInputId = useId();
  const [tab, setTab] = useState('basis');
  const [editing, setEditing] = useState(false);
  const target = item?.proposal ?? item;
  const [draft, setDraft] = useState(target?.wording ?? '');
  const [basis, setBasis] = useState<readonly string[]>(target?.evidence.filter(e => e.state === 'available' && e.source?.kind !== 'documents').map(e => e.id) ?? []);
  const unavailableReason = 'Серверные операции с редакциями, проверками и решениями пока не подключены.';
  return <section className="panel requirement-inspector" aria-label="Карточка выбранного требования">
    <div className="panel-head"><span className="mono">{item?.id ?? 'Требование не выбрано'}</span>
      <span className="small muted">{target ? `Редакция ${target.revision}` : 'Редакция —'}</span></div>
    <div className="panel-body">
      {item?.proposal && <div className="notice good"><strong>Действующая редакция {item.revision} · решение: <DecisionBadge decision={item.decision} /></strong>
        <p>{item.wording}</p><p>Отдельное предложение {item.proposal.revision} не заменяет действующую редакцию до решения человека.</p></div>}
      <div className="requirement-detail-heading"><h3>{item?.title ?? 'Выберите требование из списка'}</h3>
        {project.permissions.is_member && <button className="secondary" disabled={!item || editing || item.decision === 'Rejected'}
          title={item?.decision === 'Rejected' ? 'Процесс пересмотра отклонённого требования пока не определён.' : undefined} onClick={() => setEditing(true)}>
          {item?.proposal ? 'Редактировать предложение' : item?.decision === 'Approved' ? 'Предложить изменение' : 'Редактировать требование'}</button>}</div>
      <div className="status-grid" role="group" aria-label="Независимые состояния требования">
        <div><span>Решение человека</span><DecisionBadge decision={item?.proposal ? null : item?.decision ?? null} /></div>
        <div><span>Доступность оснований</span><span className="badge">{target ? evidenceName(target.evidenceState) : 'Нет данных'}</span></div>
        <div><span>AI-проверка</span><span className="badge">{target ? verificationName(target.verificationState) : 'Нет данных'}</span></div>
      </div>
      {editing && target ? <div className="requirement-editor stack" role="group" aria-label="Локальный черновик требования">
        <p className="notice warn">Локальный черновик · не сохранён. {unavailableReason}</p>
        <label htmlFor={draftInputId}>Формулировка требования</label><textarea id={draftInputId} autoFocus rows={5} value={draft} onChange={event => setDraft(event.target.value)} />
        <fieldset><legend>Выбранные доступные основания</legend>{target.evidence.map(evidence => <label key={evidence.id} className="basis-check">
          <input type="checkbox" disabled={evidence.state !== 'available' || evidence.source?.kind === 'documents'} checked={basis.includes(evidence.id)} onChange={event => {
            setBasis(previous => event.target.checked ? [...previous, evidence.id] : previous.filter(id => id !== evidence.id));
          }} />{evidence.sourceLabel}{evidence.state === 'deleted' ? ' · источник удалён' : ''}</label>)}</fieldset>
        <p className="small muted">{item?.decision === 'Approved' ? 'Действующая утверждённая редакция сохранится до принятия предложения.' : 'Новая редакция потребует отдельной проверки.'}</p>
        <div className="actions"><button disabled className="primary" title={unavailableReason}>Сохранить новую редакцию</button>
          <button className="secondary" onClick={() => { setEditing(false); setDraft(target.wording); setBasis(target.evidence.filter(e => e.state === 'available' && e.source?.kind !== 'documents').map(e => e.id)); }}>Отменить правки</button></div>
      </div> : <><span className="label-field">{item?.proposal ? 'Предлагаемая формулировка' : 'Формулировка'}</span>
        {target ? <p className="requirement-text">{target.wording}</p> : <MissingData />}
        {target?.originLabel && <p className="small muted observer-space">{target.originLabel}</p>}</>}
      {item?.decision === 'Approved' && (item.evidenceState === 'partial' || item.evidenceState === 'lost') &&
        <p className="notice bad observer-space">Историческое утверждение сохранено. Часть или все исходные основания недоступны.</p>}
    </div>
    {!editing && <Tabs tabs={tabs} selected={tab} onSelect={setTab} label="Детали требования">
      {!target ? <MissingData>Для просмотра оснований, проверки и истории нужны данные выбранного требования.</MissingData>
        : tab === 'basis' ? <div className="stack">
          <h4>Почему предложено это требование</h4>{target.rationale && <p>{target.rationale}</p>}
          {target.evidence.length ? target.evidence.map(evidence => <EvidenceCard key={evidence.id} projectId={project.id} evidence={evidence} />)
            : <p className="notice warn">В этой выборке основания не переданы.</p>}
          {target.context.length > 0 && <><h4>Контекст продукта · не основание потребности</h4>
            {target.context.map(evidence => <EvidenceCard key={evidence.id} projectId={project.id} evidence={evidence} context />)}</>}
        </div> : tab === 'verification' ? <div className="stack">
          <div className={`notice ${target.verificationState === 'current' ? 'good' : 'warn'}`}>
            <strong>{verificationName(target.verificationState)} · редакция {target.revision}</strong>
            <p>AI-проверка не является человеческим утверждением.</p>{target.coverage && <p>{target.coverage}</p>}</div>
          <h4>Замечания и конфликты</h4>{target.issues.filter(issue => issue.kind !== 'question').map(issue => <VerificationIssue key={issue.id} issue={issue} />)}
          {!target.issues.some(issue => issue.kind !== 'question') && <p className="small muted">В загруженной проверке замечания не переданы. Это не закрывает прежние блокеры.</p>}
          <h4>Открытые вопросы</h4>{target.issues.filter(issue => issue.kind === 'question').map(issue => <VerificationIssue key={issue.id} issue={issue} />)}
          {!target.issues.some(issue => issue.kind === 'question') && <p className="small muted">В загруженной проверке вопросы не переданы.</p>}
          <button className="secondary" disabled title={unavailableReason}>Проверить эту редакцию</button>
        </div> : <div className="stack">{target.history.length ? target.history.map(event => <article className="history-item" key={event.id}>
          <h4>{event.title}</h4>{event.text && <p>{event.text}</p>}<p className="small muted">{[event.author, event.time].filter(Boolean).join(' · ')}</p></article>)
          : <MissingData empty>История этой редакции не передана.</MissingData>}
          <p className="notice">Сохранённая редакция неизменяема. Проверка и решение прежней редакции не переносятся на новую.</p></div>}
    </Tabs>}
    <div className="decision-bar"><p className="small muted">{target?.issues.some(issue => issue.open && issue.blocking)
      ? 'Открыт блокер. Новое утверждение недоступно.' : unavailableReason}</p>
      {project.permissions.can_approve ? <div className="actions"><button disabled className="primary" title={unavailableReason}>Утвердить</button>
        <button disabled className="secondary" title={unavailableReason}>Отклонить</button></div> : <p className="small muted">Для решения человека требуется право Approver.</p>}
    </div>
  </section>;
}

export function RequirementsScreen({ project, state, selectedId, onSelect }: {
  project: Project; state?: ViewState<RequirementsView>; selectedId?: string; onSelect?: (id: string) => void;
}) {
  const current = inProject(state ?? unavailable<RequirementsView>(project.id, 'Список требований и операции с редакциями пока недоступны.'), project.id);
  const data = viewData(current);
  const [search, setSearch] = useState(''); const [filter, setFilter] = useState('all');
  const [localSelected, setLocalSelected] = useState<string>();
  const items = data?.items ?? [];
  const filtered = items.filter(item => {
    const match = filter === 'all' || filter === 'draft' && item.decision === 'Draft' || filter === 'approved' && item.decision === 'Approved'
      || filter === 'rejected' && item.decision === 'Rejected' || filter === 'blocker' && item.openBlockingIssues
      || filter === 'issues' && (item.proposal ?? item).issues.some(issue => issue.open)
      || filter === 'lost' && (item.evidenceState === 'partial' || item.evidenceState === 'lost')
      || filter === 'approved_all' && item.decision === 'Approved' && item.evidenceState === 'available'
      || filter === 'approved_partial' && item.decision === 'Approved' && item.evidenceState === 'partial'
      || filter === 'approved_lost' && item.decision === 'Approved' && item.evidenceState === 'lost';
    return match && `${item.id} ${item.title}`.toLocaleLowerCase('ru').includes(search.toLocaleLowerCase('ru'));
  });
  const chosen = selectedId ?? localSelected;
  const selected = chosen ? filtered.find(item => item.id === chosen) : filtered[0];
  return <div className="requirements-screen"><PageHeading title="Требования" description="Рассмотрите основания, уточните формулировку и примите решение." />
    <ViewNotice state={current} />
    <div className="panel requirements-toolbar"><label className="search-field"><span className="sr-only">Поиск требования</span>
      <input type="search" placeholder="Найти требование" disabled={!data} value={search} onChange={event => setSearch(event.target.value)} /></label>
      <select className="observer-select" aria-label="Фильтр требований" disabled={!data} value={filter} onChange={event => setFilter(event.target.value)}>
        {filters.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>
      <button className="secondary" disabled={!data || !search && filter === 'all'} onClick={() => { setSearch(''); setFilter('all'); }}>Сбросить фильтр</button>
    </div>
    {current.status === 'partial' && <p className="small muted observer-space">Поиск и фильтры применяются только к загруженной части.</p>}
    <div className="requirements-workspace observer-space"><Panel title="Реестр требований" className="requirement-register"
      extra={<span className="small muted">{data ? `Загружено ${items.length}` : 'Нет данных'}</span>}>
      {filtered.length ? filtered.map(item => <button className={`req-row ${selected?.id === item.id ? 'selected' : ''}`} key={item.id}
        aria-pressed={selected?.id === item.id} onClick={() => { setLocalSelected(item.id); onSelect?.(item.id); }}>
        <span className="observer-row between"><span className="mono muted">{item.id}</span><span className="small muted">{item.revision}</span></span>
        <strong>{item.title}</strong><RequirementBadges item={item} />
      </button>) : <MissingData loading={current.status === 'loading'} empty={!!data || current.status === 'empty'} />}
      <p className="panel-body small muted">Решение, основания и замечания — отдельные признаки. Предложение не считается вторым требованием.</p>
    </Panel><div>{chosen && !selected && data && <p className="notice warn">Выбранное требование отсутствует в загруженной выборке.</p>}
      <Inspector key={`${project.id}/${selected?.id ?? 'none'}`} project={project} item={selected} /></div></div>
  </div>;
}
