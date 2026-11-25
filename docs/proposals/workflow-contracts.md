# Пакет решений для полного пользовательского цикла

**PROPOSED. A: редакция 2 от 2026-11-21; B: редакция 2 от 2026-11-25; C: редакция 1 от 2026-11-06.**
**Не является разрешением реализации.**
Основание — текущее интеграционное поручение; DOMAIN/REQUIREMENTS/AI 1.0
сохраняются. Три независимых решения ниже можно принять раздельно.

## A. Публичный запуск группировки

Предлагается отдельно утвердить целиком **редакцию 2 от 2026-11-21**
[grouping-run-api-proposed](../plans/grouping-run-api-proposed.md).
Она актуализирует редакцию 1 из be328080cbeb484b3e2b77866709775627884d98
на интеграционной базе 600065626be5e671223c8a8afd696a14bb4c20e5.
POST `/api/v1/projects/{id}/runs` получает отдельную закрытую ветку
`operation=group_findings`, `finding_refs`, `document_refs`, `previous_group_refs`.
F1 inputs сохраняются. Member + Origin/CSRF + UUID Idempotency-Key;
1–100 findings, до 16 excerpts/16 прежних групп, общий HTTP limit 16 KiB,
canonical request/response ≤1 MiB. Весь selected finding рассматривается целиком.
Один Run/Unit finding_set, queued Attempt=null; тот же ключ/тело возвращает
прежний Run без повторного inference. Исторические refs не заменяются текущими.
Ошибки, bounds, fingerprints и поведение unknown COMMIT — в указанной ревизии.
Нет публичного grouping retry/cancel или TTL. Без настроенного провайдера
команда принимается, затем failed/provider_not_configured. Synthetic — только тест.

После согласования: discriminated HTTP DTO → существующий enqueue → worker;
frontend exact selection/context/start/same-key recovery/polling; контрактные
PG/API/CSRF/isolation/unknown COMMIT тесты. Новая миграция не нужна.
Выбор реальной модели/разрешение передачи — отдельное решение.

Редакция 2 точно определяет snapshot 202/COMMIT, transaction-aware подключение
существующего enqueue через Actor/Tx без вложенной auth-транзакции, строгие типы
refs/locator и безопасный replay под тем же initiator. Это подготовленный
контракт, не HTTP-реализация. [Frontend handoff и сценарии](grouping-launch-frontend.md),
[проверяемые примеры](grouping-launch-examples.json). A не утверждает B/C;
редакция и статус каждого следующего пакета указаны отдельно.

## B. Требования, редакции, проверки и решение человека

**PROPOSED, редакция B.2 от 2026-11-25.** Подготовка разрешена текущим
поручением пользователя; новые таблицы, API и runtime ещё не утверждены.
Окончательный конкретный вариант:
[модель и транзакции B.2](requirements-server-slice.md),
[HTTP DTO и handoff frontend](requirements-frontend-handoff.md),
[синтетические lifecycle traces](requirements-lifecycle-examples.json).

Четыре независимо проверяемых результата после утверждения:
B1 — сохранение новых кандидатов и exact evidence;
B2 — immutable revisions/read/history и human saves неутверждённого;
B3 — saved checks/issues/questions и открытая история;
B4 — Approver decisions/resolutions и отдельные изменения Approved.
Планируемые m04a–m04d следуют после M03, не переписывают F1/F2.
Каждый этап имеет собственный PG/API acceptance run и передачу frontend.

B.2 уточняет прежний эскиз M04: composite FK/constraint triggers,
типизированные input/related bindings, human idempotency receipts, manifest/
material/review hashes, точную цель decision, потерю evidence как отдельную
проекцию и requirement-scoped resolutions. Пустая новая проверка не закрывает
старый blocker; новая revision не наследует чужой Approved. Новая proposal
не меняет действующую approved base до отдельного решения человека.

Используются существующие автономные generate_requirements/verify_requirement
1.0, без изменения схем, включения модели или автоматического решения.
Точная достаточность не выводится из FK/coverage/no_issue_found.
B1–B4 можно утвердить целиком либо явно перечисленным подмножеством.
A.2 и C независимы и этим предложением не утверждаются.

## C. Доверенный обмен и формальная проверка

Предлагается согласовать [обмен F2](qwen-z3-f2-exchange.md) ревизии 0.1
как направление следующего среза, **не как готовый HTTP/SQL контракт**.
GroupDetail не восстанавливает canonical snapshot/local mapping. Нужен exporter
с exact attempt, полным принятым canonical request/response, mapping, разрешёнными
states и provenance. До его проекта и решения production Z3 не подключается.

Прикладной сценарий: выбор двух exact findings/позиций → evidence → предложенные
object/parameter/C/A и пропуски → отдельная доверенная проверка соответствия
источникам/сопоставимости/полноты Ω → Z3. AI не подтверждает собственный результат.
Показываются D/K/S/U только после gate; timeout/unknown/resource_limit/error
отдельно. Вывод относится только к модели и подтверждённым предпосылкам.
Хранение формализации/review/result требует следующего конкретного SQL/DTO
проекта; имеющееся [предложение хранения](formal-expectations-results.md)
остаётся PROPOSED. Автономные synthetic replay доступны независимо.

## Граница разрешения

Согласование A не утверждает B/C или реальную модель. Для B нужно отдельно
утвердить предложенные таблицы/DTO/права/жизненный цикл этой ревизии; никакие
из них пока не действуют в backend. C требует конкретного exporter/
доверенного review/storage контракта. Нынешняя интеграционная ветка не создаёт
новых product таблиц/POST за пределами уже утверждённого F1/F2.
