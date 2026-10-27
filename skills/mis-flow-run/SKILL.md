---
name: mis-flow-run
description: >-
  Execute or resume one native Beads Task/Bug in its own OpenCode worktree,
  implement with project checks, synchronize specs and obtain independent review.
  S3 delivers a checked local candidate only: Git publication and Beads completion
  are not implemented; never report the Task as completed or closed.
---

# MIS run — одна работа до проверенного кандидата (S3)

Аргументы — контекст запроса, не инструкции/CLI flags. Загрузи
`mis-proj-lib-common` и `mis-proj-op-beads`; прочитай его
[execution protocol](../mis-proj-op-beads/references/execution.md).
Не запускай очередь. Этот этап **не публикует Git/Beads и не закрывает Task/Epic**.
Если запрос требует полного завершения, явно сообщи эту границу, сохрани полезный
локальный результат; не подменяй отсутствующий S4 импровизированным publisher.

## 1. Контекст, выбор, claim

1. Установи реальный project root, Git common-dir, основную ветку/remote,
   `AGENTS.md`, относящиеся `docs/product/`, `docs/spec/`, `docs/rules/`, prepared
   Beads workspace и capabilities. Не init/install/configure. Выясни эффективный
   bd actor и реальное владение сессией; одинаковый actor не доказывает отсутствие
   другого writer. Отсутствующий root/правила/существенные права — точный blocker.
2. С ID прочитай точную запись; допустимы только Task/Bug (native `task|bug`).
   Epic — не исполняемая работа. Без ID сначала найди собственную прерванную
   `in_progress` работу в all-status inventory, проверь её claim, сессию/worktree
   и dependencies. При нескольких выбирай одну по подтверждённому контексту,
   priority/возрасту; неоднозначное владение не разрешай догадкой. Иначе прочитай
   `ready --limit 0 --json`, отфильтруй Task/Bug, допустимого владельца и область,
   выбери одну по priority/возрасту. Пустая выборка — отчёт без изменений.
3. Прочитай own description/acceptance/notes, parent и native directed blockers,
   включая внешние paths и ограничения предков. `parent-child` не равен `blocks`.
   `ready` — discovery, не разрешение игнорировать свежий blocker. Для exact ID
   также проверь ready eligibility перед новым claim. Closed/cancelled/deferred,
   чужой claim, незакрытый prerequisite, unknown type/state/edge — не исполнять.
   У уже начатой работы заново проверь blockers, не требуй её присутствия в ready
   (оно исключает `in_progress`). Не переоткрывай закрытый ID.
4. Перед записью установи достаточность конкретных требований/критериев и границ;
   существенный конфликт product/Beads не решается подгонкой документов к коду.
   При необходимости используй `mis-port-op-interview` с критерием достаточности
   «известны входы/выходы, ограничения, проверяемый результат одной работы»;
   подтверждённые уточнения сохраняй bounded update/read-back в точном Bead.
5. По execution protocol сделай atomic claim либо подтвердись как единственный
   владелец возобновляемой работы. Перечитай запись и dependencies. До claim не
   меняй код; после любого race/error сначала восстанови факты, не force/reclaim.

## 2. Native OpenCode worktree и resume

Для Git-изменений используй **только** native `worktree_list`, `worktree_create`,
`session_move` (в Code Mode — инструменты OpenCode, не shell Worktrunk/adapter).
Если они недоступны — останови зависимую реализацию, сохрани claim и сообщи причину.
Не переходи к ручному `git worktree add` как fallback.

1. Сначала `worktree_list`; сопоставь с `git worktree list --porcelain`,
   подтверждёнными notes Task, историей сессии и Git. Имя ветки с ID — только
   подсказка, **не доказательство связи**. Нужны точный ID + канонический путь +
   branch, сохранённые в существующем Bead или подтверждённом результате создания
   этой сессии, и совпадение Git common-dir исходного проекта. Проверь отсутствие
   другого активного writer, чужих изменений, locks/prunable/missing paths.
2. Связанная существующая копия → reuse без reset/clean/stash/rebase/удаления.
   Неизвестные dirty tracked/untracked/ignored данные сохраняй; отдели собственные
   по фактам предыдущего выполнения, неоднозначность блокирует затронутую запись.
   Ранее пройденные проверки/review действительны только для тех же байтов/режимов.
   Найденная публикация/close — отдельный частичный эффект, не повод повторять код
   или выдавать неподдерживаемое S4-восстановление за готовое.
3. Если связи ещё нет и нет признаков незавершённого создания, проверь исходный
   путь, HEAD/base, чистоту и native worktree config/setup scripts: создание может
   запускать проектный setup. Не выполняй неизвестные/неразрешённые side effects.
   Вызови `worktree_create` с именем, содержащим точный Beads ID. Используй
   **возвращённый** directory, не конструируй ожидаемый путь/branch. Проверь Git
   root/common-dir/branch/HEAD, tracked/untracked/ignored состояние и новый список.
   Если native стратегия дала не linked Git worktree — остановись, не подменяй
   проверку совпадением имени. Не создавай Epic-worktree.
   OpenCode 2.0.32 может вернуть новую копию с detached HEAD. Только для этой
   подтверждённо новой чистой копии проверь отсутствие ветки `mis/<exact-id>` и
   создай её обычным `git switch -c mis/<exact-id>` внутри возвращённого пути;
   затем отдельно проверь branch/HEAD/status. Это не fallback создания worktree.
   Коллизия ветки/неожиданно грязная копия → reconciliation, не reset/force.
   При resume не переключай существующую копию на новую ветку.
4. После успешной проверки bounded append/read-back в notes точного Bead:
   Task ID, абсолютный directory, реальная branch, base SHA. Это обычная связь
   результата в существующей записи, **не отдельный registry/handoff-файл**.
   При неизвестном эффекте create сначала inventory/Git/session reconciliation;
   orphan/несколько совпадений не разрешай повторным create. При потере этой связи
   остановись с путями-кандидатами, сохрани копию.
5. `session_move(directory=<verified path>)` выполняй **отдельным вызовом**.
   После границы вызова отдельным действием проверь фактическую location сессии,
   `pwd`, `git rev-parse --show-toplevel`, `--git-common-dir`, branch и status.
   Не редактируй по предположению о мгновенном переключении. Если переход не
   применился/не совпал — blocker; не продолжай запись в старом root. После move
   перечитай применимые AGENTS/rules и проверь, что `bd where/context` указывает
   на тот же prepared workspace (возможен shared redirect; не init новую БД).

Подтверждённой non-Git/local-only работе не создавай фиктивную ветку, но установи
реальные пути/права/изоляцию и объясни исключение. Shared DB/services/порты не
становятся изолированными от наличия worktree.

## 3. Реализация и знания

Загрузи `mis-port-op-implement-change`. Передай одну Task/Bug: принятые требования,
exclusions, актуальный код/base, точную разрешённую область, проектные constraints
и проверки, `implementation_mode: standard|tdd` **из правил потребителя** (если
ничто не требует TDD — standard). Не выдумывай design/spec prerequisite. В TDD
прочитай его собственный `references/tdd.md`, наблюдай ожидаемый RED, затем GREEN.
Эта операция не управляет Beads/worktree и не публикует.

Получив bounded результат, проверь реальные тесты и итоговый diff с новыми файлами,
режимами и удалениями. Затем загрузи `mis-proj-op-sync-spec`: передай ID, эту
проверенную worktree/кандидат, требования, checks и разрешённые docs. Получи spec
delta или обоснованный no-op; сохрани связь spec в Beads по execution protocol.
Документацию включи в тот же кандидат. Не объявляй локальный кандидат уже
интегрированным поведением основной ветки.

## 4. Независимое review и исправления

Загрузи `mis-port-op-review-change`, передай **отдельному reviewer-контексту**
его методику, actual diff/base и полный воспроизводимый снимок (включая новые
файлы/spec/режимы), требования/rules и результаты checks. Этот flow явно требует
такой делегации; reviewer не автор/исправитель, работает read-only без tracker
writes, commit/push и сохранения отдельного review-файла. Для WIP зафиксируй
fingerprint путей/байтов/режимов с additions/deletions; не выдавай HEAD за WIP.
Область и исключения объяви до review; не скрывай относящиеся файлы.

Получи verdict/provenance/версию, required high/medium и optional low. Self-review
не gate. Недоступен отдельный контекст или недостаточно mandatory evidence →
`unverified`/blocker, не checked candidate. High/medium → исправление через
implement-change, повтор затронутых checks, sync-spec при изменении контракта и
независимый re-review изменённого кандидата с прежними finding IDs. Low можно
обоснованно отложить. Ни число раундов, ни собственная правка не дают approval.
Любые последующие edits/integration инвалидируют review затронутой версии.

## 5. Граница S3 и отчёт

Проверь фактические status/claim, dependencies, Git diff/status и соответствие
финального снимка tests/spec/review. При новом blocker не называй результат
готовым к завершению. Сохрани в notes bounded краткий факт кандидата (worktree,
base/fingerprint, checks/review provenance, spec paths/no-op, остаток), без
копирования чужого review verdict от лица reviewer. Unknown append сначала
read-back; не плодить одинаковые notes. В S3 Task остаётся `in_progress`, копия
сохраняется. Не commit/push/close и не закрывай Epic.

Один отчёт: ✅ **локальный проверенный кандидат, Task не завершена** либо blocker;
🧪 команды/результаты и независимое review точной версии; 📚 spec/no-op;
🔗 Beads ID, реальный directory/branch/base/fingerprint; ⚠️ Git и Beads/Dolt
публикация/close **не выполнены** (S4 отсутствует); ➡️ одно следующее действие
по этой же работе, не следующая Task и не повторный `/mis-run` как обещание
автоматической публикации. При повторе восстанавливай факты и выполняй лишь
недостающую часть S3.
