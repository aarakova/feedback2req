# Обмен с Qwen-агентом: qwen-z3/1

Статус: экспериментальная спецификация обмена, не продуктовый AI-контракт.
Ветка-получатель `experiment/qwen-z3-expectations`, база bridge `9f3a1a0`.
Qwen c03d343 изучен как источник транспортного интерфейса; код не объединён.
Этот документ не разрешает установку runtime/весов, передачу данных или inference.

1. Использовать только экспортированные synthetic tasks. Начать с
   `B-01-direct-conflict`, `B-02-different-conditions`, `B-03-compatible`,
   `B-04-incomplete-information`, затем S05/S06 и отрицательные ловушки.
2. Получить пакет командой `python -m experiments.qwen_z3 export --output <new-dir>`.
   Подавать только `tasks/<case_id>.json`: system, input, response_schema.
   **Не подавать references.json или экспертную разметку в prompt.**
3. Применить schema в том виде, который поддерживает выбранный runtime,
   проверив поддержку local $defs/oneOf и полный контекст. Зафиксировать хеш
   реально поданного task. Не урезать источники/схему молча; при нехватке
   контекста сохранить технический отказ и согласовать другой размер отдельно.
4. Назначить model identity: точные name, digest/revision (или null), runtime/version,
   параметры seed/temperature/top_p/top_k/num_ctx/num_predict/think и prompt_version
   `qwen-z3/1`. Отдельно сохранять дату, длительности, usage/stop_reason,
   квантование/устройство и transport envelope. Не выдумывать недоступные показатели.
5. Сохранить **исходный content**, включая неверный JSON/Markdown/think, в
   `<case_id>.json`. Ошибки модели не ремонтировать. Transport envelope и
   диагностику хранить отдельно. Предыдущее group_findings content имеет другую
   схему и не превращается в formalization автоматически.
6. Подготовить metadata.json формата из README. Передать сохранённые content
   и metadata; контур `collect` сам создаст manifest и SHA-256 без ручной правки:

```text
python -m experiments.qwen_z3 collect --responses <content-folder> --model <metadata.json> --case B-01-direct-conflict --case B-04-incomplete-information --output <new-package>
python -m experiments.qwen_z3 replay --manifest <new-package>/manifest.json --output <new-review>
```

Для повторов использовать отдельный пакет и `collect --attempt N`, не
перезаписывать прежние ответы. Доля ошибок/уточнений всегда имеет явный состав
серии; отсутствующие попытки не считаются правильными или завершёнными.

7. Передать pending reviews.json **независимому человеку**, отдельно от raw.
   Эксперт проверяет ссылочную точность, смысл атомов/C/A, неизвестные,
   parameter aliases, контексты и Ω. Не поручать Qwen заполнять подтверждения
   для своих же ответов. Не использовать универсальный synthetic verifier.
8. Применить именно выбранный человеком review через `replay --reviews` в новый
   каталог. Старый raw и snapshot должны остаться теми же. Только затем Z3.

Пять подтверждений bridge не входят в формат ответа. Они строятся программой
только из принятого human review точного снимка или фиксированного инженерного
контроля. Реальный inferencing runner остаётся ответственностью Qwen-агента;
никаких вызовов Ollama в принимающем инструменте нет.

При первом реальном обмене проверить: actual task hash/версии, content bytes,
model metadata, отсутствие references в prompt, все source states и полноту
выбранных позиций. Сначала оценивать стадии ошибок раздельно. До экспертного
review не публиковать смысловую точность, false K/D или «качество совместной системы».
