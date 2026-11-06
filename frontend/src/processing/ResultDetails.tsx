import type { ExtractionOutcomeView } from '../observer/viewModels';

export function ResultDetails({ value, published = true }: { value: ExtractionOutcomeView; published?: boolean }) {
  return <div className="result-details stack">
    {value.synthetic && <p className="notice warn synthetic-result"><strong>{published ? 'Синтетический результат' : 'Синтетический тестовый режим попытки'}</strong> · тестовые сведения, не результат реального AI-вызова.</p>}
    <p className="small muted">{value.aiLabel}</p>
    <dl className="processing-facts"><div><dt>Провайдер</dt><dd>{value.provider ?? 'Не указан'}</dd></div><div><dt>Модель</dt><dd>{value.model ?? 'Не указана'}</dd></div></dl>
    <div><h4>Охват этой попытки</h4><ul>{value.coverage.map((line, index) => <li key={index}>{line}</li>)}</ul>
      <p className="small muted">Это сведения о выбранных входах попытки, не исчерпывающий анализ проекта и не решение человека.</p></div>
    {value.questions.length > 0 && <div><h4>Вопросы извлечения</h4>{value.questions.map(question => <article key={question.id} className="notice observer-space">
      <strong>{question.text}</strong><p>{question.reason}</p>{question.blocking && <p className="small muted">Требует уточнения.</p>}
      <p className="mono small">{question.links.map(link => link.id).join(' · ')}</p></article>)}</div>}
    {value.uncertainties.length > 0 && <div><h4>Неопределённости извлечения</h4>{value.uncertainties.map(item => <article key={item.id} className="notice warn observer-space">
      <p>{item.reason}</p><p className="mono small">{item.links.map(link => link.id).join(' · ')}</p></article>)}</div>}
  </div>;
}
