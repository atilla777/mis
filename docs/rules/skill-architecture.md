---
type: Architecture Decision
title: Минимальная архитектура скиллов MIS
status: stable
description: Два сквозных скилла, портативные методики, тонкие проектные операции.
---
# Состав скиллов

## User entry points

| Команда OpenCode | Внутренний сквозной скилл | Результат |
| --- | --- | --- |
| `/mis-plan` | `mis-flow-plan` | Согласованный достаточный граф Epic/Task в Beads |
| `/mis-run` | `mis-flow-run` | Завершённая и проверенная работа с Git/Beads-публикацией |
| `/mis-status` | `mis-proj-op-show-plan` | Компактное read-only дерево незавершённых работ |
| `/mis-update` | `mis-proj-op-update` | Проверенное обновление только установленного пакета MIS |
| `/mis-install` | `mis-proj-op-install` | Явная установка пакета и подготовка/восстановление embedded Beads |

## Атомарные методики и операции (проектный MVP)

| Скилл | Тип | Источник/принцип |
| --- | --- | --- |
| `mis-port-op-interview` | Portable; перенос | `ris-port-op-interview` |
| `mis-port-op-plan-milestones` | Portable; новый | `ris-port-op-plan-roadmap`: выделять технические и продуктовые вехи |
| `mis-port-op-plan-tasks` | Portable; новый | `ris-port-op-decompose-feature-spec` + `ris-port-op-plan-epic-features`; **без** design/spec/feature-gates |
| `mis-port-op-implement-change` | Portable; перенос | `ris-port-op-implement-change`, режим TDD/standard по проекту |
| `mis-port-op-review-change` | Portable; перенос | `ris-port-op-review-change`, независимая оценка конкретного снимка |
| `mis-proj-op-sync-spec` | Project; новый | Обновить конкретное реализованное поведение в `docs/spec/` |
| `mis-proj-op-beads` | Project; упрощение | `ris-proj-adapter-beads-tasks`, один фиксированный `bd` |
| `mis-proj-op-show-plan` | Project; упрощение | `ris-proj-op-show-plan`, компактное read-only дерево без Feature-модели |
| `mis-proj-op-update` | Project; новый | Сравнение точных Git-ревизий, защита локальных правок, ограниченный update script |
| `mis-proj-op-install` | Project; новый | Установка общим package engine и явная подготовка Beads в проектном Git remote |
| `mis-proj-op-publish-change` | Project; упрощение | `ris-proj-op-publish-task`, безопасная Git-интеграция/проверка remote |
| `mis-proj-lib-common` | Shared; сокращение | `ris-proj-lib-common`: контекст, диалог, одноразовые подтверждения, recovery, отчёт |

Всего **14 скиллов, включая 2 основных сквозных**, проектные операции статуса, установки и обновления. Установка/обновление разделены по полномочиям, но используют один package script. Внутренние `references/` и `scripts/` ресурсы не равны новым зарегистрированным скиллам.

## Границы ответственности

- **Flow** координирует одну операцию, принимает недостающие решения в едином диалоге, вызывает методы по мере потребности, держит общий результат и публикацию.
- **Portable op** получает уже отобранные требования, код/контекст и выдаёт результат без `bd`, project root, Git-публикации или настройки OpenCode.
- **Project op** знает фиксированную структуру MIS, конкретный инструмент и одну операцию. Нет универсального config resolver.
- **Shared lib** содержит только общие правила; не решает, какую задачу делать, и не запускает полный lifecycle.

Профиль выбирает flow по [политике делегирования](../../skills/mis-proj-lib-common/references/delegation.md):
ограниченная реализация — `standard`, требования/сложные решения — `advanced`,
независимый review/re-review — отдельный `advanced`. Модель задаёт OpenCode,
не portable skill. Новых скиллов, MIS-конфига или обязательного design-gate нет.

## Ленивая загрузка

OpenCode регистрирует скиллы, но полные тела отдельных методик загружаются лишь при вызове. Оба flow читают релевантные ресурсы по условиям. Не загружать весь каталог при запуске. В целях низкого контекста оставить `mis-proj-lib-common` коротким, а редкие правила положить в тематические `references/`.

## Изоляция от RIS

MIS — самостоятельный репозиторий и пакет. Не устанавливать `ris-*` как транзитивную зависимость. Копировать source и нужные `references/`, переименовывать технические связи и frontmatter в пространство `mis-*`; нельзя изменить name в заголовке, оставив внутренний вызов удалённого `ris-*`. Саму содержательную методику портативных операций сохранять без переписывания. Исходные лицензии и upstream SHA сохраняются в [карте переноса](../build/source-map.md).

## Worktree

В первую версию **не включать отдельный скилл для worktree и ни одного Worktrunk/git-worktree adapter**. `mis-flow-run` использует нативный OpenCode, с минимальным проверенным протоколом выбора/создания/повторного использования рабочей копии. Если восстановление требует явно независимого действия, можно позже выделить скилл по фактическому примеру.

## Не включать в MVP

Feature prepare/design/decomposition workflow RIS, Formulas, `mis-next`, отдельный `mis-init` вне явной установки, адаптеры альтернативных трекеров, Help/Retro workflow, отдельный Run-Bug процесс, TDD-only wrapper (portable implement уже поддерживает режим).
