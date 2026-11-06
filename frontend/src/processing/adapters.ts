import type { EvidenceView, FindingView, FindingsView, ExtractionOutcomeView } from '../observer/viewModels';
import type { AnnotationsDTO, CoverageDTO, FindingDTO, FragmentDTO, RunState } from './dto';

export const operationName = (operation: string) => operation === 'inspect_text' ? 'Техническая проверка текста' : 'Извлечение находок';
export const stateName = (state: RunState): string => ({ queued: 'В очереди', running: 'Выполняется', completed: 'Завершено',
  failed: 'Ошибка', cancelled: 'Отменено', partial: 'Частично завершено' })[state] ?? 'Состояние неизвестно';
export const stateTone = (state: RunState) => state === 'failed' || state === 'cancelled' ? 'bad' : state === 'partial' ? 'warn' : state === 'completed' ? 'good' : '';
export const reasonMessage = (reason: string | null) => ({
  provider_not_configured: 'AI-провайдер не настроен или передача ему не разрешена. Извлечение не выполнено.',
  provider_error: 'Ошибка обращения к AI-провайдеру. Успешный результат не подтверждён.',
  invalid_response: 'Ответ провайдера отклонён проверкой формата или оснований.',
  execution_error: 'Задание завершилось ошибкой выполнения.', lease_expired: 'Срок владения попыткой истёк; успешное завершение не подтверждено.',
  deadline_exceeded: 'Превышено допустимое время попытки.', input_changed: 'Состояние материала изменилось. Прочитайте его заново и создайте новый явный запуск.',
  access_revoked: 'Доступ инициатора отозван; задание отменено.',
  retry_not_allowed: 'Повтор для этой попытки сейчас недопустим. Обновите задание.',
  retry_already_requested: 'Для попытки уже запрошен повтор. Обновите историю запусков.',
  idempotency_conflict: 'Ключ уже связан с другой командой. Новое задание автоматически не создаётся.',
  invalid_input: 'Материал или его состояние не подходит для выбранной операции.',
} as Record<string, string>)[reason ?? ''] ?? 'Причина не предоставлена или не распознана. Обновите состояние задания.';
export const aiLabel = (value: boolean | null) => value === true
  ? 'Получен ответ реального AI-адаптера; успешность результата оценивается отдельно.'
  : value === false ? 'Реальный AI-вызов не выполнялся.' : 'Факт выполнения реального AI-вызова не подтверждён.';
export const dateLabel = (value: string | null) => value && Number.isFinite(Date.parse(value))
  ? new Intl.DateTimeFormat('ru-RU', { dateStyle: 'short', timeStyle: 'medium' }).format(new Date(value)) : '—';
export function coverageLines(coverage: CoverageDTO[] | null): string[] {
  if (!coverage) return ['Сведения об охвате не предоставлены.'];
  return coverage.map(item => `${item.input_key}: ${item.disposition === 'completed' ? 'рассмотрен'
    : item.disposition === 'insufficient_information' ? 'недостаточно информации' : 'не обработан'}${item.reason ? ` · ${item.reason}` : ''}`);
}
export function annotationViews(annotations: AnnotationsDTO | null) {
  return {
    questions: annotations?.questions.map(item => ({ id: item.local_id, text: item.text, reason: item.reason, blocking: item.blocking,
      links: item.related.map(link => ({ kind: link.origin, id: link.id })) })) ?? [],
    uncertainties: annotations?.uncertainties.map(item => ({ id: item.local_id, reason: item.reason,
      links: item.related.map(link => ({ kind: link.origin, id: link.id })) })) ?? [],
  };
}
export function fragmentEvidence(fragment: FragmentDTO): EvidenceView {
  return { id: fragment.id, sourceLabel: 'Текстовый отзыв', state: 'available', quote: fragment.quote,
    position: `Символы ${fragment.locator.start}–${fragment.locator.end} (конец не включён)`,
    source: { kind: 'sources', id: fragment.source_ref.id },
    fragment: { id: fragment.id, stateId: fragment.state_id, sourceStateId: fragment.source_ref.state_id },
  };
}
export function outcomeView(value: { synthetic: boolean; ai_performed: boolean | null; provider: string | null; model: string | null; coverage: CoverageDTO[] | null; annotations: AnnotationsDTO | null }): ExtractionOutcomeView {
  return { synthetic: value.synthetic, aiLabel: aiLabel(value.ai_performed), provider: value.provider, model: value.model,
    coverage: coverageLines(value.coverage), ...annotationViews(value.annotations) };
}
export function findingView(item: FindingDTO): FindingView {
  const labels = { problem: 'Проблема', request: 'Пожелание', observation: 'Наблюдение', need: 'Потребность' };
  return { id: item.id, text: item.text, types: item.types.map(type => labels[type]),
    originLabel: item.mode === 'direct' ? 'Прямое высказывание' : 'Интерпретация', evidence: item.evidence.map(fragmentEvidence),
    conflictsWith: [], requirementIds: [], extraction: {
      stateId: item.state_id, attemptId: item.attempt_id, createdAt: dateLabel(item.created_at),
      freshness: item.freshness === 'current' ? 'Текущее состояние источника' : 'Требует актуализации · источник изменился',
      stale: item.freshness !== 'current', ...outcomeView(item),
    } };
}
export function findingsView(items: FindingDTO[]): FindingsView {
  return { groups: [], findings: items.map(findingView), requirements: [], groupsAvailable: false, relationsAvailable: false };
}
export function exactFragmentText(fragment: FragmentDTO, source: { id: string; state_id: string; text: string }): boolean {
  return source.id === fragment.source_ref.id && source.state_id === fragment.source_ref.state_id
    && Array.from(source.text).slice(fragment.locator.start, fragment.locator.end).join('') === fragment.quote;
}
