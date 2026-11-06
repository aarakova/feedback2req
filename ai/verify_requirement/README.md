# verify_requirement 1.0

Автономная третья продуктовая роль — Requirements Verification Agent.
Операция проверяет точную `RevisionView`, возвращает четыре `CheckAssessment`
и новые кандидаты замечаний. Она не сохраняет результат, не исправляет
редакцию и не принимает человеческого решения.

Основания: [AI_CONTRACTS §6–9](../../docs/AI_CONTRACTS.md), FR-018–027,
[AI_VALIDATION](../../docs/AI_VALIDATION.md). Схемы 1.0 не менялись.
Проверка смысла задана [версионированным prompt](prompt.py); программный
приём устанавливает структуру, ссылки и согласованность деклараций.

## Запуск

Из корня этого worktree, Python 3.12 и [зависимости AI](../requirements.txt):

```text
python -m pip install -r ai/requirements.txt
python -B -W error -m unittest discover -s ai/tests -v
python -B -m ai.verify_requirement --request evals/ai/verification/supported.request.json --synthetic-response evals/ai/verification/supported.response.json --output verification-result.json
python -B -m ai.verify_requirement --request evals/ai/verification/partial.request.json --synthetic-response evals/ai/verification/partial.response.json --synthetic-plan evals/ai/verification/partial.plan.json --output verification-partial.json
python -B evals/ai/verification/replay.py --output evals/ai/results/verification-run
```

CLI всегда явно синтетический: `model=none; semantic_quality=not_evaluated`.
Он возвращает и проверяет заданный ответ; смысловой inference не выполняется.
Существующий файл/каталог результата не перезаписывается. Файл содержит
канонический ответ, без добавленных полей режима или служебного плана.

Примеры: [завершённый вход](../../evals/ai/verification/supported.request.json),
[ответ](../../evals/ai/verification/supported.response.json),
[частичный вход](../../evals/ai/verification/partial.request.json),
[частичный ответ](../../evals/ai/verification/partial.response.json) и
[синтетический план](../../evals/ai/verification/partial.plan.json).
[Манифест](../../evals/ai/verification/manifest.json) содержит роли и хэши
22 контролей и двух намеренных смысловых контрпримеров. Исходные данные
переиспользованы из S01–S14 и утверждённых примеров, а не заменены новой разметкой.
Воспроизведение: `python -B -m evals.ai.verification.build_cases`.
[Отчёт проверки](../../evals/ai/verification/VALIDATION.md).

## Python-интерфейс

```python
from ai.verify_requirement import ReviewPlan, VerificationError, verify_requirement
from ai.verify_requirement.provider import Ollama, OllamaConfig


def check_saved_revision(request, verify_against_application_state, config):
    return verify_requirement(
        request,
        Ollama(config),
        verify_context=verify_against_application_state,
        required_context=frozenset({"prior_decision", "change_context"}),
    )


# Только подготовка конфигурации: передача данных запрещена.
config = OllamaConfig(
    endpoint="http://127.0.0.1:11434/api/chat",
    model="MODEL_NOT_SELECTED",
    transfer_enabled=False,
    timeout_seconds=60,
    temperature=0,
    think=False,
)
```

`required_context` в этом примере предполагает, что backend независимо
установил наличие прежнего решения и проверку изменения. В обычном вызове
передаётся только действительно необходимый набор из `prior_decision`,
`change_context`, `followup`. Это неизменяемая служебная метаинформация,
не поле AI-запроса. По умолчанию набор пуст, что не является доказательством
отсутствия истории. Обязательный verifier всё равно должен проверить её полноту.

`VerificationProvider.verify(request) -> str | bytes` заменяем. Ollama
использует общий транспорт группировки, её gate/timeout/ограничение размера,
запрет redirect, отключённый ambient proxy и разделение system/user.
Для verification выбираются собственные prompt и самодостаточная схема.
Общий транспорт и существующие операции этой итерацией не изменялись.
Нет зависимости от evaluator в runtime, backend, Z3 или агентного фреймворка.
При упаковке сохранить пакет `ai` и исходные схемы `docs/contracts/ai/v1/`
относительно корня репозитория; ссылки схем разрешаются только локально.

Реальная модель/сервер не выбраны и не запускались. Включать передачу можно
только после отдельного согласования модели, провайдера и условий данных.
Флаг не заменяет такое согласование; loopback URL не доказывает локальность
весов. Поддержка полного диалекта схемы выбранным сервером пока не испытана.

## Программный приём

Вход и ответ изолируются копиями; неизвестные поля, невалидный JSON,
повторные JSON-свойства, NaN/Infinity/overflow отклоняются без ремонта.
Запрос, ответ и транспортная оболочка имеют технический предел 1 MiB каждый,
без усечения. Нет автоматического retry или сохранения сырых материалов в логах.

Проверяются:

- Точная версия/операция, глобальные key/local_id, роли и существование ссылок.
- Замыкание evidence цели на findings, принадлежность доступных фрагментов,
  длины Unicode-выдержек, source/text refs и интервалы. Полная утрата фрагментов
  допустима с историческими `deleted_source`; она не восстанавливается цитатой.
- Полнота `required_keys` относительно переданных current/pending_change/
  new_candidate при project_snapshot, запрет точной цели и повторной редакции,
  обязательный proposal_ref при pending_change и reason при selected.
- При полном отсутствии доступных фрагментов support не может быть
  no_issue_found; историческая связь не подменяет доступное основание.
- Ровно четыре разных оценки. Duplicates рассматривает comparisons, остальные
  оценки — target/findings/fragments/documents. Рассмотренная содержательная
  оценка содержит target.key.
- Coverage относится только к target. `not_processed` требует пустых considered,
  четырёх inconclusive и отсутствия issues, включая регрессию известного дефекта
  evaluator. Неизвестный охват не превращается в полный.
- Пропущенное обязательное сравнение запрещает полный coverage и чистый вывод
  duplicates. Обнаруженные issues допускаются в частичном ответе и сохраняются.
- Категория issue согласуется с check, issues_found требует issue, а issue
  несовместим с no_issue_found соответствующей оценки. Possible_duplicate
  ссылается на рассмотренную редакцию другого requirement_id.
- question_ids существуют; ссылки related разрешаются, scope вопросов и связь
  вопроса с замечанием проверяются. Severity и blocking не преобразуются друг
  в друга автоматически. Insufficient_information или явно неразрешённый новый
  вопрос по target несовместимы с четырьмя чистыми оценками.
- followup ссылается на точный previous_result и его issue_refs. Условно
  обязательные поля проверяются по required_context, известные связи собственной
  исходной редакции — по переданным comparisons. Истина отсутствующих состояний
  и фактов решений проверяется приложением, не угадывается из свободного summary.

`VerificationError.code`: `invalid_request`, `invalid_response`, `timeout`,
`provider_error`; ошибочная служебная конфигурация может дать `configuration_error`.
`rule` — безопасный код причины. Технический отказ не получает вымышленный coverage.
Невалидный ответ целиком отклоняется; его части не отбрасываются для получения PASS.

## Неполный охват

Без плана допустимы completed/insufficient_information, если все предусмотренные
сравнения рассмотрены, либо not_processed. Полностью рассмотренный selected
не является частичным лишь из-за ограничения области. Completed означает
завершённое рассмотрение, а не отсутствие проблем; вывод может быть inconclusive.

`partially_processed` принимается только с `ReviewPlan`, подготовленным
независимым исполнителем, например:

```python
plan = ReviewPlan(
    checked_assessments=frozenset({"support", "contradictions", "ambiguity"}),
    comparison_keys=frozenset({"other1"}),  # other2 предусмотрен, но пропущен
)
```

В плане — завершённые именованные оценки и сравнения. Неисполненная оценка
имеет пустые considered и inconclusive; рассмотренные сравнения должны точно
совпасть с планом. План с пропуском нельзя обойти заявлением completed.
Все требуемые единицы завершены — произвольный partial также отклоняется.

Сервис не формирует пакеты и не создаёт план из ответа модели. Текущий Ollama
делает один вызов; доверенный частичный агрегат должен подготовить внешний
исполнитель. CLI принимает отдельный **синтетический** план только для replay.
Частичное чтение текста одной оценки этот механизм не подтверждает.
Декларации considered/coverage и сам структурно верный план не доказывают
фактическое содержательное чтение моделью.

## История и будущая интеграция

`verify_context(request) -> None` обязателен и должен выбросить исключение при
ошибке. Возврат False не является отказом. No-op verifier допустим только для
явно синтетических фикстур. Он получает копию до AI-вызова; backend проверяет
права, единый проект, точные states, тексты/цитаты, состав scope, прежние
проверки, решения и условную необходимость контекста по доверенной привязке.

Новый пустой issues не закрывает предыдущий блокер. Входная история не меняется,
а ответ вообще не содержит команд изменения is_open/решения/редакции.
Ключи related — временные keys, не ID из previous_checks.ref: старые замечания
связываются через доверенный followup и прикладную историю.

[Требования к будущему backend](../../docs/proposals/verification-backend-handoff.md)
описывают сборку входа, хранение VerificationResult, повторную проверку
актуальности, сохранение прежних блокеров и границу нового HumanDecision.
Это предложение дальнейшей интеграции, не новый HTTP/DB-контракт.
Реальная смысловая поддержка каждого положения, различение условий/конфликтов,
достаточность, возможные дубли и обоснованность блокировки требуют модели
и экспертной оценки. Два контрпримера специально проходят технический приём.
