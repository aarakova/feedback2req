import { useEffect, useId, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { ApiClient, errorMessage } from '../api';
import type { Material, User } from '../api';
import { Panel } from '../observer/ui';
import { ProcessingScreen } from '../observer/Processing';
import { ErrorNotice, Loading } from '../ui';
import { findingsAttemptHref, findingHref, materialStateHref, runHref } from '../routes';
import { dateLabel, operationName, outcomeView, reasonMessage, stateName, stateTone } from './adapters';
import { INPUT_LIMIT } from './dto';
import type { InputRef, Operation, OverviewDTO, RunDTO, UnitDTO } from './dto';
import { useCommand } from './commands';
import { usePages, useRead, checkProject } from './reads';
import { useRun } from './polling';
import { ResultDetails } from './ResultDetails';
import { GroupingRunUnit } from '../grouping/ProjectGroups';

const sameInput = (a: InputRef, b: InputRef) => a.kind === b.kind && a.id === b.id && a.state_id === b.state_id;
const inputKey = (input: InputRef) => `${input.kind}/${input.id}/${input.state_id}`;
interface MaterialPage { items: Material[]; next: string | null; loading: boolean; error: string; more: () => void; reload: () => void }

function MaterialChoices({ title, kind, page, selected, operation, locked, toggle }: {
  title: string; kind: InputRef['kind']; page: MaterialPage; selected: InputRef[]; operation: Operation; locked: boolean; toggle: (input: InputRef) => void;
}) {
  return <fieldset className="processing-choices"><legend>{title}</legend>
    {kind === 'document' && <p className="small muted">Документы допустимы только для inspect_text, не для извлечения находок.</p>}
    {page.items.map(item => {
      const input: InputRef = { kind, id: item.id, state_id: item.state_id };
      const checked = selected.some(ref => sameInput(ref, input));
      return <label key={inputKey(input)} className="processing-choice"><input type="checkbox" checked={checked}
        disabled={locked || !checked && (operation === 'extract_feedback' && kind === 'document' || selected.length >= INPUT_LIMIT)}
        onChange={() => toggle(input)} /><span><strong>{'title' in item ? item.title : 'Текстовый отзыв'}</strong>
        <span className="input-preview">{item.text}</span><span className="mono small">ID: {item.id}<br />Состояние: {item.state_id}</span></span></label>;
    })}
    {page.loading && <Loading>Загружаем сохранённые материалы…</Loading>}
    {page.error && <><ErrorNotice message={page.error} /><button type="button" className="secondary" onClick={page.reload}>Повторить загрузку материалов</button></>}
    {!page.loading && !page.error && !page.items.length && <p className="small muted">В этой коллекции пока нет материалов.</p>}
    {page.next && <button type="button" className="secondary" disabled={page.loading} onClick={page.more}>Показать ещё материалы</button>}
  </fieldset>;
}

function RunDetails({ projectId, run, locked, retry, successor }: {
  projectId: string; run: RunDTO; locked: boolean; retry: (unit: UnitDTO) => void; successor: (id: string) => string | undefined;
}) {
  const technical = run.operation === 'inspect_text';
  return <div className="panel-body stack">
    <div className="observer-row between"><h3>{operationName(run.operation)}</h3><span className={`badge ${stateTone(run.state)}`}>{stateName(run.state)}</span></div>
    <p className="mono small">Run: {run.id}</p><p className="small muted">Создано: <time dateTime={run.created_at}>{dateLabel(run.created_at)}</time> · {run.operation}</p>
    <p className="notice">{technical ? 'inspect_text проверяет размер текста без AI и не создаёт находки.' : 'Завершение задания означает выполнение и приём результата, не полноту анализа всего проекта и не утверждение человеком.'}</p>
    {run.units.map(unit => unit.input.kind === 'finding_set' ? <GroupingRunUnit key={unit.id} projectId={projectId} unit={unit} /> : <section className="processing-unit" key={unit.id} aria-label={`Материал задания ${unit.id}`}>
      <div className="observer-row between"><strong>{unit.input.kind === 'source' ? 'Текстовый отзыв' : 'Документ продукта'}</strong>
        <span className={`badge ${stateTone(unit.state)}`}>{stateName(unit.state)}</span></div>
      <a className="source-link mono" href={materialStateHref(projectId, unit.input.kind === 'source' ? 'sources' : 'documents', unit.input.id, unit.input.state_id)}>{unit.input.id} · открыть материал ↗</a>
      <p className="mono small muted">Состояние: {unit.input.state_id}<br />Unit: {unit.id}</p>
      {unit.retry_of_attempt_id && <p className="small muted mono">Повтор попытки: {unit.retry_of_attempt_id}</p>}
      {unit.attempt ? <>
        <dl className="processing-facts"><div><dt>Попытка</dt><dd className="mono">{unit.attempt.id}</dd></div>
          <div><dt>Начало</dt><dd><time dateTime={unit.attempt.started_at}>{dateLabel(unit.attempt.started_at)}</time></dd></div><div><dt>Окончание</dt><dd><time dateTime={unit.attempt.finished_at ?? undefined}>{dateLabel(unit.attempt.finished_at)}</time></dd></div></dl>
        {unit.attempt.reason_code && <p className="notice bad">{reasonMessage(unit.attempt.reason_code)} <span className="mono">({unit.attempt.reason_code})</span></p>}
        {technical ? unit.attempt.technical_result && <div className="notice good">Технический результат: символов {unit.attempt.technical_result.character_count}, UTF-8 байт {unit.attempt.technical_result.utf8_byte_count}. AI не выполнялся.</div>
          : <ResultDetails value={outcomeView(unit.attempt)} published={unit.state === 'completed' && unit.attempt.coverage !== null} />}
        {!technical && unit.attempt.finding_ids.length > 0 && <div className="related-links"><a className="source-link" href={findingsAttemptHref(projectId, unit.attempt.id)}>Находки этой попытки →</a>
          {unit.attempt.finding_ids.map(id => <a className="source-link mono" key={id} href={findingHref(projectId, id)}>{id} ↗</a>)}</div>}
        {!technical && unit.state === 'completed' && unit.attempt.finding_ids.length === 0 && <p className="small muted">В этой попытке находки не опубликованы. Сведения об охвате показаны отдельно.</p>}
        {unit.state === 'failed' && unit.attempt.state === 'failed' && (successor(unit.attempt.id)
          ? <a className="source-link" href={runHref(projectId, successor(unit.attempt.id)!)}>Открыть повтор из загруженной истории →</a>
          : <div className="stack"><button className="secondary retry-unit" disabled={locked} onClick={() => retry(unit)}>Повторить неудачную операцию</button>
            <p className="small muted">Текущее состояние входа и допустимость повтора проверяются заново. Будет создано отдельное задание с точной ссылкой на эту попытку.</p></div>)}
      </> : <p className="small muted">Попытка ещё не назначена. Материал ожидает обработки.</p>}
    </section>)}
  </div>;
}

export function ProjectProcessing({ api, user, projectId, selectedRunId, prefill, onRecheck }: {
  api: ApiClient; user: User; projectId: string; selectedRunId?: string; prefill?: InputRef; onRecheck: () => void;
}) {
  const root = `/projects/${projectId}`;
  const operationId = useId();
  const sources = usePages<Material>(api, `${root}/sources`, onRecheck);
  const documents = usePages<Material>(api, `${root}/documents`, onRecheck);
  const history = usePages<RunDTO>(api, `${root}/runs`, onRecheck);
  const overview = useRead<OverviewDTO>(api, `${root}/overview`, onRecheck);
  const pinned = useRead<Material>(api, prefill ? `${root}/${prefill.kind === 'source' ? 'sources' : 'documents'}/${prefill.id}` : undefined, onRecheck);
  const command = useCommand(api, user.id, projectId, onRecheck);
  const [operation, setOperation] = useState<Operation>(command.command?.kind === 'start' ? command.command.body.operation : prefill?.kind === 'document' ? 'inspect_text' : 'extract_feedback');
  const [selected, setSelected] = useState<InputRef[]>(command.command?.kind === 'start' ? command.command.body.inputs : prefill ? [prefill] : []);
  const [notice, setNotice] = useState(''); const [preflightError, setPreflightError] = useState('');
  const [preparing, setPreparing] = useState(false);
  const preparingRequest = useRef<AbortController | null>(null);
  useEffect(() => () => preparingRequest.current?.abort(), []);
  const latest = overview.data?.project_id === projectId ? overview.data.processing.latest_run_id : null;
  const active = useRun(api, projectId, selectedRunId ?? latest ?? undefined, onRecheck);
  const locked = command.busy || !!command.command || preparing;
  const invalidDocuments = operation === 'extract_feedback' && selected.some(input => input.kind === 'document');
  const stalePrefill = !!prefill && !!pinned.data && pinned.data.state_id !== prefill.state_id && selected.some(input => sameInput(input, prefill));
  const pinnedPage: MaterialPage | null = pinned.data && prefill && !(prefill.kind === 'source' ? sources : documents).items.some(item => item.id === pinned.data!.id)
    ? { items: [pinned.data], next: null, loading: pinned.loading, error: pinned.error, more: () => {}, reload: pinned.reload } : null;
  function toggle(input: InputRef) {
    setSelected(previous => previous.some(item => sameInput(item, input)) ? previous.filter(item => !sameInput(item, input))
      : [...previous.filter(item => item.kind !== input.kind || item.id !== input.id), input]);
  }
  function accepted(run: RunDTO | undefined) {
    if (!run) return;
    setNotice('Команда принята сервером. 202 подтверждает создание задания, а не завершение анализа.');
    refreshHistory(); window.location.hash = runHref(projectId, run.id);
  }
  function refreshHistory() { history.reload(); overview.reload(); }
  async function start(event: FormEvent) {
    event.preventDefault(); if (locked || !selected.length || selected.length > INPUT_LIMIT || invalidDocuments || stalePrefill) return;
    accepted(await command.start({ operation, inputs: selected.map(input => ({ ...input })) }));
  }
  async function retry(unit: UnitDTO) {
    if (unit.input.kind === 'finding_set' || locked || preparingRequest.current || unit.state !== 'failed' || unit.attempt?.state !== 'failed') return;
    const controller = new AbortController(); preparingRequest.current = controller; setPreparing(true); setPreflightError('');
    try {
      const current = await api.request<Material>(`${root}/${unit.input.kind === 'source' ? 'sources' : 'documents'}/${unit.input.id}`, { signal: controller.signal });
      if (controller.signal.aborted) return;
      if (current.id !== unit.input.id || current.state_id !== unit.input.state_id) { setPreflightError(reasonMessage('input_changed')); return; }
      accepted(await command.retry(unit.id, unit.attempt.id));
    } catch (cause) { if (!controller.signal.aborted) { setPreflightError(errorMessage(cause)); checkProject(cause, onRecheck); } }
    finally { if (preparingRequest.current === controller) preparingRequest.current = null; if (!controller.signal.aborted) setPreparing(false); }
  }
  function refreshInputs() { setSelected([]); setPreflightError(''); sources.reload(); documents.reload(); pinned.reload(); }
  const runtime = <div className="processing-runtime stack">
    <Panel title="Новое задание"><form className="panel-body stack" aria-label="Запуск обработки текста" onSubmit={start}>
      <div className="processing-operation"><label htmlFor={operationId}>Операция</label><select id={operationId} className="observer-select" value={operation} disabled={locked} onChange={event => setOperation(event.target.value as Operation)}>
        <option value="extract_feedback">Извлечение находок · extract_feedback</option><option value="inspect_text">Техническая проверка · inspect_text</option></select></div>
      <p className="notice">{operation === 'extract_feedback' ? 'Извлекаются проблемы, пожелания, наблюдения и потребности из выбранных отзывов. Группировка и требования не создаются.' : 'Проверяются число символов и UTF-8 байт без AI. Документы не используются как отзывы.'}</p>
      {pinnedPage && prefill && <MaterialChoices title="Материал по прямой ссылке" kind={prefill.kind} page={pinnedPage} selected={selected} operation={operation} locked={locked} toggle={toggle} />}
      {pinned.loading && <Loading>Проверяем материал по ссылке…</Loading>}
      {pinned.error && <ErrorNotice message={pinned.error} />}
      {stalePrefill && <p className="notice warn">{reasonMessage('input_changed')}</p>}
      <MaterialChoices title="Текстовые отзывы" kind="source" page={sources} selected={selected} operation={operation} locked={locked} toggle={toggle} />
      <details open={operation === 'inspect_text' || selected.some(input => input.kind === 'document')}><summary>Документы · только техническая проверка</summary><MaterialChoices title="Документы продукта" kind="document" page={documents} selected={selected} operation={operation} locked={locked} toggle={toggle} /></details>
      <p className="small muted">Выбрано {selected.length} из допустимых {INPUT_LIMIT}. Передаются точные ID и state_id; сохранённый текст не обрезается. Добавление материала само по себе не запускает работу.</p>
      {selected.length > 0 && <button type="button" className="secondary" disabled={locked} onClick={() => setSelected([])}>Сбросить выбор</button>}
      {invalidDocuments && <p className="notice warn">Для extract_feedback снимите выбор документов или выберите техническую проверку. Выбор не изменён автоматически.</p>}
      <button className="primary" disabled={locked || !selected.length || selected.length > INPUT_LIMIT || invalidDocuments || stalePrefill || pinned.loading || !!pinned.error && !!prefill && selected.some(input => sameInput(input, prefill))}>Создать задание</button>
    </form></Panel>
    {command.warning && <p className="notice warn">{command.warning}</p>}
    {command.error && <ErrorNotice message={command.error} />}
    {preflightError && <ErrorNotice message={preflightError} />}
    {(command.code === 'input_changed' || preflightError || stalePrefill) && <button className="secondary" disabled={locked} onClick={refreshInputs}>Перечитать материалы и сбросить выбор</button>}
    {command.command && <section className="notice warn stack" aria-label="Неопределённый результат команды">
      <strong>{command.busy ? 'Команда отправляется' : 'Результат команды неизвестен'}</strong>
      <p>Сервер мог создать задание. Новая команда заблокирована. Автоматического POST-повтора нет.</p>
      <p className="mono">Ключ: {command.command.key}</p>
      {command.command.kind === 'start' ? <p className="small mono">{command.command.body.operation} · {command.command.body.inputs.map(input => `${input.id} / ${input.state_id}`).join(' · ')}</p>
        : <p className="small mono">Retry Unit: {command.command.unitId} · ожидаемая попытка {command.command.expectedAttemptId}</p>}
      <button className="secondary" disabled={command.busy} onClick={async () => accepted(await command.replay())}>Повторить ту же команду с прежним ключом</button>
      <button className="secondary" onClick={refreshHistory}>Сверить историю запусков</button>
      <p className="small">История помогает увидеть задания; повтор с тем же ключом возвращает результат исходной команды. Перезагрузка не создаёт новый запуск.</p>
    </section>}
    {notice && <p className="success-notice" role="status">{notice}</p>}
    <Panel title="История запусков" extra={<button className="secondary" disabled={history.loading} onClick={refreshHistory}>Обновить историю</button>}>
      <div className="panel-body stack"><p className="small muted">Показано загруженных заданий: {history.items.length}. Порядок задаёт сервер; последний запуск определён отдельно.</p>
        {latest && <a className="source-link" href={runHref(projectId, latest)}>Последний запуск →</a>}
        {overview.error && <p className="small muted">Последний запуск не удалось определить. История загружается независимо.</p>}
        {history.loading && <Loading>Загружаем историю…</Loading>}{history.error && <ErrorNotice message={history.error} />}
        {!history.loading && !history.error && !history.items.length && <p className="small muted">В истории пока нет запусков.</p>}
        <ul className="run-list">{history.items.map(run => <li key={run.id}><a className="run-row" href={runHref(projectId, run.id)} aria-current={active.run?.id === run.id ? 'true' : undefined}>
          <strong>{operationName(run.operation)}</strong><span className={`badge ${stateTone(active.run?.id === run.id ? active.run.state : run.state)}`}>{stateName(active.run?.id === run.id ? active.run.state : run.state)}</span>
          <span className="mono small">{run.id}</span><time className="small muted" dateTime={run.created_at}>{dateLabel(run.created_at)}</time></a></li>)}</ul>
        {history.next && <button className="secondary" disabled={history.loading} onClick={history.more}>Показать ещё запуски</button>}
      </div></Panel>
    <Panel title="Выбранное задание" extra={<button className="secondary" disabled={active.loading || !(selectedRunId ?? latest)} onClick={active.refresh}>Обновить состояние</button>}>
      {active.loading && <Loading>Проверяем состояние задания…</Loading>}
      {active.error && <div className="panel-body"><ErrorNotice message={active.error} /><p className="small muted">Ниже — последнее подтверждённое состояние, если оно доступно.</p></div>}
      {active.paused && <p className="notice warn">Автообновление приостановлено. Продолжите наблюдение кнопкой «Обновить состояние».</p>}
      {active.run && <RunDetails run={active.run} projectId={projectId} locked={locked}
        retry={unit => { void retry(unit); }} successor={attemptId => history.items.find(run => run.units.some(unit => unit.retry_of_attempt_id === attemptId))?.id} />}
      {!active.run && !active.loading && !active.error && <p className="panel-body muted">Выберите задание в истории или создайте новое.</p>}
      <p className="panel-body small muted">Активное задание проверяется раз в 2 секунды, до 60 успешных проверок. Уход со страницы прекращает наблюдение, но не отменяет серверную работу. Проценты выполнения не вычисляются.</p>
    </Panel>
  </div>;
  return <ProcessingScreen projectId={projectId} runtime={runtime} />;
}
