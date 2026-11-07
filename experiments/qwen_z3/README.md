# Сохранённые предложения Qwen → формализация → Z3

**Автономный экспериментальный инструмент. Реальный inference не выполнялся.**
Он обрабатывает сохранённые content-ответы, а не запускает модель. Старые
`ai/formal_expectations`, `ai/formal_expectations_bridge`, группировка, AI 1.0,
backend/worker/frontend не изменяются. Новой продуктовой AI-роли нет.

## Запуск

Python 3.12+, зависимости прежнего bridge: Z3 4.15.4.0, jsonschema 4.26.0,
referencing 0.37.0; Ruff 0.11.13 только для разработки. Из собственного worktree:

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r experiments/qwen_z3/requirements.txt
.venv/Scripts/python.exe -B -m experiments.qwen_z3 inventory
.venv/Scripts/python.exe -B -m experiments.qwen_z3 export --output .local/qwen-z3/export-01
.venv/Scripts/python.exe -B -m experiments.qwen_z3 synthetic --output .local/qwen-z3/controls-01
.venv/Scripts/python.exe -B -m experiments.qwen_z3 replay --manifest .local/qwen-z3/controls-01/manifest.json --output .local/qwen-z3/result-01
.venv/Scripts/python.exe -B -m experiments.qwen_z3 negative-controls --output .local/qwen-z3/negative-01
.venv/Scripts/python.exe -B -m experiments.qwen_z3 replay --manifest .local/qwen-z3/negative-01/manifest.json --output .local/qwen-z3/negative-result-01
```

Linux: `.venv/bin/python`. Каталоги вывода всегда **новые**, перезапись запрещена.
`replay` exit 0 — все записи завершили формальную проверку или модель воздержалась;
1 — есть неразрешённые этапы/ошибки; 2 — вход/конфигурация не позволяют запустить
серию. Контрольная серия ожидаемо имеет exit 1: в ней есть случай неполного Ω.
Это не результат unit-тестов и не свидетельство качества модели.

## Что экспортируется и что скрыто от модели

22 случая: все 19 bridge-сценариев и S05/group, S05/reordered, S06/group.
Из S01–S14 только эти три примера содержат готовый canonical group_findings
request. Для остальных в applicability.json фиксируются исходный hash и причина
неприменимости. Другие операции не превращаются в вымышленные Finding states.

`export` создаёт:

- inputs.json — исходные русские находки/фрагменты и точные состояния, ответ
  группировки, область выбранных позиций, input_sha256;
- tasks/<case_id>.json — версионированный system prompt, input и response schema;
- references.json — **отдельные** подготовленные reference-структуры, ожидаемые
  формальные исходы, вопросы эксперту и причины воздержания;
- applicability.json — применимость всех S01–S14.

References строятся [dataset.py](dataset.py) независимо от модельных ответов.
Ошибочные варианты ложного K/D из bridge-каталога не используются как правильные
эталоны: отдельные reference-структуры исправляют, например, true/false на
true/true и ложное разбиение одинакового контекста. Их статус
**PRELIMINARY_ENGINEERING_CONTROL**, не утверждённый semantic gold и не
завершённая человеческая разметка. Ожидаемый класс относится только к данной
структуре. При несопоставимости/неподдерживаемой зависимости reference может
отсутствовать и ожидается воздержание. Неизвестный контекст без полного Ω не U.
Ни inputs.json, ни task не содержат reference, ожидаемый класс или экспертный ответ.

## Формат ответа Qwen

Закрытая [response.schema.json](response.schema.json), версия
`qwen-formal-proposal/1`; её исходник — [schema.py](schema.py).
Это отдельный экспериментальный формат, не изменение group_findings 1.0.

```text
{
  format_version: "qwen-formal-proposal/1",
  case_id, input_sha256,
  decision: propose | abstain,
  selection: <полная явная область позиций/находок> | null,
  formalization: {
    version, decomposition_rationale,
    model: {id,version,formal_model,contexts,relations,method,rationale},
    atoms: [{id,object_id,parameter_id,context_id,values,missing_fields,
             sources:[{finding_key,finding_ref,evidence_keys}]}],
    pair: {left_atom_id,right_atom_id,rationale},
    omissions:[{finding_key,reason}],
    omega: null | {method,justification,declared_complete,variants}
  } | null,
  questions: [...], limitations: [непустые пояснения]
}
```

`abstain` требует null selection/formalization и конкретный вопрос. `propose`
допускает null неизвестных C/A с missing_fields. Domain/values используют прежние
bool/enum/закрытые интервалы, точные десятичные строки и единицы. Ω — только
кандидаты, без автоматического пополнения. Все уровни закрыты: модель не может
включить origin или пять trust confirmations. Даже AI declared_complete=true
не даёт подтверждения полноты. Синтаксически/структурно неверный ответ не
очищается от Markdown/think, не дополняется, не ремонтируется.

[protocol.py](protocol.py) проверяет JSON/схему, case/input hash и полноту
выбранных позиций, затем копирует **неизменённые** исходные canonical snapshots
в прежний bridge. Модель выбирает атомарную пару внутри разрешённой области,
а не меняет произвольно источники/позиции. Origin AI назначается конвертером
из явно сохранённой model metadata. Этот шаг маркирует происхождение, а не
достоверность. Числа, условия и кандидаты Ω из ответа не исправляются.

## Реальные сохранённые ответы: без ручной правки content

Инструкция для Qwen-агента: [HANDOFF_QWEN.md](HANDOFF_QWEN.md).
Агент сохраняет **ровно** content-байты в `<case_id>.json`, транспортную оболочку
и inference-логи отдельно. Настоящий content с новым форматом поступает в collect:

```text
python -B -m experiments.qwen_z3 collect --responses <folder> --model <metadata.json> --case B-01-direct-conflict --case S06-group --output .local/qwen-z3/saved-01
python -B -m experiments.qwen_z3 replay --manifest .local/qwen-z3/saved-01/manifest.json --output .local/qwen-z3/review-01
```

Model metadata — `{name,revision,runtime,parameters,prompt_version}`. Неизвестный
revision обозначается null. Parameters: seed/temperature/top_p/top_k/num_ctx/
num_predict/think; никаких credentials. Указываются фактические значения,
а не придуманные версии/длительности. Collect сохраняет исходные байты и их
SHA-256, строит manifest; никакого inference и никакого редактирования ответа.
Отбор cases явный, пропуски не считаются проверенными записями.

Manifest включает experiment_version=1, mode=saved_model_proposals,
dataset_sha256, model и записи `{case_id,attempt,response_file,response_sha256}`.
Пути относительные к manifest, ограничены его каталогом после resolve, включая
symlinks. Дубликаты case/attempt, старые dataset hash, повреждённые raw hash,
файлы >1 MiB и неизвестные случаи отклоняются. До подтверждения входов каталог
результата не создаётся. Режим saved_model — заявление происхождения поставщиком;
инструмент не доказывает, что байты действительно получены от модели.

Старый Qwen c03d343 отвечает по group_findings, поэтому его **прежний grouping
response** не является формализацией и будет отвергнут этой схемой. Его способ
сохранения content пригоден без изменения байтов; новый prompt/schema и отдельная
серия должны быть назначены Qwen-агентом. Ветки не объединяются, transport не импортируется.

## Независимый review и mandatory gate

Каждый replay создаёт reviews.json с pending-формами. Форма содержит binding
dataset/case/input/raw/model/attempt/reference/packet/prompt hashes, reviewer_kind=human,
вопросы и восемь критериев: atoms, conditions, object_parameter, values_grounded,
unknowns, provenance, contexts, omega_completeness. Вердикт по каждому:
pending/accepted/rejected/uncertain; завершённый вердикт требует reviewer и rationale.

Эксперт отдельно изучает source input, raw, packet и reference; альтернативная
верная формализация может отличаться от reference. Механические различия JSON
не являются смысловой оценкой. Если для полной пары Ω не требуется, эксперт
явно принимает критерий omega_completeness с пояснением «полная пара, единственный
вариант», а не пропускает критерий.

Сохраните заполненную **отдельную** форму как `{reviews:[...]}` и явно назначьте:

```text
python -B -m experiments.qwen_z3 replay --manifest .local/qwen-z3/saved-01/manifest.json --reviews <human-reviewed.json> --output .local/qwen-z3/approved-01
```

Только все accepted для **того же** неизменённого снимка разрешают прежний
`prepare → trusted verifier → Z3`. Pending/uncertain/rejected не создают
формального заключения. Accepted не чинит повреждённую структуру и не делает
declared_complete=false полным. При смене raw (даже whitespace), model/attempt,
reference/dataset/prompt или packet нужен новый review. Если эксперт меняет
саму формализацию, это новый ответ/снимок и отдельная проверка, а не правка истории.

Файл review выбирает **вызывающий человек/доверенный процесс**, не модель.
Локальная программа не удостоверяет личность автора файла криптографически;
она проверяет структуру, обоснования и точную привязку. Кто имеет право дать
подтверждение и проверку настоящих источников, решает доверенный прикладной
контур. Нет CLI approve-all и универсального no-op verifier.

Исключение только для `mode=synthetic_proposals`: точные канонические rawbytes
встроенного реестра, точная synthetic metadata, attempt=1 и совпавший prepared
packet разрешают **инженерный контроль**. В отчёте это прямо не human review.
Любое изменение числа/контекста/raw/model/attempt остаётся неподтверждённым.
Эта оговорка не превращает preliminary references в экспертную истину.

## Результаты, ошибки и оценка

Выход replay: report.json, исходный manifest и source-manifest.bin, raw/*.bin,
packets/*.json, pending reviews.json, отдельные references.json; при review —
applied-reviews.bin с hash. Входные и экспертные файлы не перезаписываются.
Результаты содержат синтетический исходный текст; не использовать этот контур
как архив настоящих отзывов или удалённых источников.

Различаются syntax_error, structure_error, provenance_error,
formalization_error, semantic_error после reviewer, review_required,
incomplete_omega, unconfirmed_omega, review_error, preparation_failure,
z3_technical_error и formal_conclusion. Отказ модели — model_abstained.
Unknown/timeout/resource остаются технической ошибкой, не U.

Отдельно считаются распределение статусов и формальных D/K/S/U, экспертные
вердикты по критериям, требующие уточнения count/fraction с явным denominator,
и экспертные отметки потенциальных false_K/false_D/missed_conflict с числом
неразмеченных записей. Такие отметки требуют обоснованного завершённого review;
они не выводятся из несовпадения строк или provisional reference-класса.
`semantic_accuracy=null`: финальная смысловая точность не установлена.

Негативные controls демонстрируют неверный параметр, потерю условий,
выдуманное число, ложное disjoint, усечённое Ω, одну находку из позиции,
самоподтверждение, подмену state и повреждённый JSON. Семантически неверное,
но формально допустимое предложение может пройти prepare; оно должно остаться
pending или быть отклонено экспертом. Z3 не умеет доказать, что число извлечено
из текста. Все выводы попарные, не глобальная совместимость тройки.

## F2 и границы итерации

Прочитан опубликованный F2 4c62684. Из GroupDetail нельзя надёжно восстановить
весь исходный canonical request/response. Таблица точного отображения,
недостающие поля и минимальный обмен — в
[отдельном PROPOSED](../../docs/proposals/qwen-z3-f2-exchange.md).
Никакой реконструкции по догадкам, HTTP/DTO/worker/миграций здесь нет.
Прежний [formal results proposal](../../docs/proposals/formal-expectations-results.md)
остаётся PROPOSED без изменений.

Без реальной модели нельзя измерить частоту ошибок извлечения, стабильность,
латентность/ресурсы inference и влияние prompt. Без независимого эксперта нельзя
подтвердить смысл, сопоставимость, разбиение контекстов и полноту Ω. Qwen может
предлагать, но не снимать эти ограничения. Проведено тестирование инструмента,
а не завершённое исследование Qwen + Z3. Подробности — [VALIDATION.md](VALIDATION.md).
