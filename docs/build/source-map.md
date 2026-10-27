---
type: Migration Map
title: RIS → MIS — карта заимствования
status: stable
description: Список источников, способ переноса и минимальные изменения.
---
# Карта переноса RIS → MIS

Исходный репозиторий: **https://github.com/atilla777/ris**. Справочник: [RIS skills catalog](https://github.com/atilla777/ris/blob/main/docs/skills.md).

**Зафиксированный источник:** `RIS_SOURCE_SHA: a2a68cbe0a7c0bd5950cd448fa65f7bcc4424690`.
SHA проверен через `git ls-remote ... HEAD` и `git rev-parse HEAD` отдельной
shallow-копии RIS. Все заимствования S1 взяты из этого снимка; не смешивать
произвольные текущие версии. Лицензия upstream — MIT, copyright 2026 Aleksey
Slivka; её точная копия сохранена в `skills/LICENSE-RIS`. При установке переносить
этот файл вместе со скиллами. У переносимых операций нет scripts или сторонних
ресурсов с отдельной лицензией.

## 1. Перенос портативных методик (минимальное изменение)

| RIS source directory | MIS target directory | Изменения |
| --- | --- | --- |
| `skills/ris-port-op-interview/` | `skills/mis-port-op-interview/` | Имя/description и внутренние ссылки только если требуется; передать критерий достаточности интервью |
| `skills/ris-port-op-implement-change/` | `skills/mis-port-op-implement-change/` | Имя/ссылки; сохранить TDD, проверки и ограничения области |
| `skills/ris-port-op-review-change/` | `skills/mis-port-op-review-change/` | Имя/ссылки; сохранить метод независимого review |

Копировать **все релевантные** `references/` и обязательные ресурсы. Любое методическое изменение описать явно рядом с upstream source в конце файла; предпочтительно без них.

## 2. Новые компактные portable-методики

| MIS target | Источники идей | Что убрать/переосмыслить |
| --- | --- | --- |
| `skills/mis-port-op-plan-milestones/` | `ris-port-op-plan-roadmap` | Веха может быть чисто технической; без RIS feature graph и специальных согласований |
| `skills/mis-port-op-plan-tasks/` | `ris-port-op-decompose-feature-spec` и `ris-port-op-plan-epic-features` | Без обязательных Feature spec/design/AC IDs; минимальная Task и native зависимость; задача может быть технической |

## 3. Тонкая проектная реализация (не буквальная копия)

| MIS target | RIS inspiration | Почему переработать |
| --- | --- | --- |
| `skills/mis-proj-op-beads/` | `ris-proj-adapter-beads-tasks` + его `references/` | Только Beads, Epic/Task/Bug/native dependencies и publisher; убрать feature-specific ограничения и config resolver |
| `skills/mis-proj-op-publish-change/` | `ris-proj-op-publish-task` | Сохранить безопасный remote Git, убрать RID/spec/design gates и универсальные маршруты |
| `skills/mis-proj-op-sync-spec/` | `ris-proj-op-update-documentation` | Отдельное обновление фактически реализованного `docs/spec/` по функциональности, no-op если не требуется |
| `skills/mis-proj-lib-common/` | `ris-proj-lib-common` | Только условные инструкции контекста/диалога, безопасности, продолжения и отчёта |

## 4. Полностью новые сквозные скиллы

- `skills/mis-flow-plan/SKILL.md` — единый сценарий Beads-планирования.
- `skills/mis-flow-run/SKILL.md` — одна Task/Bug от выбора до публикации, включая нативный OpenCode worktree.

Slash-фасады пакетируются в `commands/opencode/mis-plan.md`, `commands/opencode/mis-run.md`. Содержат минимальную инструкцию загрузить соответствующий скилл и передать `$ARGUMENTS` без дополнительной бизнес-логики.

## 5. Сознательно не переносить

`ris-proj-op-resolve-context`, `ris-proj-flow-prepare-feature`, `ris-proj-flow-execute-task`, `ris-proj-flow-execute-simple-task`, `ris-proj-op-design-feature`, `ris-proj-op-specify-feature`, `ris-proj-op-decompose-feature`, `ris-proj-op-prepare-task-worktree`, `ris-port-op-prepare-worktree`, `ris-port-adapter-git-worktrees`, `ris-port-adapter-worktrunk-worktrees`, сложный project init, helper stages, Formulas.

## Проверка после каждого копирования

- В target-folder присутствует `SKILL.md`, все прямые `references/` и нужные scripts.
- Frontmatter `name` совпадает с basename папки.
- Поиск по `skills/` не находит **выполняемых** ссылок на отсутствующие `ris-*` или старые RIS docs/config. Строки атрибуции upstream допустимы.
- Прямой portable skill выполняется без RIS-конфигурации, Beads и проектного layout; перенос содержательных ограничений обоснован.
- Сохранены лицензии исходников и их ресурсов; не распространять скопированное с нарушением лицензий.

## Реестр фактических отличий

Во всех строках S1 ниже source commit —
`a2a68cbe0a7c0bd5950cd448fa65f7bcc4424690`. Сравнение полного набора файлов
каждой portable-папки с upstream подтвердило: отличаются только строки `name`
в `SKILL.md`; все references побайтово совпадают. У interview references нет.
Отрицательные упоминания RIS (`No ... required`, `outside RIS`) оставлены как
часть исходного текста: это не вызовы или runtime-зависимости. Limited interview
по-прежнему требует явного критерия достаточности от вызывающей стороны.

| MIS file | RIS source commit/path | Отличие и причина |
| --- | --- | --- |
| `skills/mis-port-op-interview/SKILL.md` | S1 SHA / `skills/ris-port-op-interview/SKILL.md` | Только `name: ris-*` → `name: mis-*` |
| `skills/mis-port-op-implement-change/SKILL.md` | S1 SHA / `skills/ris-port-op-implement-change/SKILL.md` | Только `name`; standard/TDD и ограничения сохранены |
| `skills/mis-port-op-implement-change/references/tdd.md` | S1 SHA / `skills/ris-port-op-implement-change/references/tdd.md` | Без изменений |
| `skills/mis-port-op-implement-change/references/publication-snapshot.md` | S1 SHA / `skills/ris-port-op-implement-change/references/publication-snapshot.md` | Без изменений |
| `skills/mis-port-op-review-change/SKILL.md` | S1 SHA / `skills/ris-port-op-review-change/SKILL.md` | Только `name`; независимость и read-only сохранены |
| `skills/mis-port-op-review-change/references/publication-snapshot.md` | S1 SHA / `skills/ris-port-op-review-change/references/publication-snapshot.md` | Без изменений; это отдельный ресурс review, не implement |
| `skills/mis-proj-lib-common/SKILL.md` | S1 SHA / `skills/ris-proj-lib-common/SKILL.md` (идеи) | Новая краткая библиотека по правилам MIS: без RIS config resolver, Feature lifecycle, prepare/adapters и обязательных published-inputs/artifacts; native OpenCode worktree, отдельные Git/Beads факты, один отчёт, recovery без журнала. Не буквальная копия; upstream references не вызываются |
| `skills/LICENSE-RIS` | S1 SHA / `LICENSE` | Точная копия MIT notice, распространяется вместе с заимствованными скиллами |

`mis-flow-plan`, `mis-flow-run` и `commands/opencode/mis-*.md` — новые файлы
MIS. В S1 это обнаруживаемые точки входа с явным отказом от исполнения.
В S2 `mis-flow-plan` реализован; в S3 `mis-flow-run` доводит работу до локального
проверенного кандидата; S4 добавляет публикацию/закрытие и recovery.

### S2 — новые методики и фиксированный Beads

Все источники ниже прочитаны из того же SHA
`a2a68cbe0a7c0bd5950cd448fa65f7bcc4424690` (локальный `rev-parse` перепроверен).
Это **новые компактные методики и тонкая проектная реализация**, не изменение
трёх побайтово сохранённых portable-операций S1. MIT notice распространяется
вместе с пакетом. Новые файлы не вызывают upstream resources/scripts.

| MIS target | Точный source path в S1 SHA | Сохранено / обоснованное отличие |
| --- | --- | --- |
| `skills/mis-port-op-plan-milestones/SKILL.md` | `skills/ris-port-op-plan-roadmap/SKILL.md` | Goal → bounded outcome, smallest slice, evidence/source distinction, coverage, light boundary check, necessary dependencies. Вместо roadmap → feature refinement: продуктовые **и технические** Milestone, допустим standalone без Epic; без feature graph, design authority/AC slug conventions; дальние цели без подробных Task |
| `skills/mis-port-op-plan-tasks/SKILL.md` | `skills/ris-port-op-decompose-feature-spec/SKILL.md`, `skills/ris-port-op-plan-epic-features/SKILL.md` | One-task-first, независимый проверяемый результат, negative/numeric constraints, integrated checks, identity reconciliation all states, delta, external paths/cycles. Убраны mandatory accepted design/spec, Feature-подсистема и AC IDs; прямых достаточных требований достаточно. Read-only без файлов/трекера |
| `skills/mis-proj-op-beads/SKILL.md` | `skills/ris-proj-adapter-beads-tasks/SKILL.md` и `references/{plan-overview,create,update,structure,concurrency}.md` в этой папке | Сохранены bd 1.3.1 CLI forms, полное all-status чтение, own fields vs brief, exact types/IDs, sandbox, fresh targeted write/read-back, native guards/limits, unknown-create reconciliation, membership vs blocks, cycle check. Новый короткий единый протокол вместо tasks-v1 adapter/config/Feature routes; cross-Epic и standalone blocks допустимы по MIS. Init, claim, close, investigation и execution не реализованы в S2 |
| `skills/mis-proj-op-beads/references/dolt-publication.md` | `skills/ris-proj-adapter-beads-tasks/references/dolt-publication.md` | Компактная адаптация с сохранением shared-history authority, verified embedded DB/remote, confirmation-first S/L/R, reachability/no-op, clean outgoing-only push, fresh remote read-back и ambiguity recovery. Без RIS policy injection/tasks-v1; никаких новых publisher abstractions |

`mis-flow-plan` и command description — собственная реализация MIS по
`docs/product/planning.md`; не копия RIS flow. Единственный условный ресурс
новой Beads-операции — её собственный `references/dolt-publication.md`, перенесён
целиком в адаптированном виде. Прочие RIS references служат источником протокола,
а не runtime-зависимостями: их нужные правила включены в основной скилл; ссылок
на неустановленные resources нет. `tests/s2_beads_smoke.py` — собственный
одноразовый CLI-contract smoke на новых временных fixtures, не runtime planner,
не установщик и не доказательство модельного e2e `/mis-plan`.

### S3 — исполнение до кандидата и sync-spec

Источник идей перепроверен в том же RIS SHA
`a2a68cbe0a7c0bd5950cd448fa65f7bcc4424690`; portable implement/review и их
references **не изменены**, включая standard/TDD и независимость reviewer.

| MIS target | Точный source path / происхождение | Сохранено / обоснованное отличие |
| --- | --- | --- |
| `skills/mis-proj-op-sync-spec/SKILL.md` | S1 SHA / `skills/ris-proj-op-update-documentation/SKILL.md` | Bounded authorization, проверенная dedicated worktree/кандидат, authority requirements vs code, product не переписывается, justified no-op, read-back/links и pending integration. Новая узкая операция `docs/spec/` по функциональности + возврат Beads linkage; без resolver/config, published-inputs, prepare/review YAML и OKF specialist dependency. Upstream references не вызываются: все применимые правила включены в файл |
| `skills/mis-proj-op-beads/references/execution.md` | Собственный S3 протокол по `docs/product/execution.md`; проверенный `bd 1.3.1 update/ready --help` | Exact Task/Bug, native ready/blocks, atomic `update --claim` (несовместим с guards), ownership/read-back, guarded append и связь worktree/spec; без reclaim/force/close. Основной Beads skill лишь условно подключает ресурс, planning запреты сохранены |
| `skills/mis-flow-run/SKILL.md`, `commands/opencode/mis-run.md` | Собственная реализация по MIS execution/specifications/reliability и native OpenCode 2.0.32 API/tool contracts | Один claim/worktree/кандидат, resume из фактов без registry, session_move boundary, implement → sync-spec → independent review/repair. Native create возвращает detached HEAD: для новой чистой проверенной копии обычный Git создаёт Task-ветку; worktree создаёт только OpenCode. Явная S3 граница: нет Git/Beads publication/close |

Новый sync-spec не копирует весь RIS documentation skill и его ресурсы: это
тонкая реализация фиксированного MIS-контракта, не runtime dependency на RIS.
`tests/s3_execution_smoke.py` — собственный disposable CLI/API contract smoke:
две Task, native worktree/session API, реальный TDD fixture/spec и технический
no-op/resume. Это не исполнитель скиллов и не fresh-model slash-command e2e.

### S4 — Git publication, completion и recovery

Источник publisher повторно прочитан из pinned RIS
`a2a68cbe0a7c0bd5950cd448fa65f7bcc4424690` (проверен `git rev-parse HEAD`).
Portable S1 и все их resources не менялись. Это тонкая проектная адаптация, не
переписывание portable алгоритмов и не зависимость на установленный RIS.

| MIS target | Точный source path / происхождение | Сохранено / обоснованное отличие |
| --- | --- | --- |
| `skills/mis-proj-op-publish-change/SKILL.md` | S1 SHA / `skills/ris-proj-op-publish-task/SKILL.md` | Полный publication snapshot с unchanged base/modes/exclusions, independent provenance, all outgoing history/authority, established upstream/primary, own dedicated copy, commit → merge latest primary → affected recheck/independent reassessment → explicit non-force push → fresh remote reachability, confirmation-first retry. Убраны Feature/RID/design gates, Fast exception, adapter/resolver, обязательный YAML review, pre-ID document routes и source-copy maintenance. Task/Bug одинаково используют свои native requirements; локальный primary не обновляется. Все применимые правила включены в основной файл; upstream `references/bug-subject.md` и `references/primary-sync.md` не вызываются, поскольку их специальные routes отсутствуют |
| `skills/mis-proj-op-beads/references/completion.md` | Собственная реализация MIS execution/reliability/acceptance; фактический `bd 1.3.1 close --help`; S2 Dolt resource | Result-before-close, exact ID, read-back и native отсутствие close CAS, без force/continue/claim-next; собственные критерии Epic + complete children, отдельный Dolt S/R, recovery open-after-Git/closed-before-Dolt/confirmation-only. Без отдельного receipt/registry и автоматического reopen |
| `skills/mis-flow-run/SKILL.md`, command, Beads main/execution resource | Собственное расширение S3 | Заменена S3 stop-boundary на publish → result/close → substantive Epic check → Dolt → один отчёт. Explicit closed-ID recovery до claim/create; нет автоматического следующего Task. Native move не переносит ignored package: сохранить installed root в контексте и при потере discovery читать методы/resources той же проверенной установки по абсолютным путям, без runtime install/config |

`tests/s4_publication_smoke.py` — disposable synthetic Git/bd/Dolt fault-contract
smoke, не runtime publisher/исполнитель скиллов и не замена независимому review
или модельному e2e. Отдельный модельный цикл S4 и его ограничения фиксируются
только в плане. Новых upstream resources/scripts, нужных runtime, нет.
