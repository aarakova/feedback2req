# Обмен F2 → формальный эксперимент

**PROPOSED, редакция 0.1, 2026-11-06.** Это предложение read-only обмена,
не новый HTTP API/DTO/таблица/миграция или подключение production worker.
Исходник исследования: опубликованные FINDING_GROUPS_API.md и
TEXT_PROCESSING_API.md на `feat/backend-finding-groups`, HEAD
`4c62684e7769d2c3a71de3264aa15e954a1262d0`. Ветка F2 не объединялась.

## Что можно отобразить точно

| F2 поле | Экспериментальная привязка | Ограничение |
|---|---|---|
| GroupDetail.id/state_id | Постоянная group/state ссылка в прикладном контексте | Не AI local_id |
| conflicts[].id/positions[].id | Точные позиции данного состояния | Нужна явная связь с исходными local_id/ordinal, если используется canonical response |
| members[].ref | Finding StateRef атома | Только выбранный исторический state, не текущий по ID |
| members[].finding | Текст/mode/authorship/evidence выбранной находки | Backend Finding имеет другую форму, чем AI FindingView; не копировать DTO как canonical |
| evidence[].id/state_id/source_ref/text_ref | Fragment/source/text refs | Только доступные разрешённые свидетельства, сохраняются locator/reliability |
| positions[].findings | Полный состав находок позиции | Не сокращать до первого элемента |
| considered_findings | Рассмотренная область | Может включать находки вне members, тела которых в GroupDetail отсутствуют |
| coverage и annotations | Степень обработки и вопросы/неопределённость | Сохранить точные key ↔ state связи; completed не доказывает смысл |
| freshness | Текущая актуальность зависимости | Не оценка достаточности evidence и не право публикации |
| Run Unit.input / Attempt.grouping_result.input_findings | Выбранные refs и key ↔ Finding state | Требуется точная попытка; не заменяет весь исходный canonical snapshot |

Исторический GroupDetail запрашивается по exact group/state. Результат нового
GET текущего state не подставляется в старое исследование. Утрата доступа
или основания должна блокировать новую публикацию, а не скрываться в кеше.

## Почему GroupDetail недостаточно для восстановления AI-ответа

- Нет исходных project_id/request_id канонического вызова в самом DTO;
  проект известен из прикладного маршрута, request identity требует привязки попытки.
- Нет прежних AI local_id и полного их отображения на group/conflict/position IDs.
- Один GroupDetail не содержит все группы/ungrouped выбранной попытки.
- considered_findings могут не входить в members, а значит отсутствуют их тела,
  выбранные фрагменты и часть первоначального контекста.
- context содержит document refs/locator, но не обязательно исходный текст всех
  DocumentExcerpt, их input keys и полный previous_groups контекст вызова.
- Run.input_findings помогает интерпретировать coverage keys, но не возвращает
  все старые локальные адреса и выбранное представление запроса/ответа целиком.
- Нельзя объявлять annotations уже исходными каноническими questions/uncertainties,
  отбросив добавленные backend refs или потеряв привязку origin/key.

Поэтому в этой итерации **нет** адаптера, который сочиняет canonical request/response
из GroupDetail. Автономный replay принимает только уже предоставленные точные
canonical snapshots синтетического реестра.

## Минимальный предлагаемый пакет обмена

После отдельного решения доверенный прикладной exporter мог бы передавать:

```text
{
  exchange_version, project_ref, run/unit/attempt refs,
  selected_group_state_ref | null,
  selected_positions: [{persistent_position_ref, finding_state_refs}],
  canonical_request_snapshot,
  accepted_canonical_response_snapshot,
  local_to_persistent: {groups, conflicts, positions, input_keys},
  source_availability, snapshot_provenance
}
```

При выборе пары без обнаруженного конфликта selected_positions заменяются
явным обоснованным выбором Finding states; группе/конфликту не приписываются
несуществующие IDs. Несколько атомов одной находки не становятся независимыми
участниками. Предлагаемый пакет не даёт модели прав на чтение других объектов.

Пакет должен собираться/проверяться приложением по точным сохранённым refs,
в рамках одного проекта и прав пользователя. Перед публикацией результата
нужна повторная проверка текущей доступности/прав и состояния попытки. Hash
пакета — контроль целостности, не доказательство авторства/истинности.
Правила удаления источников запрещают превращать снимки и hashes в архив
удалённого текста. Прежний
[formal results proposal](formal-expectations-results.md) остаётся PROPOSED.

До согласования такого exchange текущий инструмент не читает F2 HTTP/БД,
не меняет backend, не назначает постоянные IDs и не делает выводов о полноте
реального прикладного контекста. Проверяется только явно переданный синтетический снимок.
