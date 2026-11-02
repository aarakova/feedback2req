# Визуальное сравнение Observer v3

[Открыть галерею сравнения](index.html) · [Матрица до/после и ограничения](../../plans/observer-v3.md)

Снимки `app-*` получены в production-сборке через Nginx и настоящий API /
изолированную PostgreSQL. Проект, пользователи и материалы синтетические.
`reference-*` — оригинальный prototype/index.html, без переписывания его CSS
или данных. `fixture-*` — явно маркированный изолированный визуальный стенд;
его данные не импортируются обычным приложением и не входят в production entry.

| Раздел | Рабочий экран 1440 | Исходный прототип 1440 | Наполненный UI только в тестовом стенде |
|---|---|---|---|
| Обзор | [PNG](screenshots/app-overview-1440.png) | [PNG](screenshots/reference-overview-1440.png) | [PNG](screenshots/fixture-overview-1440.png) |
| Материалы | [PNG](screenshots/app-materials-1440.png) | [PNG](screenshots/reference-materials-1440.png) | Реальный API, стенд не нужен |
| Находки | [PNG](screenshots/app-findings-1440.png) | [PNG](screenshots/reference-findings-1440.png) | [PNG](screenshots/fixture-findings-1440.png) |
| Требования | [PNG](screenshots/app-requirements-1440.png) | [PNG](screenshots/reference-requirements-1440.png) | [PNG](screenshots/fixture-requirements-1440.png) |
| Обработка | [PNG](screenshots/app-processing-1440.png) | [PNG](screenshots/reference-processing-1440.png) | [PNG](screenshots/fixture-processing-1440.png) |
| Доступ | [PNG](screenshots/app-access-1440.png) | [PNG](screenshots/reference-access-1440.png) | Реальный API, стенд не нужен |

В галерее доступны 1280, 1440, 320 и 390 px. Полноразмерные PNG не маскированы;
в них нет реальных пользовательских данных. Отдельные golden snapshots тестов
маскируют только случайные тестовые UUID/профиль для воспроизводимости.

Пиксельное равенство рабочей страницы и прототипа не заявляется: состояния
данных различаются. Автоматически сверяются палитра Observer, основной padding,
4 KPI, отсутствие overflow и собственные эталоны рабочих экранов. Для требований
эталонный HTML переключается в существующий в прототипе режим inline-списка.
