import { useState } from 'react';
import type { ReactNode } from 'react';
import type { Project } from '../api';
import { findingHref, groupHref, projectHref, requirementHref } from '../routes';
import { ResultDetails } from '../processing/ResultDetails';
import { EvidenceCard, MissingData, PageHeading, Panel, RequirementBadges, Tabs, VerificationIssue, ViewNotice } from './ui';
import { inProject, unavailable, viewData } from './viewModels';
import type { FindingView, FindingsView, ViewState } from './viewModels';

const groupTabs = [{ id: 'findings', label: 'Находки' }, { id: 'requirements', label: 'Требования' }, { id: 'issues', label: 'Замечания требований' }];

export function FindingCard({ finding, data, projectId, detail = false }: { finding: FindingView; data: FindingsView; projectId: string; detail?: boolean }) {
  const opponents = data.findings.filter(item => finding.conflictsWith.includes(item.id));
  return <article className="finding-card" id={`finding-${encodeURIComponent(finding.id)}`} tabIndex={-1}>
    <div className="observer-badges">{finding.types.map(type => <span className="badge blue" key={type}>{type}</span>)}
      <span className="badge">{finding.originLabel}</span>{finding.humanEdited && <span className="badge warn">Правка человека</span>}
      <span className="mono muted">{finding.id}</span></div>
    <h4>{finding.text}</h4>
    {finding.extraction && <div className="stack">
      <p className={`notice ${finding.extraction.stale ? 'warn' : ''}`}>{finding.extraction.freshness}</p>
      <p className="mono small muted">Состояние находки: {finding.extraction.stateId}<br />Попытка: {finding.extraction.attemptId}<br />Создано: {finding.extraction.createdAt}</p>
      <ResultDetails value={finding.extraction} />
      {!detail && <a className="source-link" href={findingHref(projectId, finding.id)}>Открыть находку ↗</a>}
    </div>}
    {finding.evidence.map(evidence => <EvidenceCard key={evidence.id} evidence={evidence} projectId={projectId} />)}
    {finding.conflictsWith.length > 0 && <div className="conflict-notice">
      <strong>Конфликтующие позиции · не усреднять</strong>
      <div className="conflict-pair"><div className="notice warn"><strong>Эта позиция</strong><p>{finding.text}</p></div>
        {opponents.map(item => <div className="notice warn" key={item.id}><strong>Другая позиция</strong><p>{item.text}</p>
          <a className="source-link" href={data.groups.find(group => group.findingIds.includes(item.id))
            ? groupHref(projectId, data.groups.find(group => group.findingIds.includes(item.id))!.id) : projectHref(projectId, 'findings')}
            onClick={event => {
              const target = document.getElementById(`finding-${encodeURIComponent(item.id)}`);
              if (target) { event.preventDefault(); target.focus(); target.scrollIntoView({ block: 'center' }); }
          }}>Открыть противоположную позицию</a></div>)}</div>
      {opponents.length !== finding.conflictsWith.length && <p className="small muted">Часть конфликтующих позиций не загружена.</p>}
    </div>}
    <div className="observer-space"><strong className="small">Связанные требования</strong><div className="related-links">
      {data.relationsAvailable === false ? <span className="small muted">Связи с требованиями пока не подключены.</span> : finding.requirementIds.length ? finding.requirementIds.map(id => <a key={id} href={requirementHref(projectId, id)}>
        {data.requirements.find(item => item.id === id)?.title ?? id} ↗</a>) : <span className="small muted">В этой выборке связи не переданы.</span>}</div></div>
  </article>;
}

export function FindingsScreen({ project, state, selectedGroupId, onSelectGroup, runtime, controls, groupRuntime, detailMode = false }: {
  project: Project; state?: ViewState<FindingsView>; selectedGroupId?: string; onSelectGroup?: (id: string | undefined) => void;
  runtime?: ReactNode; controls?: ReactNode; groupRuntime?: ReactNode; detailMode?: boolean;
}) {
  const current = inProject(state ?? unavailable<FindingsView>(project.id, 'Находки, группы и связи с исходными свидетельствами пока недоступны.'), project.id);
  const data = viewData(current);
  const [localGroup, setLocalGroup] = useState<string>(); const [tab, setTab] = useState('findings');
  const chosen = selectedGroupId ?? localGroup;
  const selected = data?.groups.find(group => group.id === chosen);
  const findings = selected ? data!.findings.filter(item => selected.findingIds.includes(item.id)) : data?.findings ?? [];
  const select = (id: string | undefined) => { setLocalGroup(id); setTab('findings'); onSelectGroup?.(id); };
  return <div className="findings-screen">
    <PageHeading title={selected?.title ?? 'Находки и группы'} label="Находки" description={runtime ? 'Результаты извлечения из текстовой обратной связи и их исходные свидетельства.' : 'Откройте группу, чтобы увидеть её состав, требования и замечания.'} />
    <ViewNotice state={current} />
    {runtime}
    {chosen ? <><a className="source-link" href={projectHref(project.id, 'findings')} onClick={event => {
      if (onSelectGroup) { event.preventDefault(); select(undefined); }
    }}>← К находкам и группам</a>
      <Panel title="Состав группы" className="observer-space"><Tabs tabs={groupTabs} selected={tab} onSelect={setTab} label="Содержимое группы">
        {data?.groupsAvailable === false ? <div className="stack"><span className="badge">Функция не подключена</span><p>Группировка F2 пока не предоставляет состав группы. Отсутствие API не означает отсутствие групп.</p></div>
          : !selected || !data ? <MissingData>{data ? 'Группа отсутствует в загруженной выборке.' : 'Состав группы пока недоступен.'}</MissingData>
          : tab === 'findings' ? <>
            {selected.summary && <p className="notice">{selected.summary}</p>}
            {selected.conflict && <p className="notice warn">В группе есть несовместимые ожидания. Обе позиции показаны отдельно.</p>}
            {findings.map(finding => <FindingCard key={finding.id} finding={finding} data={data} projectId={project.id} />)}
            {findings.length !== selected.findingIds.length && <p className="notice warn">Часть состава группы не загружена.</p>}
            {!findings.length && <MissingData empty />}
          </> : tab === 'requirements' ? <div className="stack">{data.requirements.filter(item => selected.requirementIds.includes(item.id)).map(item =>
            <a className="req-row" key={item.id} href={requirementHref(project.id, item.id)}><strong>{item.title}</strong><RequirementBadges item={item} /></a>)}
            <p className="small muted">Связи показаны через находки. Каждое загруженное требование представлено один раз.</p>
            {selected.requirementIds.some(id => !data.requirements.some(item => item.id === id)) && <p className="notice warn">Часть связанных требований не загружена.</p>}
            {!selected.requirementIds.length && <MissingData empty />}</div>
          : data.requirementIssues ? <div className="stack">
            {data.requirementIssues.filter(item => selected.requirementIds.includes(item.requirementId)).map(item => <div key={`${item.requirementId}/${item.issue.id}`}>
              <a className="source-link" href={requirementHref(project.id, item.requirementId)}>{item.requirementTitle} · открыть требование ↗</a>
              <VerificationIssue issue={item.issue} /></div>)}
            {!data.requirementIssues.some(item => selected.requirementIds.includes(item.requirementId)) && <MissingData empty />}
            <p className="small muted">Замечания принадлежат проверкам требований, а не самой группе.</p>
          </div> : <MissingData>Замечания проверок требований в этой выборке не переданы.</MissingData>}
      </Tabs></Panel>
    </> : <>
      {groupRuntime ?? <Panel title="Группы находок" extra={<span className="small muted">{data?.groupsAvailable === false ? 'Данные недоступны' : data ? `Загружено ${data.groups.length}` : 'Нет данных'}</span>}>
        {data?.groupsAvailable === false ? <div className="panel-body stack"><span className="badge">Функция не подключена</span><p className="muted small">Группировка F2 пока не подключена. Находки ниже получены сервером; группы на frontend не создаются.</p></div>
          : data?.groups.length ? <div className="group-grid panel-body">{data.groups.map(group => <a key={group.id} className="group-card"
          href={groupHref(project.id, group.id)} onClick={event => { if (onSelectGroup) { event.preventDefault(); select(group.id); } }}>
          <div className="observer-row between"><span className="mono">{group.id}</span>{group.conflict && <span className="badge warn">Конфликт</span>}</div>
          <h3>{group.title}</h3><p className="small muted">Загруженный состав: {data.findings.filter(item => group.findingIds.includes(item.id)).length} находок</p>
          <span className="source-link">Открыть состав группы →</span></a>)}</div>
          : <MissingData loading={current.status === 'loading'} empty={!!data || current.status === 'empty'} />}
      </Panel>}
      {!detailMode && <Panel title="Все находки" className="observer-space" extra={<span className="small muted">Содержательные выводы из отзывов</span>}>
        {data?.findings.length ? data.findings.map(finding => <FindingCard key={finding.id} finding={finding} data={data} projectId={project.id} />)
          : <MissingData loading={current.status === 'loading'} empty={!!data || current.status === 'empty'} />}
      </Panel>}
    </>}
    {controls}
  </div>;
}
