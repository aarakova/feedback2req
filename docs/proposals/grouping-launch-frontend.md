# Передача frontend: запуск группировки, пакет A.2

**PROPOSED, 2026-11-21. До утверждения команда запуска недоступна.**
Окончательный [контракт A.2](../plans/grouping-run-api-proposed.md) — единственный
источник будущего DTO. Уже работают F2 GET и F3 внутренний enqueue/worker.
В интеграционной базе 6000656 POST поддерживает только inspect_text/extract_feedback.
Новые DTO, handler и frontend-кнопка этой работой не добавлены.

## Запрос и данные для UI

POST `/api/v1/projects/{project_id}/runs`, operation=group_findings,
finding_refs[1..100], document_refs[0..16], previous_group_refs[0..16].
Точные kind/id/state_id обязательны; optional массивы default=[]. Документ может
иметь locator [start,end) в Unicode code points, а не UTF-16 code units JS.
Общий HTTP предел 16 KiB по умолчанию сильнее отдельных пределов количества;
серверный AI request/response ≤1 MiB. Не обрезать контекст ради прохождения лимита.
Чужие/неизвестные refs и state другой группы неотличимы (404).

Сессию/Origin/CSRF передавать существующим способом. Idempotency-Key — UUID,
созданный один раз на одно намерение. Сохранить неизменяемый снимок body, key,
project_id и текущего actor_id до разрешения исхода. Не включать credentials,
model/provider/synthetic, исходные тексты, owner_token или fingerprint в body.
UUID/canonical fingerprint назначает/нормализует сервер; клиент не вычисляет его.

После 202 сохранить run_id, читать прежние GET `/runs/{run_id}`, `/runs`.
queued/running продолжают polling; completed/failed/cancelled завершают его.
Одновременно не держать несколько polling requests одного Run, не применять
ответы старого project/actor/запроса. Частоту/таймер взять из существующего Run UI,
новый обязательный retry budget этим контрактом не вводится.
202 — snapshot транзакции, а не обещание текущего состояния на клиенте.
group_ids=[] при completed — успешный результат; coverage, ungrouped и annotations
читаются из Run, даже когда нет ссылок на GroupDetail. Проценты полноты проекта
из числа групп не выводить. synthetic показывать отдельно от реального AI.

## Восстановление неизвестного исхода

Timeout, disconnect, 5xx, не-JSON proxy error или непригодный 202 не доказывают
rollback. Состояние «исход неизвестен» — только локальное состояние UI, не новый
статус backend. Если run_id известен — GET. Иначе повтор **того же** body/key под
тем же actor/project возвращает прежний Run. Новый ключ не генерировать автоматически.
При 401 восстановить сессию исходного пользователя; при смене actor не делать
replay старого pending body. При 403/404 закрыть недоступное представление и
следовать существующей обработке потери доступа. Ошибка повторного запроса
не доказывает отсутствия задания, созданного ранее при неизвестном исходе.
409 idempotency_conflict требует явного разбора конфликта body/key; не «чинить»
его бесконечной генерацией новых ключей. Изменённый выбор — новое явное намерение.
Закрытие страницы/AbortController отменяет клиентский запрос, не queued job.

## Ошибки

| Стадия | Ответ/код | Поведение frontend |
|---|---|---|
| Auth | 401 unauthenticated | Вход исходным пользователем, без повторной команды новым key |
| Security | 403 origin_rejected/csrf_rejected | Существующее восстановление контекста/CSRF, не скрывать ошибку |
| Scope | 404 not_found | Убрать недоступные данные; не различать чужой/несуществующий объект |
| Selection | 409 input_changed | Загрузить актуальный выбор, новый start только явным действием |
| Command | 409 idempotency_conflict | Сохранить снимок pending команды, не менять key автоматически |
| Body | 413 body_too_large | Уменьшить явный выбор; не резать текст/диапазон скрытно |
| DTO | 422 invalid_request | Показать ошибку ввода/интеграции, не model retry |
| Context | 422 invalid_input | Дубликат/range/лимит/незамкнутая previous_group; исправить выбор |
| Unknown | 500 internal_error, proxy 5xx/network | GET известного run_id или same-key recovery |
| Worker | failed/provider_not_configured | Провайдер не включён; без synthetic fallback |
| Worker | failed/provider_error/invalid_response/execution_error | Показать технический отказ и безопасный reason_code |
| Worker | failed/lease_expired/deadline_exceeded | Показать истечение, без auto retry |
| Worker | cancelled/input_changed/access_revoked | Отмена publication, не старый «успешный» UI |

Envelope `{error:{code,message,details:{},request_id}}`, X-Request-ID/no-store.
Пользователю не показывать raw SQL/transport exception. Нынешний отдельный
POST `/units/{id}/retries` для finding_set остаётся 409 retry_not_allowed.

## Проверяемые сценарии после утверждения

Все строки — **критерии будущего HTTP/PG/browser прогона, сейчас NOT RUN**.
Синтетические данные отдельного project/DB; provider calls считать на адаптере.
Наличие старых unit-тестов F3 не означает, что новый POST уже проверен.

| ID | Условия/действие | Ожидание |
|---|---|---|
| A01 | Member, 2 findings, новый key | 202 queued/attempt=null; одна Unit, session token не в queue |
| A02 | Точный document excerpt и previous_group, members в findings | Worker читает выбранные states/range; refs в GET точны |
| A03 | one/many synthetic result, конфликт | completed; GET groups/positions → Finding → Fragment → Source |
| A04 | Валидный полностью ungrouped ответ | completed/group_ids=[]; coverage/annotations доступны в Run |
| A05 | Повтор body/key до claim и после terminal | Тот же run_id, дополнительного provider call нет |
| A06 | UUID case/order и omitted optional arrays ↔ [] | Тот же fingerprint/Run; дубликат не удаляется молча |
| A07 | Другой body с прежним key | 409 idempotency_conflict, нет второго задания |
| A08 | Два параллельных POST одного key и два worker | Одна Unit/Attempt, ≤1 provider call |
| A09 | Нет сессии / неверный Origin / неверный CSRF | Соответствующий 401/403, enqueue не выполнен |
| A10 | Чужой проект/группа/finding, отсутствующий UUID, state другой группы | Одинаковый 404; нет утечки и новых Run |
| A11 | Старый expected source/document/group state при новом key | 409 input_changed, нет queued Unit |
| A12 | Дубликат finding/previous group; full-doc + full-range alias | 422 invalid_input, rollback команды |
| A13 | null/unknown field/string/boolean/float locator/неверный UUID | 422 invalid_request; старые F1 DTO сохраняются |
| A14 | 101 findings, 17 docs/previous groups при body в HTTP limit | 422 invalid_request (list bounds в DTO), нет enqueue |
| A15 | >HTTP limit / >1 MiB canonical context | 413 body_too_large / 422 invalid_input, без обрезки и model call |
| A16 | Unknown enqueue COMMIT: запись и rollback | Same-key повтор найдёт прежний либо создаст первый Run, не второй |
| A17 | Unknown claim COMMIT: запись и rollback | До подтверждённого claim transport не вызван; persisted running истекает |
| A18 | Unknown final COMMIT: запись и rollback | GET показывает completed либо running→failed; повторной модели нет |
| A19 | Отзыв доступа до claim / во время compute | cancelled/access_revoked; нет публикации, после отзыва GET 404 |
| A20 | Source/doc/previous group изменились после enqueue | cancelled/input_changed; исторические states не подменены |
| A21 | Прерывание worker, lease/deadline истекли | failed с точным reason, после restart нет повторного model call |
| A22 | Нет provider / invalid output / transport exception | Точный failed reason; никакого synthetic fallback |
| A23 | Terminal Run replay после смены входного state | Прежний Run с историческими refs; нового inference нет |
| A24 | Timeout POST, затем logout/login другого actor | Нет автоматического replay под другим initiator |
| A25 | Старый ответ GET после смены project/actor/нового запроса | Не применяется к текущему UI |
| A26 | Настоящий Actor/Tx + enqueue; ошибочный COMMIT | Нет nested-session self-wait; до успешного COMMIT нет 202 |
| A27 | Исчезновение старого blocker в новом AI-ответе | Ссылка не закрывает прежние вопросы и не разрешает конфликты |

## Зависимости и граница передачи

Требуется явное утверждение пакета A редакции 2 целиком. После этого сервер
подключает DTO/transaction-aware делегирование к enqueue и проверяет матрицу
на PostgreSQL. Frontend подключает start/pending/polling к уже имеющемуся чтению
групп отдельной итерацией. Реальная Qwen-модель и пакеты B/C не являются
зависимостями для synthetic приёмки A.2 и этой редакцией не утверждаются.
