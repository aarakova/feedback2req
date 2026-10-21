# API

Статус: **APPROVED только для И1**, DEC-007 от 2026-10-21, на основе
FIRST_TEXT_SLICE.md, ревизия 1. Реализованы регистрация/сессии/projects/access.
Остальной внешний API остаётся PROPOSED; DEC-006 утверждает стек.

Проект HTTP API первого текстового сценария находится в
[FIRST_TEXT_SLICE.md](FIRST_TEXT_SLICE.md#4-предлагаемый-http-api).
Он сохраняет PROPOSED; ограниченное утверждение И1 записано в DEC-007.

## API principles

Префикс `/api/v1`, JSON UTF-8, UUID строками. Неизвестные поля отклоняются.
Списки: `{items,next_cursor}`; `?cursor=<UUID>` продолжает после последнего ID,
сортировка UUID по возрастанию, размер страницы задаётся сервером (по умолчанию 50).
Курсор задаёт позицию, а не предоставляет доступ. Пароли/хеши/сессионные токены
в JSON-ответах отсутствуют. Ответы не кешируются (`Cache-Control: no-store`).

## Approved contracts

И1, FR-001/FR-003/FR-032 → часть AC-01:

| Метод и путь после `/api/v1` | Вход → ответ | Доступ |
|---|---|---|
| POST `/auth/register` | `{login,password}` → 201 `{id,login}`; без автоматического входа | Анонимный |
| POST `/auth/session` | `{login,password}` → 200 `{user:{id,login},csrf_token}` + cookie | Анонимный |
| GET `/auth/session` | 200 тот же JSON текущей сессии | Сессия |
| DELETE `/auth/session` | 204, отзыв в БД, удаление cookie | Сессия + CSRF |
| POST `/projects` | `{name}` → 201 Project | Сессия + CSRF |
| GET `/projects` | 200 `{items:[Project],next_cursor}` только доступных | Сессия |
| GET `/projects/{project_id}` | 200 Project | Member |
| PATCH `/projects/{project_id}` | `{name}` → 200 Project | Owner + CSRF |
| GET `/projects/{project_id}/access` | 200 `{items:[Access],next_cursor}` | Owner |
| PUT `/projects/{project_id}/access/{user_id}` | `{can_approve:boolean}` → 200 Access; добавить/изменить | Owner + CSRF |
| DELETE `/projects/{project_id}/access/{user_id}` | 204, в том числе если строки уже нет | Owner + CSRF |

Project: `{id,owner_id,name,execution_mode,permissions:{is_owner,is_member,can_approve}}`.
Access: `{user_id,is_owner,is_member,can_approve}`. Владелец включён в список
как вычисляемый участник: права следуют из owner_id, а не из отзывной строки.
PUT/DELETE владельца возвращают 409 `owner_access_immutable`; проектного
переноса владения в И1 нет. PUT неизвестного User.id → 422 `invalid_user`.
Каталога пользователей нет: User.id получает сам пользователь при регистрации
или в GET сессии. Approver — дополнительное право Member, не право управлять.
В И1 execution_mode фиксируется `mock`; обработка ещё отсутствует.

Параметры ввода реализации: login нормализуется NFKC → strip → casefold,
результат 1–128 символов без Unicode-категорий C; входной предел 256 символов.
Пароль регистрации 12–1024 символа, входа 1–1024, без нормализации/обрезания.
Название 1–200 символов с удалением внешних пробелов, пробельное отклоняется.
Параметры являются техническими ограничениями И1, не новой продуктовой baseline.

Изменяющие запросы требуют точный `Origin`, равный F2R_ALLOWED_ORIGIN;
отсутствующий Origin и `null` отклоняются. Анонимные POST register/session
также требуют Content-Type application/json; они не используют прежнюю cookie
для аутентификации и выдают новую сессию при входе. Для остальных изменений
после аутентификации обязателен `X-CSRF-Token` текущей сессии, включая logout.
GET сессии возвращает token клиенту. Cookie `f2r_session`: HttpOnly, SameSite=Lax,
Path=/, Secure для HTTPS. HTTP допускается только явно в локальном loopback-профиле.
Каждый вход создаёт новую независимую сессию, logout отзывает текущую.
В БД — SHA-256 случайного 256-битного session token и CSRF-секрет; сырого token нет.
Сервер проверяет абсолютный и idle сроки; активность продлевает только idle.
По умолчанию 24 часа / 30 минут; параметры и Argon2id задаются F2R_* конфигурацией.

## Error semantics

Форма `{error:{code,message,details:{},request_id}}`; request_id также в
`X-Request-ID`. Ошибки не отражают введённые значения, SQL или чужие объекты.

| HTTP | Причина / основные code |
|---|---|
| 401 | `unauthenticated`: отсутствующая/просроченная/отозванная сессия; `invalid_credentials`: одинаковая ошибка неизвестного login и неверного пароля |
| 403 | `forbidden`: участнику не хватает прав; `origin_rejected`, `csrf_rejected` |
| 404 | `not_found`: неизвестный или недоступный проект с одинаковым сообщением |
| 409 | `login_unavailable`, `owner_access_immutable` |
| 413 | `body_too_large`: фактический body больше конфигурационного лимита (16 KiB) |
| 422 | `invalid_request`, `invalid_login`, `invalid_user`, `json_required` |
| 429 | `rate_limited`: общий IP-лимит register/login, по умолчанию 10 запросов/60 с на процесс |
| 500 | `internal_error`: безопасная ошибка без деталей исключения |

Origin и ограничения запроса проверяются до обработчиков; сессия и CSRF —
до проектного доступа и полномочий. Для И1 лимитер в памяти одного процесса,
сбрасывается при перезапуске; proxy headers не доверяются. Распределённый лимитер
не вводится. Актуальные права читаются из БД при каждом запросе; кеша ролей нет.

## Versioning considerations

Префикс v1 относится к HTTP И1. Политика будущих несовместимых изменений
остаётся открытой; внутренний AI-контракт 1.0 версионируется отдельно.

## Unresolved endpoints/contracts

Все endpoints вне таблицы И1 остаются предложением: материалы, runs/worker,
находки/группы/требования, проверки, решения, удаление и frontend.

## Граница внутренних AI-контрактов

Внутренние AI-контракты утверждены DEC-005 и специфицированы только в
[AI_CONTRACTS.md](AI_CONTRACTS.md). Они не являются HTTP API и не заполняют
этот шаблон внешними endpoints или транспортными решениями.
