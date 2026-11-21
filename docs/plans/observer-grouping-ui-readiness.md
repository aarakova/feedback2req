# Observer: готовность пользовательского запуска группировки

2026-11-21. **Frontend-подготовка, не утверждение HTTP/DTO/модели данных.**
Основание — поручение продолжить Observer от согласованной интеграционной версии,
сначала подготовить зависимости запуска, затем подключать утверждённый backend.
Push, merge в main и внешние AI-вызовы запрещены этим поручением.

## База и изоляция

- Проверены refs после `git fetch origin`, зарегистрированные worktree и их status.
  Preview `a866b4e` и прежняя frontend-ветка `ae6dd06` не являются полной версией.
  Main/integration/ai-foundation — `410b936`.
- Использована `origin/integration/full-workflow-ui`:
  **600065626be5e671223c8a8afd696a14bb4c20e5**. Включает F1, F2 read/F3 worker,
  сохранённые группы, конфликты, exact states и готовые browser-проверки.
- Новая ветка **feat/observer-grouping-ui-20261121** создана непосредственно от
  этого SHA. Собственный вложенный worktree находится в `.local/worktrees/` старой
  рабочей области. Команды выполняются в новом checkout; исходный checkout чист.
- Параллельные worktree с изменениями AI-evals, backend public-contract и
  integration-readiness не менялись. Их незакоммиченные файлы не интегрировались.
- Применяются [AGENTS](../../AGENTS.md), [PLANS](../../PLANS.md),
  [DECISIONS](../DECISIONS.md), в частности INT-2026-11-06. Эта запись разрешает
  чтение групп/F3, но явно оставляет публичный старт несогласованным.

## Что уже реализовано и сохраняется

| Область | Реализация базы | Граница |
| --- | --- | --- |
| Материалы/F1 | [Materials](../../frontend/src/Materials.tsx), [ProjectProcessing](../../frontend/src/processing/ProjectProcessing.tsx) | inspect_text/extract_feedback; создание материала не запускает анализ |
| Выводы F1 | [ProjectFindings](../../frontend/src/processing/ProjectFindings.tsx) | пагинация/detail, synthetic/ai_performed, coverage/annotations |
| Группы/конфликты | [ProjectGroups](../../frontend/src/grouping/ProjectGroups.tsx) | три настоящих GET; current и exact state различаются |
| История F3 | GroupingRunUnit в том же компоненте, [Run DTO](../../frontend/src/processing/dto.ts) | finding_set, queued/attempt=null, результат с группами либо ungrouped |
| Неизвестный POST F1 | [commands](../../frontend/src/processing/commands.ts), [pending](../../frontend/src/processing/pending.ts) | сохраняются key/intent по actor/project; текущий StartCommand допускает только F1 |
| Наблюдение | [polling](../../frontend/src/processing/polling.ts), [reads](../../frontend/src/processing/reads.ts) | ограниченные GET, AbortController, защита контекста и поздних ответов |
| Цитаты | [EvidenceCard](../../frontend/src/observer/ui.tsx), exact Fragment/Source routes | ссылки на states, Unicode code points/CRLF, без поиска похожего текста |
| Требования | [Requirements](../../frontend/src/observer/Requirements.tsx) | UI/изолированные fixtures; product storage/verification/human-write не подключены |

Существующий [Start](../../backend/feedback2req/api/processing.py) разрешает только
две F1 operation. Наличие `group_findings` в **ответе** Run не утверждает такую
операцию в POST. Новая форма, payload type, pending-вариант и HTTP-вызов сейчас
не добавлены. Нет новой кнопки с имитацией запуска или успешного сохранения.

## Статус серверного контракта

Действуют [FINDING_GROUPS_API](../FINDING_GROUPS_API.md),
[TEXT_PROCESSING_API](../TEXT_PROCESSING_API.md) и внутренний
[F3 enqueue/worker](../GROUPING_ORCHESTRATION.md).
Публичный запуск в [предложении](grouping-run-api-proposed.md) и пакете A
[workflow-contracts](../proposals/workflow-contracts.md) имеет статус **PROPOSED**.

В параллельной ветке `feat/backend-grouping-public-contract` подготовлен пакет
A редакции 2 от 2026-11-21 и frontend-handoff, коммит `639f1e4`.
Статус остаётся PROPOSED: handler/DTO не реализованы, это не разрешение реализации.
В этом checkout сохранена редакция интеграционной базы; чужие правки не копируются.
После утверждения нужны запись согласования,
точный коммит реализованного backend и результаты его контрактных PG/API-тестов.
Frontend должен брать закрытый DTO из этой принятой версии, а не из этого отчёта.
Подготовленный A.2 можно прочитать из локального коммита:
`git show 639f1e4:docs/plans/grouping-run-api-proposed.md`; сопровождающая матрица —
`git show 639f1e4:docs/proposals/grouping-launch-frontend.md`.
Этот отчёт дополняет её картой существующих компонентов и зависимостей, а не
создаёт конкурирующую редакцию HTTP-контракта.

## Точный перечень серверных данных

Ниже перечислены данные и гарантии, а не новый wire format.

| Сценарий UI | Что необходимо | Что уже есть / что требуется |
| --- | --- | --- |
| Выбрать находки | id/state_id, text/types/mode, freshness, evidence, происхождение | GET findings/detail уже даёт эти поля; страницы items/next_cursor, без total/snapshot |
| Увидеть состав выбора | exact refs всех выбранных находок, включая другие страницы | выбор хранится отдельно от загруженной страницы; отсутствие на первой странице ничего не доказывает |
| Дополнительный контекст | exact states документов/прежних групп, допустимые Unicode locator и ограничения замыкания | чтение уже есть; правила передачи в новую команду требуют принятого пакета A |
| Явный запуск | принятые operation/URL/method, обязательные поля и defaults, лимиты количества/байт, права | в A.2 предложены finding_refs/document_refs/previous_group_refs; в действующем POST их ещё нет |
| Авторизация | действующий actor/project и серверные permissions, Origin/CSRF | существующий ApiClient сохраняется; FR-032 разрешает Member запуск обработки, Approver не даёт администрирование |
| Подтверждение команды | 202 с сохранённым Run.id и снимком состояния | существующий Run DTO пригоден для чтения; 202 не доказывает queued в момент показа или успех AI |
| Идемпотентность | область UUID key, канонизация refs/ranges, replay/conflict, поведение при изменившемся доступе | публичная гарантия для grouping должна быть утверждена и реализована, как и её связь с общей областью F1 key |
| Состояние | Run/Unit state; finding_set inputs; nullable Attempt; даты и reason_code | GET runs/runs/{id} уже поддерживают F3; polling переиспользуется без процентов |
| Принятый результат | grouping_result, group_ids, ungrouped_findings, input_findings, coverage/annotations | уже есть в Run; null не равен принятому пустому результату, group_ids=[] не является ошибкой |
| Происхождение | synthetic, ai_performed, provider/model, authorship, freshness | уже есть в Run/GroupDetail; статус выполнения, охват и решение человека различаются |
| Состав/конфликты | GroupDetail.members с exact Finding/evidence, considered_findings, context, positions, previous_state_id | три GET групп уже реализованы; M:N membership и позиции не усредняются |
| Точный результат старой Attempt | однозначное разрешение исходных group states или явно обозначенный current-переход | Run отдаёт group_ids без state_id; см. ограничение ниже |
| Ошибки | безопасный envelope/code, отличие отказа до enqueue от неизвестного исхода; input_changed/access_revoked и ошибки provider/lease/deadline | коды чтения/worker есть; таблица ошибок нового публичного POST должна быть принята и покрыта тестами |
| Повтор/отмена | является ли действие retry, новым start или только same-key replay; есть ли cancel/TTL | сейчас finding_set retry →409 retry_not_allowed; retry/cancel UI не добавлять по аналогии с F1 |

В A.2 **предлагаются**, но ещё не утверждены публично, пределы 1–100 findings,
до 16 excerpts/16 previous groups, HTTP 16 KiB и canonical context 1 MiB.
Frontend не переносит внутренние пределы в новый DTO до принятия контракта,
не обрезает выбор/текст и не добавляет контекст автоматически.

У immutable F1 Finding актуальность источника выражена отдельно от её state_id.
Если finding имеет requires_update, нельзя выдумать новый state_id или заменить
её основание текущим текстом. Потребность в новом явном F1-извлечении показывается
отдельно; обновление списка или отказ grouping не запускают его автоматически.

### Текущее состояние группы и сохранённый результат

[GET groups](../../backend/feedback2req/api/groups.py) соединяет только
FindingGroup.current_state_id; attempt_id фильтруется **после этого**.
Следовательно, после human state список `groups?attempt_id` не является архивом
групп старой Attempt, а отсутствие на странице не доказывает отсутствие результата.
Один `group_id` из Run также не является точным state ref.

Рекомендация для минимального первого среза: сохранить существующую явную подпись
«Текущее состояние группы» у Run-перехода; из GroupDetail открывать exact state
и previous_state_id по уже действующим GET. Не подписывать current как «точный
результат этой попытки», не брать его state_id для реконструкции старого результата.
До настоящего human-write API это не препятствует запуску A.2, который не
перезаписывает прежние группы. Если требуется прямой неизменный снимок каждой
группы именно данной Attempt после будущих правок, backend должен определить
гарантированный способ разрешения таких states. Новое поле/endpoint здесь не
проектируется и в frontend не придумывается.

### Восстановление команды

После принятия A переиспользовать поведение F1, сохраняя закрытые варианты команд:

1. До POST запомнить UUID key и неизменный одобренный body по actor/project.
   Только refs/ranges/operation; без текста, cookie, CSRF, provider credentials.
2. Потерянный ответ/5xx/непригодный 202 не означают rollback. Заблокировать новое
   намерение; GET истории не должен автоматически порождать POST.
3. Доступен явный повтор того же body/key под тем же actor/project. Изменение
   выбора — отдельное намерение после разрешения исхода, а не автоматический retry.
4. Не восстанавливать body из Run: Unit.input.documents не содержит locator,
   отсутствие locator и явный full range могут иметь различный fingerprint.
5. Смена actor/project, logout/401 и поздний ответ не должны восстанавливать старое
   представление/намерение в новом контексте. Ошибка same-key запроса сама по себе
   не доказывает отсутствия исходного Run; это отдельно проверить по принятому A.2.
6. Истёкшее наблюдение — локальная пауза, а не новый backend-state. AbortController
   прекращает клиентское чтение; это не отмена server job.

## Рекомендуемый порядок реализации после backend

1. Принятый пакет A + точный backend SHA + реальные HTTP/PG/idempotency тесты.
2. Минимальный UI: выбор находок в «Находках», видимый состав точных states,
   явный запуск и переход на существующий Run route. Сначала без редактора
   дополнительных excerpts/прежних групп; пустой контекст допустим только если
   это подтвердит принятый контракт. Ни новые группы, ни текст результатов локально
   не генерируются. Новый роутер/UI-фреймворк не требуется.
3. Расширить StartCommand/pending только точным принятым вариантом, сохранив F1
   проверки и разграничение body. Не заменять типы на произвольный object/any.
4. Переиспользовать useRun/GroupingRunUnit/ProjectGroups, ошибки и exact-ссылки.
   Пустой принятый результат показывает coverage/questions/ungrouped, не ложный сбой.
5. Реальные browser/API/PG проверки выбора через страницы, повторного клика,
   потерянного POST/COMMIT, same-key replay, смены входа/доступа/actor, поздних
   ответов, failed/provider_not_configured, completed без групп и 320/390 px.
   Synthetic — только явно маркированный собственный стенд. Старые F1/F2 проверки
   и эталоны не ослаблять; неизвестные KPI не превращать в нули.

## Следующие срезы, не реализуемые до соответствующего backend

| Срез | Необходимые серверные данные/операции | Критерий готовности UI |
| --- | --- | --- |
| Сохраняемые требования | identity требования и exact Revision, формулировка/авторство/история, evidence/context, freshness, права, конкурентная запись и предложения к Approved | сохранённый Draft читается после reload; локальная правка не изображает сохранение; старый Approved не подменён proposal |
| Проверки | exact сохранённая Revision, сохранённый verification result, четыре независимые оценки, issues/questions/blocking, comparison scope/coverage/provenance | проверка относится к своей редакции; старые блокеры не исчезают из-за пустого нового ответа; AI не меняет решение человека |
| Решения человека | серверное право Approver, привязка решения к exact Revision/проверке, основания отказа, конкурентные изменения и история | Approved/Rejected подтверждены сервером; Member не утверждает, Approver не получает Owner-полномочий; потеря основания показана отдельно от старого решения |

Логические правила уже описаны в REQUIREMENTS/DOMAIN. Пакеты B/C, физические DTO,
storage и публичные операции остаются отдельными согласованиями. Автономные AI/Z3
модули и тестовые fixtures не являются product save/verify/decision API.

## Проверки этой подготовки

Новый [grouping-read-regressions.spec.ts](../../frontend/tests/grouping-read-regressions.spec.ts):

| Требование | Проверка |
| --- | --- |
| FR-011/FR-021, AC-04/AC-07 | Group exact state → Fragment exact state → Source; quote по code points, полный текст/CRLF/reload; навигация не создаёт Run |
| FR-032, AC-01 | реальное завершение сессии и GET групп удаляют защищённые данные и проектную навигацию |
| FR-022/FR-023, AC-07 | Run-переход явно current; human state не выдан за старый AI-результат; исторический state доступен отдельно |

TypeScript/Vite и production Docker build интеграционного frontend — PASS
(46 модулей). Runtime собран из той же базы под собственным именем.
Новые три browser-регрессии и пять прежних group tests через production Nginx,
настоящие API/PostgreSQL/worker — **8 passed, 0 failed** (48,7 s).
Включены 1440/1280/390/320 px, F3 queued→completed, completed без групп,
503/read retry, outsider 404 и поздний ответ после смены проекта.

Ни один прежний тест или golden snapshot не изменён. Экспорт четырёх снимков
старого group test направлен в собственный ignored scratch через bind mount;
tracked QA-файлы исходной базы не переписываются. Прежние processing.spec.ts и
project-layout.spec.ts: **24 passed, 1 skipped, 0 failed** (3,1 минуты).
Skip — отдельный отрицательный F1 provider-not-configured режим; в этом прогоне
настроен synthetic provider. Проверены фактические start/retry F1, lost POST и
same-key replay, running/terminal/partial, pagination, Unicode/CRLF, project/actor
изоляция, отзыв доступа, ограничение polling, reload, неизвестный маршрут и
desktop/mobile keyboard navigation. Повтор тестового раннера отключён.

Стенд: собственный префикс `f2r-observer-gui-20261121-adf66`, отдельные internal
network, PG volume и browser modules; без host ports. Seed/F3 используют
существующие synthetic helpers и подготовленный ORM human-state только в новой
test DB. Это не human-write API и не доказательство реального inference.
Существующие Docker-ресурсы не перезапускались; новые образы имеют отдельные tags.
Первый запрос разрешения на build завершился timeout проверки, не исполнялся;
разрешённый повтор успешно выполнил сборку. Docker Desktop был выключен и запущен
для тестирования, без смены конфигурации. Внешних AI-вызовов не было.
После прогонов активных queued/running Unit в собственной БД не осталось;
остановлены только шесть собственных активных контейнеров. Сеть и собственные
volumes сохранены, чужие работающие стенды не останавливались.

Полный suite/CI, реальная модель, Firefox/Safari/TLS и независимое ревью этой
подготовки не выполнялись. Просмотр кода не является browser-проверкой.
Публичный grouping start/его lost POST не тестируются как работающая функция:
они ещё не реализованы. Baseline-тесты F1 проверяют существующий механизм recovery.

Воспроизводимые browser-команды из `/tests/frontend` собственного контейнера:

```sh
F2R_E2E_MODE=built F2R_E2E_TUNNEL=frontend:80 npm run test:e2e -- grouping.spec.ts grouping-read-regressions.spec.ts --reporter=line,json
F2R_E2E_MODE=built F2R_E2E_TUNNEL=frontend:80 npm run test:e2e -- processing.spec.ts project-layout.spec.ts --reporter=line,json
```

В этой ветке изменены только этот документ и новый файл browser-регрессий.
Product frontend/backend, модели, контракты, миграции, старые тесты и эталоны
остались из `6000656`. Локальный подготовительный коммит и окончательный Git status
указаны в итоговом сообщении. Push/merge не выполнялись. Переход к реализации
launch UI зависит от утверждения A.2 **и** готового backend-коммита с его
публичными контрактными тестами; наличия предложения или внутреннего enqueue
для этого недостаточно.
