# И1 — backend, M01, identity/projects

Разрешение: сообщение пользователя от 2026-10-21 «Приступаем к реализации
feedback2req…», DEC-007. Только И1 ревизии 1 FIRST_TEXT_SLICE; M02–M05,
worker, frontend, материалы и AI не входят. Исходное рабочее дерево чистое.

План:
1. Выполнено: ограниченное утверждение и соответствие требований тестам.
2. Выполнено: минимальный backend, M01 и конфигурация PostgreSQL/Compose.
3. Выполнено: identity/projects, защита запросов и серверные права.
4. Выполнено: pytest на PostgreSQL, native и Compose restart, CI и инструкции.
5. Выполнено: документы синхронизированы; результаты и ограничения ниже.

Структура: backend/feedback2req/{api,identity,projects,persistence}; обработчики
вызывают прикладные сервисы, транзакция охватывает проверку прав и запись.
SQL-запросы находятся в persistence/identity.py и persistence/projects.py,
прикладные правила — в identity/service.py и projects/service.py.
Синхронный SQLAlchemy/Psycopg соответствует небольшой нагрузке И1. Owner
вычисляется из projects.owner_id, членство/Approver остальных — из access.
Новые модули будущих задач не создаются. Сроки сессий, параметры Argon2,
лимиты ввода/частоты — конфигурация, не новые продуктовые требования.

## Соответствие до реализации поведения

| FR → AC / контракт | Сценарий | Тест в backend/tests |
|---|---|---|
| FR-032 → часть AC-01 | Регистрация, нормализация/дубликат, правильный/ошибочный вход | test_identity.py: registration_and_login, duplicate_login |
| FR-032 → часть AC-01; §7 среза | Сессия: новый token, hash в БД, абсолютный/idle срок, logout | test_identity.py: session_storage_and_logout, expired_session, login_rotates_token |
| FR-001 → часть AC-01 | Создание, имя, Owner/Member/Approver по правилу | test_projects.py: owner_and_name |
| FR-003,032 → часть AC-01 | Чужой проект, список, запрет Member/Approver управлять | test_projects.py: isolation_and_permissions |
| FR-032 → часть AC-01 | Назначение/отзыв access/Approver немедленно, защита Owner | test_projects.py: access_lifecycle |
| FR-003,032 → часть AC-01; §4.2,7 | Origin/CSRF, JSON, закрытые поля, безопасные ошибки, 413/429 | test_security.py |
| FR-001,032 → часть AC-01; M01 | Миграция пустой БД, UNIQUE/FK/CHECK, совпадение ORM/DDL | test_database.py: empty_database_upgrade, migration_and_constraints |
| FR-001,032 → часть AC-01; M01 | Новый процесс API читает сохранённые данные; остановка/старт PostgreSQL | test_database.py: fresh_process; scripts/check_i1_restart.py |

AC-01 покрывается только в части И1. Материалы, обработка и межпроектный
AI-контекст не реализуются/не проверяются. Тесты Approver проверяют право,
а не принятие требований. AI-контракты проверяются существующим валидатором.

## Фактическая валидация

2026-10-21:

- pytest: **21 passed**, настоящая PostgreSQL 17.0, Python 3.12.0, Windows.
  Проверены новая пустая БД, пустые схемы, M01/ORM, UNIQUE/FK/CHECK,
  сессии, роли, изоляция, немедленные изменения доступа, безопасные ошибки,
  Origin/CSRF, body/rate limits и откат транзакции без секретов в логах.
- scripts/check_i1_restart.py --pg-ctl: **PASS**. Два реальных stop/start
  отдельного Uvicorn/Python-процесса и PostgreSQL .local/i1-postgres с тем же
  каталогом. Сохранились User, session и её отзыв, Project/имя/Owner,
  назначение и удаление access; API-процессы завершены скриптом.
- Docker: образ собран из backend/Dockerfile; compose.yaml и compose.test.yaml
  config --quiet **PASS**. В отдельном проекте feedback2req-i1-validation
  выполнены up db → build → run alembic upgrade head → up api.
  HTTP register/login/project/access **PASS**, настоящий restart контейнеров
  db и api с прежним постоянным volume **PASS**; сохранены проект, сессия,
  Approver, после restart проверены отзыв доступа и logout. Smoke-проверка
  выполнена локальным скриптом .local/check_compose.py (не артефакт проекта).
  После проверок тестовые контейнеры и native-кластер остановлены; их данные
  и постоянный volume сохранены. Docker Desktop оставлен запущенным.
- Ruff check/format и pip check **PASS**; git diff --check **PASS**;
  цели локальных ссылок изменённых инструкций **PASS**.
- Исходный AI-валидатор **PASS**: 9 схем, 88 refs, 38 положительных и
  34 отрицательных примера, 399 мутаций неизвестных полей, 20 fixture-пар.
  AI-контракты/примеры/валидатор не менялись. Это не оценка AI-семантики.

Промежуточные неудачи: Git потребовал safe.directory (использован только -c,
глобальная конфигурация не менялась); pip не принимал цепочку TLS, режим
truststore отсутствовал в старом pip. Установка успешно повторена с сертификатами
Windows, без отключения TLS. Песочница не позволила старт/stop PostgreSQL;
операции повторены с разрешённым доступом вне неё. Docker первоначально был
остановлен, после запуска Desktop сборка и сценарий прошли. Первичные замечания
Ruff исправлены. Промежуточные сбои не выдаются за успешные проверки.

Ограничения: одно предупреждение Starlette о deprecated-интеграции TestClient
с httpx; тесты проходят, предупреждение не скрывалось. Независимого ревью нет.
Workflow GitHub Actions добавлен, но на GitHub не запускался (push не выполнялся).
Полный pytest прогон выполнен на native PostgreSQL, контейнеры проверены
отдельным HTTP smoke; default Compose-ветка scripts/check_i1_restart.py
отдельно не запускалась, использована native-ветка и прямой Compose restart.
LAN/TLS и настоящий AI не проверялись. Лимитер один на процесс и сбрасывается
при restart. Откат M01 с удалением данных намеренно не реализован.

И1 готова к завершению в разрешённых границах; AC-01 целиком не закрыт.
Для И2 нужно отдельное разрешение на M02, материалы/документы и очередь;
их API, lease/retry и синхронизация остаются PROPOSED и должны быть согласованы
в относящейся к И2 части до реализации.

## Проверенное дополнение при И2а, 2026-10-21

После завершения локальной И1 пользователь сохранил/отправил коммит
`c20f6e51c687f0dac792148320873bac3f6fc14d`. Чтением GitHub API и jobs подтверждён
[запуск 39574175588](https://github.com/aarakova/feedback2req/actions/runs/39574175588),
event=push, completed/success, job i1 success: install, Ruff, pytest и AI-валидатор.
Полного stop/start в этом историческом workflow не было; его успех не доказывает
CI-restart или И2а. Это уточняет прежнее «workflow не запускался» на момент И1.

В И2а TestClient переведён на совместимый httpx2, предупреждение не подавлялось.
Новый workflow добавляет отдельную PostgreSQL/volume Compose для restart и
реальную остановку/старт API с проверкой материалов. Этот изменённый workflow
пока не запускался на GitHub: текущая задача запрещает push. Локальные результаты
И2а и restart приводятся отдельно в [плане И2а](i2a-materials.md).
