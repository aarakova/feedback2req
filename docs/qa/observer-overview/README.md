# Observer — исправленный обзор

[Галерея сравнения](index.html) · [Матрица и фактические результаты](../../plans/observer-overview.md)

| Ширина | Рабочая сборка | Наполненный fixture | Недоступные данные fixture | Прототип |
|---|---|---|---|---|
| 1440 | [PNG](../observer-v3/screenshots/app-overview-1440.png) | [PNG](fixture-ready-1440.png) | [PNG](fixture-unavailable-1440.png) | [PNG](reference-1440.png) |
| 1280 | [PNG](../observer-v3/screenshots/app-overview-1280.png) | [PNG](fixture-ready-1280.png) | [PNG](fixture-unavailable-1280.png) | [PNG](reference-1280.png) |
| 390 | [PNG](../observer-v3/screenshots/app-overview-390.png) | [PNG](fixture-ready-390.png) | [PNG](fixture-unavailable-390.png) | [PNG](reference-390.png) |
| 320 | [PNG](../observer-v3/screenshots/app-overview-320.png) | [PNG](fixture-ready-320.png) | [PNG](fixture-unavailable-320.png) | [PNG](reference-320.png) |

Базовый внешний вид до исправления доступен в истории Git на cf37a69:
[рабочий обзор](https://github.com/aarakova/feedback2req/blob/cf37a695c1f9f39b8570be2fbfb2ce60e1090342/docs/qa/observer-v3/screenshots/app-overview-1440.png),
[наполненный fixture](https://github.com/aarakova/feedback2req/blob/cf37a695c1f9f39b8570be2fbfb2ce60e1090342/docs/qa/observer-v3/screenshots/fixture-overview-1440.png).

В рабочей сборке нет демонстрационной аналитики. Маркированные fixture-данные
не входят в production entry. Разное количество групп/требований в fixture и
исходном HTML влияет на высоту заполненных списков; пиксельное равенство
бизнес-содержимого не заявляется. Снимки для просмотра не маскированы; golden
рабочих экранов скрывает только случайные тестовые ID и профиль.
