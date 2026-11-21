# Формальный checker/bridge: совместимость интеграционной версии

Поручение пользователя 2026-11-21. Новых product API/storage/архитектурных
согласований нет; push, merge main и внешние AI-вызовы запрещены.
Повторно используются INT-2026-11-06 и прежние автономные formal/bridge согласования.

База после fetch: origin/integration/full-workflow-ui
`600065626be5e671223c8a8afd696a14bb4c20e5`. Собственные worktree
`.local/worktrees/formal-package-c-readiness` и ветка
`feat/formal-package-c-readiness`. Preview a866b4e не полная сборка.
Readiness-кандидат 8d5174a проверяется другим агентом, не объявляется принятой
новой базой. Его дельта ограничена Qwen и здесь не переносится.

- [x] Проверить refs/worktrees/историю и действующий PROPOSED C.
- [x] Добавить автономную механическую сверку явно переданных saved DTO с bridge.
- [x] Проверить реальную цепочку F1 → F2 → exact DTO → bridge в собственной PG.
- [x] Подготовить конкретный C1 PROPOSED: snapshot, independent review, Ω, result.
- [x] Запустить formal/bridge/replay/grouping регрессии, Ruff/contracts.
- [x] Зафиксировать результаты и ограничения; подготовить локальный commit, не push.

Новые endpoint/exporter/ORM/storage/review UI не реализуются. Механическая
сверка не даёт Verification, не проверяет права и смысл и не вызывает Z3.
Production worker/основной цикл не изменяются. Синтетические данные изолированы.

## Полученный результат

- [Механический аудит](../../ai/formal_expectations_bridge/compatibility.py) и
  CLI `python -B -m ai.formal_expectations_bridge audit <bridge.json> --saved <saved.json>`.
  Matched означает совпадение проверенных полей, не доверенный снимок/смысл.
  У всех результатов classification=null, verification_created=false и
  outstanding gates. Не создаются receipt/HumanDecision, HTTP-запросы или Z3-вызовы.
- [Новые unit-тесты](../../ai/formal_expectations_bridge/tests/test_compatibility.py)
  и [PG suite](../../experiments/formal_integration_checks/README.md) с настоящими
  API/PG F1/F2 и явно синтетическими источниками. Данные других стендов не читались.
- [Конкретный C1](../proposals/formal-package-c1.md) — PROPOSED 0.1:
  exact snapshot + независимый field-level review + обоснование Ω + условный
  read-only результат. Полномочия reviewer/exporter/storage не реализованы.

Подтверждена механическая совместимость canonical запроса из prepare F2,
контролируемого принятого ответа и сохранённых Finding/Fragment/GroupDetail DTO.
F1 Finding/Fragment сейчас immutable (state_id=id), GroupState имеет отдельный ID;
положительный тест читает точный group/state. У F2 Run сохранён completed и после
условной тестовой K, и после настоящего ограничения ресурсов Z3. Без verifier
bridge отказывается вычислять класс. После отзыва доступа обычный Member
получает 404, даже если локальный cache механически совпадает.

Недостаточно одного GroupDetail: не хватает полного original canonical
request/response, output local mapping, request identity, considered non-member
тел, DocumentExcerpt/previous_groups контекстов. GET текущего Source не обещает
произвольный historical text. Аудит их не восстанавливает. Даже имеющиеся
canonical данные сами по себе не удостоверяют их приём сервером или права.

## Фактическая проверка 2026-11-21

| Набор | Итог |
|---|---|
| formal_expectations | 33 PASS, 51.718 s |
| bridge, включая 6 новых audit unit tests | 33 PASS, 36.003 s |
| ai/tests: group/generate/verify | 113 PASS, 87.215 s |
| qwen_z3 saved proposals/review replay | 28 PASS, 141.489 s |
| test_grouping + test_grouping_previous_annotations | 66 PASS, 237.43 s |
| Новая PG compatibility цепочка | 8 PASS, 38.26 s |
| Итого без повторного счёта отдельных запусков | **281 PASS** |
| AI contracts | 9 schemas/88 refs; 38 positive/34 negative; 399 field mutations; 20 pairs — PASS |
| Ruff check/format и git diff --check | PASS |

Тесты запускались по командам README в имеющемся immutable image
`sha256:da3a309e0cc45b09759e559fb8ed53512b67a510884b73d945ad4dd49baa4999`.
Python 3.12.16; Z3 4.15.4.0; jsonschema 4.26.0; referencing 0.37.0;
Ruff 0.17.1; pytest 9.1.1; SQLAlchemy 2.0.55; Psycopg 3.3.6.
Новых dependencies/lock changes нет. Чистая установка зависимостей не проверялась.
Исходники checks подключены read-only, свой /tmp — tmpfs; offline-наборы без сети.
PG checks используют только собственную internal network f2r-formal-c-20261121,
контейнер f2r-formal-c-pg-20261121, БД f2r_formal_c_test на tmpfs без host ports.
PostgreSQL image ID
`sha256:b8faeff7712663c2773a190181e1246e37e364b887611c04658c28b44e2408fe`.
Каждый PG-тест создаёт собственную schema и удаляет её стандартной fixture.
Чужие контейнеры/БД/volumes/tags не менялись. После тестов собственный PG остановлен.

В начальных прогонах были ошибки нового test setup: read-only root без /tmp,
ошибочная попытка отозвать Owner через ProjectAccess и выбор повреждаемой группы
по недетерминированному UUID порядку. Исправлены tmpfs и fixture для обычного
Member/явной конфликтующей группы. Повторный полный новый suite прошёл.
Прежние тесты/ожидания не редактировались. Ruff замечания в новых imports/format
и blank lines старого code-block в изменяемом README устранены. Один запуск
разрешения ранее не состоялся из-за лимита auto-review; после продолжения
пользователем проверки разрешены и выполнены. Это не технический результат Z3.

Нулевой diff относительно базы: backend, frontend, mathematical checker,
group/generate/verify runtime, Qwen, AI JSON Schema 1.0, DOMAIN/REQUIREMENTS,
прежнее PROPOSED хранение. Production pipeline не импортирует audit или Z3.
Полный backend/browser suite и независимое ревью новых изменений не выполнялись:
использованы адресные проверки и собственная проверка кода/границ.
Реальные отзывы/AI inference/оценка смысловой точности не использовались.
Нет доказательства полноты реального мира или глобальной совместимости многих
ожиданий. Пустое/неполное Ω, unknown/timeout/resources не переименовываются в U.

Следующий зависимый шаг — отдельное согласование C1 exporter/review authority/
временного сеанса; product API/storage требуют конкретного последующего решения.
Ни отсутствие формального результата, ни отказ Z3 не задерживают завершение
основного цикла и не меняют человеческое решение. Push/merge не выполняются.
