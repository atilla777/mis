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
MIS. В S1 это обнаруживаемые точки входа с явным отказом от исполнения, а не
готовые workflow. Они не вызывают ещё отсутствующие операции S2–S4.
