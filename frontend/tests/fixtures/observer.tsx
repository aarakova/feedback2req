// Test-only entry: never imported by App or the production index.html.
import { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import type { Project } from '../../src/api';
import { AppLayout } from '../../src/Layout';
import { ProjectOverview } from '../../src/ProjectOverview';
import { FindingsScreen } from '../../src/observer/Findings';
import { RequirementsScreen } from '../../src/observer/Requirements';
import { MaterialProcessingStatus, ProcessingScreen } from '../../src/observer/Processing';
import { Panel } from '../../src/observer/ui';
import { groupHref, parseRoute, projectHref, requirementHref, requirementsFilterHref, sectionNames } from '../../src/routes';
import type { ProjectSection, RequirementFilter } from '../../src/routes';
import type { FindingsView, OverviewView, ProcessingView, RequirementView, ViewState } from '../../src/observer/viewModels';
import '../../src/styles.css';
import '../../src/observer/observer.css';
import './fixture.css';

const projectId = '11111111-1111-4111-8111-111111111111';
const sourceId = '22222222-2222-4222-8222-222222222222';
const project: Project = { id: projectId, name: 'Observer · тестовый проект', owner_id: 'test-owner', execution_mode: 'mock',
  permissions: { is_owner: true, is_member: true, can_approve: true } };
const basis = { id: 'E-01', sourceLabel: 'Тестовый отзыв', state: 'available' as const, quote: 'Нужно автосохранение без подтверждения.',
  position: 'Тестовый фрагмент', source: { kind: 'sources' as const, id: sourceId } };
const issue = { id: 'I-01', title: 'Противоположные ожидания', text: 'Требуется решение человека по двум позициям.', kind: 'conflict' as const,
  severity: 'Высокая', blocking: true, open: true, positions: [{ label: 'Автоматически', text: 'Сохранять сразу.' }, { label: 'Вручную', text: 'Только после моего подтверждения.' }] };
const first: RequirementView = {
  id: 'REQ-01', title: 'Сохранение изменений', decision: 'Draft', evidenceState: 'available', verificationState: 'current', openBlockingIssues: true, openIssues: 2,
  revision: 'r1', wording: 'Система должна сохранять изменения с учётом выбранного пользователем режима.',
  rationale: 'Формулировка опирается на две позиции из тестовых отзывов.', originLabel: 'Синтетический тестовый кандидат',
  evidence: [basis], context: [{ id: 'D-01', sourceLabel: 'Описание сервиса заявок', state: 'available', quote: 'Тестовое описание текущего продукта.',
    source: { kind: 'documents', id: '44444444-4444-4444-8444-444444444444' } }], coverage: 'Выбранные тестовые основания, не весь проект.',
  issues: [issue, { id: 'Q-01', title: 'Какой режим использовать по умолчанию?', text: 'Вопрос открыт.', kind: 'question', severity: 'Средняя', blocking: true, open: true }],
  history: [{ id: 'H-01', title: 'Создана тестовая редакция r1', author: 'Тестовый пользователь', time: '2026-01-01', text: 'Исходная формулировка сохранена в тестовой модели.' }],
};
const approved: RequirementView = { ...first, id: 'REQ-02', title: 'Подтверждение завершения', decision: 'Approved', evidenceState: 'partial',
  revision: 'r2', wording: 'Историческая утверждённая формулировка.', openBlockingIssues: false, openIssues: 0, issues: [],
  evidence: [basis, { id: 'E-deleted', sourceLabel: 'Удалённый тестовый отзыв', state: 'deleted', quote: 'НЕ_ПОКАЗЫВАТЬ_УДАЛЁННУЮ_ЦИТАТУ' }],
  proposal: { ...first, revision: 'r3', wording: 'Отдельная предлагаемая формулировка.', issues: [], verificationState: 'stale', evidenceState: 'available' },
};
const rejected: RequirementView = { ...first, id: 'REQ-03', title: 'Уведомление о результате', decision: 'Rejected', issues: [], openBlockingIssues: false };
const lost: RequirementView = { ...approved, id: 'REQ-04', title: 'Утверждённое требование с утраченным основанием', evidenceState: 'lost', evidence: approved.evidence.slice(1), proposal: undefined };
const items = [first, approved, rejected, lost];
const findings: FindingsView = {
  groups: [{ id: 'G-01', title: 'Сохранение и подтверждение', findingIds: ['F-01', 'F-02'], requirementIds: ['REQ-01', 'REQ-02'], conflict: true,
    summary: 'Синтетическая группа с двумя несовместимыми ожиданиями.' }],
  findings: [
    { id: 'F-01', text: 'Нужно автоматическое сохранение.', types: ['Потребность'], originLabel: 'Прямые слова', evidence: [basis], conflictsWith: ['F-02'], requirementIds: ['REQ-01'] },
    { id: 'F-02', text: 'Нужно ручное подтверждение.', types: ['Пожелание'], originLabel: 'Интерпретация AI', humanEdited: true,
      evidence: [{ ...basis, id: 'E-02', quote: 'Не сохраняйте без моего подтверждения.' }], conflictsWith: ['F-01'], requirementIds: ['REQ-02'] },
], requirements: items, requirementIssues: [{ requirementId: first.id, requirementTitle: first.title, issue }],
};
const overview: OverviewView = { aggregatesAuthoritative: true, metrics: { requirements: 4, approved: 2, blockers: 1, lostEvidence: 2 }, decisions: { draft: 1, approved: 2, rejected: 1 },
  groupScaleMaximum: 2, groups: [{ id: 'G-01', title: 'Сохранение и подтверждение', findings: 2, requirements: 2, openIssues: 2 }], attention: [first, lost],
  approvedEvidence: { available: 0, partial: 1, lost: 1 }, coverage: 'Только синтетические тестовые данные; не результаты приложения.' };
const processing: ProcessingView = { stages: [
  { key: 'preparation', status: 'completed', summary: 'Тестовая подготовка завершена.' },
  { key: 'analysis', status: 'running', summary: 'Тестовое состояние выполнения.' },
  { key: 'generation', status: 'partial', summary: 'Часть тестовых кандидатов готова.', errors: ['Ошибка независимой части.'] },
  { key: 'verification', status: 'waiting', summary: 'Тестовое ожидание проверки.' },
], coverage: 'Синтетический неполный запуск.' };

function Fixture() {
  const query = new URLSearchParams(location.search);
  const initial = parseRoute(location.hash);
  const initialProject = initial.kind === 'project' && initial.id === projectId ? initial : undefined;
  const [section, setSection] = useState<ProjectSection>(initialProject?.section ?? (query.get('section') ?? 'requirements') as ProjectSection);
  const [mode, setMode] = useState(query.get('state') ?? 'ready');
  const [selected, setSelected] = useState<string | undefined>(initialProject?.requirementId); const [group, setGroup] = useState<string | undefined>(initialProject?.groupId);
  const [filter, setFilter] = useState<RequirementFilter>(initialProject?.requirementFilter ?? 'all');
  useEffect(() => {
    const changed = () => {
      const route = parseRoute(location.hash);
      if (route.kind !== 'project' || route.id !== projectId) return;
      setSection(route.section); setSelected(route.requirementId); setGroup(route.groupId); setFilter(route.requirementFilter ?? 'all');
    };
    window.addEventListener('hashchange', changed);
    return () => window.removeEventListener('hashchange', changed);
  }, []);
  const wrongScope = query.get('scope') === 'wrong';
  const actor = query.get('actor');
  const permissions = actor === 'member' ? { is_owner: false, is_member: true, can_approve: false }
    : actor === 'approver' ? { is_owner: false, is_member: true, can_approve: true } : project.permissions;
  const shownProject = { ...project, permissions, ...(wrongScope ? { id: '33333333-3333-4333-8333-333333333333', name: 'Другой тестовый проект' } : {}) };
  function state<T>(data: T): ViewState<T> {
    if (mode === 'loading') return { projectId, status: 'loading' };
    if (mode === 'error') return { projectId, status: 'error', message: 'Тестовая ошибка загрузки.' };
    if (mode === 'empty') return { projectId, status: 'empty' };
    if (mode === 'unavailable') return { projectId, status: 'unavailable', message: 'Тестовые данные недоступны.' };
    if (mode === 'partial' || mode === 'partial_empty' || mode === 'relative_scale') return { projectId, status: 'partial', data, message: 'Загружена только часть тестовых результатов.' };
    return { projectId, status: 'ready', data };
  }
  return <><div className="fixture-banner" role="note">Изолированный визуальный стенд · вымышленные данные · серверные операции не выполняются.
    <label>Состояние стенда<select value={mode} onChange={event => setMode(event.target.value)}>
      {['ready', 'loading', 'error', 'empty', 'unavailable', 'partial', 'technical', 'failure', 'zero', 'unknown_counts', 'partial_empty', 'long_names', 'invalid_counts', 'mixed_loss', 'relative_scale'].map(value =>
        <option key={value} value={value}>{({ unknown_counts: 'Нет чисел', partial_empty: 'Часть пуста', long_names: 'Длинные', invalid_counts: 'Неверные', mixed_loss: 'Утрата', relative_scale: 'Масштаб' } as Record<string, string>)[value] ?? value}</option>)}
    </select></label>
    <label>Раздел стенда<select value={section} onChange={event => { setSection(event.target.value as ProjectSection); setSelected(undefined); setGroup(undefined); setFilter('all'); location.hash = projectHref(projectId, event.target.value as ProjectSection); }}>
      {(['overview', 'findings', 'requirements', 'processing'] as const).map(value => <option key={value} value={value}>{sectionNames[value]}</option>)}
    </select></label></div>
    <div onClickCapture={event => {
      const anchor = (event.target as Element).closest('a');
      const href = anchor?.getAttribute('href');
      if (!href?.startsWith(`#/projects/${projectId}`)) return;
      const route = parseRoute(href);
      if (route.kind === 'project' && ['overview', 'findings', 'requirements', 'processing'].includes(route.section)) {
        event.preventDefault(); setSection(route.section); setSelected(route.requirementId); setGroup(route.groupId); setFilter(route.requirementFilter ?? 'all'); location.hash = href;
      }
    }}><AppLayout user={{ id: 'fixture-user', login: 'Тестовый пользователь' }} project={shownProject} section={section} onLogout={() => {}} onRefresh={() => {}}>
      {section === 'overview' ? <ProjectOverview project={shownProject} state={state(mode === 'zero' ? { ...overview,
        metrics: { requirements: 0, approved: 0, blockers: 0, lostEvidence: 0 }, decisions: { draft: 0, approved: 0, rejected: 0 },
        groups: [], attention: [], approvedEvidence: { available: 0, partial: 0, lost: 0 } }
          : mode === 'partial_empty' ? { ...overview, aggregatesAuthoritative: false, groups: [], attention: [] }
          : mode === 'unknown_counts' ? { ...overview, groupScaleMaximum: null, groups: [{ ...overview.groups[0], findings: null, requirements: null, openIssues: null }], attention: [{ ...first, openIssues: null, openBlockingIssues: null, verificationState: 'unavailable' }] }
          : mode === 'long_names' ? { ...overview, groups: [{ ...overview.groups[0], title: 'ОченьДлинноеНазваниеБезПробелов'.repeat(9) + ' 🧭 漢字' }], attention: [{ ...first, title: 'Сохранение\nизменений🧭漢字'.repeat(16) }] }
          : mode === 'invalid_counts' ? { ...overview, metrics: { requirements: NaN, approved: -1, blockers: Infinity, lostEvidence: 1.5 }, decisions: { draft: -1, approved: 2, rejected: 1 } }
          : mode === 'relative_scale' ? { ...overview, aggregatesAuthoritative: false, groupScaleMaximum: 4 }
          : mode === 'partial' ? { ...overview, aggregatesAuthoritative: false } : overview)} />
        : section === 'findings' ? <FindingsScreen project={shownProject} state={state(mode === 'partial'
          ? { ...findings, findings: findings.findings.slice(0, 1) } : findings)} selectedGroupId={group} onSelectGroup={id => { setGroup(id); location.hash = id ? groupHref(projectId, id) : projectHref(projectId, 'findings'); }} />
        : section === 'requirements' ? <RequirementsScreen project={shownProject} state={state({ items: mode === 'zero' ? [] : mode === 'mixed_loss' ? items.map(item => item.id === first.id ? { ...item, evidenceState: 'lost' } : item) : items })} selectedId={selected} filter={filter}
          onFilterChange={value => { setFilter(value); setSelected(undefined); location.hash = requirementsFilterHref(projectId, value); }}
          onSelect={id => { setSelected(id); location.hash = `${requirementHref(projectId, id)}?filter=${filter}`; }} />
        : <><ProcessingScreen projectId={shownProject.id} state={state(mode === 'technical'
          ? { stages: [], technicalInspection: { status: 'completed', summary: 'Технический inspect_text завершён.' } } as ProcessingView
          : mode === 'failure' ? { ...processing, stages: processing.stages.map(stage => stage.key === 'generation' ? { ...stage, status: 'error' as const } : stage) } : processing)} />
          {!wrongScope && <Panel title="Состояние материала · тестовый виджет" className="observer-space"><div className="panel-body">
            <MaterialProcessingStatus value={{ status: 'partial', errors: ['Тестовая ошибка материала.'], unreliableIntervals: ['00:10–00:14 · ненадёжное распознавание'] }} />
          </div></Panel>}</>}
    </AppLayout></div>
  </>;
}
createRoot(document.getElementById('root')!).render(<Fixture />);
