import { useState } from 'react';
import type { ReactNode } from 'react';
import { projectHref } from '../routes';
import { MissingData, PageHeading, Panel, ViewNotice } from './ui';
import { inProject, unavailable, viewData } from './viewModels';
import type { MaterialProcessingView, ProcessingStatus, ProcessingView, StageKey, ViewState } from './viewModels';

const stages: readonly { key: StageKey; title: string; description: string }[] = [
  { key: 'preparation', title: 'Подготовка материалов', description: 'Текст и распознавание речи' },
  { key: 'analysis', title: 'Анализ и группировка', description: 'Находки и отдельные позиции' },
  { key: 'generation', title: 'Формирование требований', description: 'Проекты требований и основания' },
  { key: 'verification', title: 'Проверка требований', description: 'Замечания и вопросы' },
];
const statusNames: Record<ProcessingStatus, string> = {
  unavailable: 'Данные недоступны', waiting: 'Ожидание', running: 'Выполняется', partial: 'Частично завершено', error: 'Ошибка', completed: 'Завершено',
};
export function ProcessingBadge({ status }: { status: ProcessingStatus }) {
  return <span className={`badge ${status === 'error' ? 'bad' : status === 'partial' ? 'warn' : status === 'completed' ? 'good' : ''}`}>{statusNames[status]}</span>;
}
export function ProcessingCallout({ projectId }: { projectId?: string }) {
  return <div className="processing-callout"><div><strong>Материалы и запуск обработки — отдельные действия</strong>
    <p>{projectId ? 'Сохранение не запускает анализ. Выберите материалы и операцию на вкладке «Обработка».' : 'Сохранённые тексты уже доступны. Запуск анализа пока не подключён.'}</p></div>
    {projectId ? <a className="primary action-link process-cta" href={projectHref(projectId, 'processing')}>Обработать материалы</a>
      : <button className="primary process-cta" disabled aria-describedby="processing-not-connected">Обработать материалы</button>}
    {!projectId && <span id="processing-not-connected" className="sr-only">Операция запуска обработки недоступна на сервере.</span>}
  </div>;
}
export function MaterialProcessingStatus({ value }: { value?: MaterialProcessingView }) {
  return <div className="material-processing-status"><ProcessingBadge status={value?.status ?? 'unavailable'} />
    {value?.errors?.map((message, index) => <p className="notice bad" key={index} role="alert">{message}</p>)}
    {!!value?.unreliableIntervals?.length && <div className="notice warn"><strong>Ненадёжные участки распознавания</strong>
      <ul>{value.unreliableIntervals.map(interval => <li key={interval}>{interval}</li>)}</ul></div>}
  </div>;
}
export function ProcessingScreen({ projectId, state, runtime }: { projectId: string; state?: ViewState<ProcessingView>; runtime?: ReactNode }) {
  const current = inProject(state ?? unavailable<ProcessingView>(projectId, 'Запуск обработки и состояния семантических этапов пока недоступны.'), projectId);
  const data = viewData(current); const [selected, setSelected] = useState<StageKey>('preparation');
  const active = data?.stages.find(stage => stage.key === selected);
  return <div className="processing-screen"><PageHeading title="Обработка" description="Результаты и действия в каждом этапе."
    >{!runtime && <button className="primary process-cta" disabled title="Серверная операция запуска пока не подключена">Обработать материалы</button>}</PageHeading>
    {runtime ?? <ViewNotice state={current} />}
    <div className={`run-header${runtime ? ' observer-space' : ''}`}><div><p className="eyebrow">{runtime ? 'Дальнейшие этапы' : 'Обработка проекта'}</p><h3>{runtime ? 'Полный конвейер Observer' : data ? 'Состояния переданных этапов' : 'Состояние запуска недоступно'}</h3></div>
      <p className="small muted">{runtime ? 'Извлечение находок подключено выше. Группировка, генерация и проверка требований пока не подключены; общий прогресс не вычисляется.' : data?.coverage ?? 'Прогресс не вычисляется без данных о реальном запуске.'}</p></div>
    <div className="stage-track" role="group" aria-label="Этапы обработки">{stages.map((stage, index) => {
      const value = data?.stages.find(item => item.key === stage.key);
      return <section className={`stage ${value?.status === 'error' ? 'stage-error' : ''}`} key={stage.key} aria-label={stage.title}>
        <span className="step-num">0{index + 1}</span><h3>{stage.title}</h3><p>{stage.description}</p>
        <ProcessingBadge status={value?.status ?? 'unavailable'} />
        <p className="small muted">{value?.summary ?? 'Результаты этапа пока недоступны.'}</p>
        <button className="secondary" disabled={!value} aria-pressed={selected === stage.key} onClick={() => setSelected(stage.key)}>Детали этапа</button>
      </section>;
    })}</div>
    <Panel title={stages.find(stage => stage.key === selected)!.title} className="observer-space">
      <div className="panel-body">{active ? <div className="stack"><ProcessingBadge status={active.status} /><p>{active.summary}</p>
        {active.errors?.map((error, index) => <p className="notice bad" key={index} role="alert">{error}</p>)}
      </div> : <MissingData loading={current.status === 'loading'} empty={current.status === 'empty'} />}
        <a className="source-link" href={projectHref(projectId, selected === 'analysis' ? 'findings' : selected === 'generation' || selected === 'verification' ? 'requirements' : 'materials')}>Открыть связанный раздел →</a>
      </div>
    </Panel>
    {data?.technicalInspection && <Panel title="Техническая проверка текста" className="observer-space"><div className="panel-body stack">
      <ProcessingBadge status={data.technicalInspection.status} /><p>{data.technicalInspection.summary}</p>
      <p className="notice warn">inspect_text — техническая инспекция. Она не означает выполнение семантического AI-анализа, генерации или проверки требований.</p>
    </div></Panel>}
    <p className="notice observer-space">Завершение технического этапа не является утверждением требования человеком.</p>
  </div>;
}
