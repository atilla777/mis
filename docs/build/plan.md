---
type: Development Plan
title: План разработки пакета MIS по сессиям
status: stable
description: Единственный простой список прогресса при создании MIS без RIS и Beads.
---
# Простой план создания MIS

Это **план разработки самого пакета MIS**, а не рабочий процесс MIS для проектов-потребителей. Для этого репозитория **не применять MIS, RIS, Beads, формулы, эпики, roadmap/skills-фреймворк**. Только Git, проверки и этот Markdown.

## Правила коротких сессий

- Каждая новая OpenCode-сессия читает `AGENTS.md`, этот файл и source-map, затем выбирает **первую незавершённую сессию**.
- Одна сессия заканчивается самостоятельным проверяемым результатом и одним/несколькими логическими Git-коммитами.
- Не создавать второй трекер, дневники или handoff-документы. В этом файле фиксировать только `status`, итог, проверки, commit SHA/ссылку, конкретный blocker и следующую сессию.
- Не стремиться к идеальному переносу всего RIS. Копировать нужное, исправлять необходимые связи, делать минимальный end-to-end тест.
- Если сессия прервана, следующая восстанавливает `git status/log`, перечитывает выполненные пункты и завершает ту же сессию; не повторяет проверенные эффекты.
- Разрешённые по текущему поручению изменения, проверки и обычные Git-коммиты не требуют формального промежуточного согласования. Соблюдать реальные ограничения среды.

## S1 — Основа пакета и портативные методики

**Цель:** корректно обнаруживаемый набор скиллов, большая часть базовых методик перенесена.

- [x] Создать каталоги `skills/` и `commands/opencode/` (не использовать Beads).
- [x] Зафиксировать конкретный RIS Git SHA в `source-map.md`; проверить лицензии и необходимые ресурсы.
- [x] Скопировать `ris-port-op-interview`, `ris-port-op-implement-change`, `ris-port-op-review-change` с `references/` в `mis-*`, меняя только имена и технические ссылки; проверить diff с источником.
- [x] Создать минимальный `mis-proj-lib-common` (политики диалога, автономности, достоверности, отчёта и recovery без RIS config).
- [x] Написать две OpenCode command Markdown-заготовки и два flow-скелета с корректным frontmatter/описанием, **без фиктивной рабочей реализации**.
- [x] Проверить обнаружение скиллов в тестовой установке OpenCode, отсутствие обязательных `ris-*` зависимостей, выполнить простые portable dry-runs.

**Критерий завершения:** новые имена обнаруживаются, портативные операции читаются, источники/отличия зафиксированы, нет ложного заявления о готовом `mis-plan`/`mis-run`.

**Прогресс:** `completed` (результат S1 проверен и опубликован)  
**Результат и проверки:** Созданы шесть скиллов и два command-фасада; workflow явно не реализованы. RIS `a2a68cbe0a7c0bd5950cd448fa65f7bcc4424690`, MIT notice сохранён. Сравнение всех шести portable-файлов: только три переименования frontmatter `name`, references и лицензия побайтово совпадают. Проверены локальные Markdown-ссылки, имена папок, наличие всех условных ресурсов; оставшиеся RIS-упоминания только отрицают зависимость, исполняемых ссылок нет. OpenCode **2.0.32**, временная установка `/tmp/opencode/mis-s1-njq5_6ic/.opencode/{skills,commands}`: `/api/skill` подтвердил шесть ID, реальные локальные пути и точные тела; `/api/command` подтвердил обе команды и descriptions; `$ARGUMENTS` и ссылки на flow проверены статически. Использован явный query `?location%5Bdirectory%5D=...` (CLI `--param` в этой проверке не выбирал нужную location). SHA256 пакета `skills/` + `commands/`: `a58378fb0117d937eded41ce209be4c0dd2d1ca8bf69d9ea817cd6a99b7cad6d` (лексикографически отсортированные относительные пути, для каждого `path + NUL + bytes + NUL`).

Portable dry-runs выполнены вручную в текущем контексте, без RIS/Beads/Git и без отдельного модельного прогона: (1) limited interview на синтетическом контракте «integer increment +1, без побочных эффектов», достаточность — известны вход/выход/границы и три примера; все ответы заданы test caller, неизвестных существенных ветвей нет, остановка без вопросов и без сохранения требований; (2) реализация в `portable/` временной копии, режим TDD: `python -B -m unittest -v test_change` дал ожидаемый RED (три assertion failures для `0`, `-1`, `4`), затем GREEN (один тест, три subtests) после единственной правки `return value + 1`; (3) read-only self-review этих двух файлов по заданному контракту: required fixes и optional recommendations пусты, независимый gate **не подтверждён**, отдельного reviewer не запускали. SHA256 fixture: `change.py` — `833556db828032d49efc4c58a380411c53465c917da89bf613a607a10cee2ba6`, `test_change.py` — `615c5323f1f99aff058c776da77e78eed6d91dcd83b57331a178305f61cb53a4`. Это ограниченная проверка переносимости, не доказательство поведения будущих flow или e2e. Приёмка S1 покрывает изоляцию/ресурсы/сохранность методик; функциональные критерии MVP для S2–S5 пока не подтверждены.  
**Коммит:** [`b98046a`](https://github.com/atilla777/mis/commit/b98046ac6f52f63131d56461f84c928e98cda760) — основа пакета S1 и исходные требования. По явному поручению пользователя инициализирован Git, создан публичный `atilla777/mis`, выполнен non-force push в `origin/main`; `git ls-remote` подтвердил полный SHA `b98046ac6f52f63131d56461f84c928e98cda760`, GitHub API подтвердил `visibility: public` и default branch `main`. В `AGENTS.md` закреплено постоянное разрешение на commit/push завершённой работы без повторного подтверждения. Перед публикацией проверены все 33 файла, типовые шаблоны секретов и имена credential-файлов; кэш исключён через `.gitignore`. Git whitespace-check проходит с разрешёнными Markdown hard breaks (`git -c core.whitespace=-blank-at-eol diff --cached --check`).  
**Блокер:** Нет. Следующая реализационная сессия — S2, без повторного переноса S1.

## S2 — Планирование и native Beads

**Цель:** работающий `/mis-plan` от `docs/product/` до Beads Epic/Task/blocks.

- [x] Создать минимальную фиксированную `mis-proj-op-beads` из проверенных операций RIS (`bd`, native graph, update, publish, read-back).
- [x] Создать portable `mis-port-op-plan-milestones` и `mis-port-op-plan-tasks`, используя методики RIS лишь как источник, **без обязательного design**.
- [x] Реализовать flow `mis-flow-plan`: чтение требований и реального состояния; при необходимости портативное интервью; предотвращение дублей; создание/обновление Epic/Task и нативных блокирующих связей.
- [x] Реализовать отчет о плане и следующем `mis-run` с подтверждёнными Beads ID.
- [x] Проверить сценарии: техническая веха; продуктовая веха; standalone Task; повторное планирование без дублей; внешняя blocker-связь; отсутствие необходимости интервью при достаточных данных.

**Критерий завершения:** `/mis-plan` действительно пишет и читает записи в тестовом Beads и не создаёт worktree/spec при планировании.

**Прогресс:** `completed` (реализация S2 опубликована; границы проверки ниже)  
**Результат и проверки:** Три новых скилла, рабочая инструкция `mis-flow-plan`, обновлённый command-фасад и отдельный условный publication resource. Источники/адаптации S1 SHA внесены в source-map; три portable-операции S1 и все их ресурсы по-прежнему совпадают с upstream, кроме `name`. Новые portable-методики не требуют spec/design/трекера и не пишут файлы. OpenCode **2.0.32**, тестовая установка `/tmp/opencode/mis-s2-mt5ce3zx/consumer/.opencode/`: `/api/skill` подтвердил **9** MIS ID, точные локальные пути и полные тела; `/api/command` подтвердил обе команды и новую description `mis-plan`. При первом запросе непосредственно после копирования skill list временно был пуст; повторное чтение вернуло полный набор, финальные assertions прошли без смены конфигурации.

`python -B tests/s2_beads_smoke.py` — **PASS**, реальные **bd 1.3.1 / embedded Dolt / dolt 2.4.1**, fresh fixture `/tmp/opencode/mis-s2-mt5ce3zx`, отдельные локальные Git/Dolt remotes. Подготовка fixture (init/remotes/исторический close) не входит в runtime MIS. Синтетические требования полны: технический unittest entry point, integer increment с `0→1`, `-1→0`, `4→5`, отказом non-integer и запретом network/storage/UI, отдельная документационная Task. Содержание предложено в текущем авторском контексте и записано реальным CLI: technical Epic `s2-27z` / Task `s2-27z.1`, product Epic `s2-hdt` / Task `s2-hdt.1`, standalone `s2-5zp`; внешний prerequisite `s2-33s`, закрытая историческая Task `s2-827`. Проверены own description/acceptance, native parent-child и complete child selection, `s2-hdt.1 → s2-33s` через `blocks`, исключение зависимой Task из ready, отказ обратного цикла без побочных edges, bounded acceptance update с сохранением остальных полей, stale status guard exit **13** без записи. All-status reconciliation фиксированного набора повторно нашёл те же **7** ID по содержанию без новых записей и сохранил closed. Git HEAD/worktree list и все исходные файлы вне `.beads/` не изменились; `docs/spec/` остался пуст. Поля и blockers затем отдельно перечитаны в текущем контексте: у `s2-27z.1` blockers нет; продуктовая Task ожидает открытый внешний prerequisite. По достаточности заданных требований интервью не требовалось; это ручная оценка содержания, не наблюдение новой модельной сессии. Рекомендация для fixture — `/mis-run s2-27z.1`, с явным предупреждением, что сам runtime run пока scaffold.

Sandbox не отправил issue writes автоматически. Отдельный non-force Dolt push и свежий fetch/merge-base подтвердили required **S = R = `6umpkpf1r53fl4o2nsa1qe0f7fgd6tps`** в `file:///tmp/opencode/mis-s2-mt5ce3zx/dolt-remote`, branch `main`; независимый test-only clone подтвердил тот же head. Повторный confirmation-only fetch установил reachability без повторной записи/push. Проверены имена, локальные Markdown-ссылки, зависимости на установленные скиллы, Python syntax, staged scope/типовые secret patterns и whitespace с разрешёнными Markdown hard breaks. Package SHA256 (`path + NUL + bytes + NUL`, как S1): `a3d7b17cb56ba97d78401cd30dd913572c4c0bfc0ab9876bfdfe5b6e251d2c8d`.

**Границы проверки:** CLI smoke исполняет фиксированные proposals и проверяет native контракт, но не является автоматическим planner или полным модельным e2e вызова slash-команды в свежем контексте. Текст flow проверен в текущем авторском контексте; независимый review, реальное адаптивное интервью, concurrent writers, server-mode Dolt, сетевой tracker remote и divergence/rejection recovery не подтверждены этой проверкой. Критерии acceptance 1–4 и 11–12 покрыты ограниченно (содержание/CLI/discovery), не заявлены за полную MVP-приёмку; fresh-session пилоты и сквозной модельный цикл остаются S4–S5. `mis-run` и остальные операции S3–S4 не реализовывались.  
**Коммит:** [`3c13d87`](https://github.com/atilla777/mis/commit/3c13d873df09397c960b050712e7615da0b79806) — S2 implementation, проверен и опубликован в `origin/main`; отдельный `git ls-remote` подтвердил полный SHA `3c13d873df09397c960b050712e7615da0b79806`, после push рабочая копия была чистой. Эта отметка прогресса публикуется отдельным docs-коммитом.  
**Блокер:** Нет для завершённой ограниченной реализации S2. Следующая сессия — **S3**, без повторного переноса/реализации S2; полное модельное e2e не считать уже выполненным.

## S3 — Исполнение и спецификации

**Цель:** `mis-run` доводит одну Task до проверенного кандидата изменений в рабочей копии.

- [x] Реализовать начало `mis-flow-run`: конкретный ID или проверенная выборка, claim, native dependencies, возобновление.
- [x] Добавить нативный OpenCode `worktree_list/create` + `session_move` и проверку реального Git-пути; **без Worktrunk и worktree-adapter**.
- [x] Подключить скопированный `mis-port-op-implement-change` в standard/TDD по правилам тестового проекта.
- [x] Создать `mis-proj-op-sync-spec`: создать/обновить документ в `docs/spec/` для устойчивого реализованного поведения или вернуть обоснованный no-op; сохранить ссылку на Beads ID.
- [x] Подключить независимый `mis-port-op-review-change` с исправлением замечаний и повторной проверкой.
- [x] На отдельном маленьком проекте проверить: небольшая продуктовая Task с spec, техническая Task без spec, возобновление без потери изменений.

**Критерий завершения:** проверенный Git-кандидат в собственной Task-worktree, согласованные тесты и документация; публикацию/закрытие пока не выдавать за сделанные.

**Прогресс:** `completed` (ограниченный результат S3 проверен и опубликован)  
**Результат и проверки:** Реализован S3 `mis-flow-run`, новый `mis-proj-op-sync-spec`, условный Beads execution resource и command description. Один Task/Bug до локального кандидата; ID/ready selection, atomic claim, directed blockers, ownership/session checks, native worktree create/reuse, сохранение связи в notes, move boundary, standard/TDD из правил потребителя, spec/no-op и независимый review/repair loop. Публикация/close в runtime явно отсутствуют, S4 не реализовывалась. Portable S1 и все references/лицензия по-прежнему совпадают с pinned RIS, кроме `name`.

`python -B tests/s3_execution_smoke.py` — **PASS**, OpenCode **2.0.32**, **bd 1.3.1**, embedded Dolt. Fixture `/tmp/opencode/mis-s3-gu8025s5`: native `/api/worktree` list/create и `/api/session/.../move` создали две linked Git worktree с проверенными root/common-dir/base и отдельными idle sessions; отдельный вызов native `session_move` tool и последующий API read-back также подтвердили technical location. Native default create возвращает detached HEAD; для подтверждённо новой чистой копии создана обычная Task-ветка Git, протокол отражён в flow. Product `s3-dtu`, branch `mis/s3-dtu`, worktree `/home/aleksei/.local/share/opencode/worktree/4e78a6/s3-dtu`: RED (ожидаемые assertion failures, без import errors), GREEN (3 unittest tests, включая baseline и subtests 0/-1/4, bool/float/string/None/list rejection), `docs/spec/integer-increment.md` и обновлённая навигация, Beads spec linkage. Technical `s3-33a`, branch `mis/s3-33a`, соседняя worktree: README check command, GREEN (1 baseline test), обоснованный spec no-op. Повторная проверка существующей связи и idempotent own claim не изменила notes, WIP fingerprint и число worktree; foreign untracked sentinel сохранён. Чужой claim отклонён; blocked `s3-zvh` с внешним prerequisite `s3-yhc` исключён из ready и остался без claim. Оба кандидата остаются `in_progress`, Git base/remote неизменен `6c4cb74a00124a62a2841a583fcc2d6271517287`; Dolt local `cb7rpck9o2sqc2fv1um9ugqj5kja5u63`, свежий fetch/merge-base подтвердил неизменённый remote `r0e0vjd1oee2e81vnmj9stad2o078jv8` (не опубликовано).

Discovery проверил **10** MIS skills, точные локальные paths/тела и command description. Учтено наблюдавшееся асинхронное первичное обнаружение 2.0.32 (до пяти чтений, финальное строгое сравнение). Регрессия `python -B tests/s2_beads_smoke.py` — **PASS**, отдельный fixture `/tmp/opencode/mis-s2-poh_ya4p`, его тестовая S2 Dolt-публикация `dcm1blm70bhj464j2kpi8ulcuc2o86n5` не относится к S3 кандидатам.

Независимый read-only reviewer (отдельный контекст `ses_e8353390bffeBd5H1ozlKx0yHa`, не автор/исправитель) вернул **pass** для пакета и обоих потребительских кандидатов; high/medium отсутствуют, исправление/re-review кода не потребовались. Reviewer самостоятельно повторил product/technical unittest (3/1 tests OK), проверил Git/native sessions/Beads read-back и совпадение candidate fingerprints: product `2f901cd794fe6563bba744638bff4a4fb10b59b838fef716175f5e9f1f6920ea`, technical `b092b59355187cb12da27c6493916aad97f3cd2f471790cafa95ab1848806dbc` (алгоритм paths/modes/bytes/deletion markers в smoke, исключён только чужой `foreign.txt`). Review пакета относительно `60300879771c10807d53552f12606a8057c26138` покрыл семь delivery-файлов, без последующих progress docs/README. Low A-L01 устранён краткой актуализацией README (не установщик S5); A-L02 учтён уточнением границ: sentinel создан **после** resume-проверки, его немедленное read-back доказывает лишь сохранность, не resume с уже существующей чужой работой. Package SHA256 `41f30c1bb9507f536817a80a02e8a068b6bccd5244772e00c353c599d3e9b8cf` (алгоритм S1); Python AST, имена/зависимости/ресурсы, Markdown file links, секреты/кэши/область публикации и whitespace проверены.

**Границы проверки:** Smoke исполняет фиксированные test proposals/code/spec через реальные API/CLI, но не является fresh-model `/mis-run` e2e. Выбор и правила flow читаются как инструкции; adaptive no-ID execution, реальные конкурентные writers, recovery неизвестного create/move, сетевой remote и fresh-session пилоты не доказаны. Возобновление smoke — повторное чтение сохранённых фактов в том же процессе, не отдельная модельная сессия. Acceptance 5–7/10 покрываются ограниченно (native contract, два локальных кандидата, review отдельно); 8–9/полный цикл остаются S4–S5. Временные неуспешные fixtures не удалены и не включены в пакет.  
После review в обеих Task guarded append/read-back сохранены проверенные fingerprints/checks и ссылка на reviewer-контекст, без close/push. Dolt local после notes — `s6tmaqcuvn7mgk8up9avb8qc53ks4b7i`; отдельный fetch/merge-base вновь подтвердил прежний remote. Reviewer отдельно проверил финальные README/progress overlays: **pass**, A-L01 resolved, A-L02 addressed; исходный runtime-кандидат не менялся.  
**Коммит:** [`b6b5a63`](https://github.com/atilla777/mis/commit/b6b5a6376eaf13e0682ec743f8d4b68f306daf72) — S3 implementation и проверки, опубликован обычным push в публичный `origin/main`. Отдельный `git ls-remote` подтвердил полный SHA `b6b5a6376eaf13e0682ec743f8d4b68f306daf72`, после push рабочая копия чистая. Эта отметка публикуется отдельным docs-коммитом.  
**Блокер:** Нет для ограниченной реализации S3. Следующая реализационная сессия — **S4**; в рамках S3 не начиналась. Полный модельный e2e и MVP-приёмку не считать выполненными.

## S4 — Публикация, завершение, восстановление

**Цель:** полный цикл `/mis-run`, включая независимое подтверждение Git и Beads результата.

- [x] Реализовать `mis-proj-op-publish-change` на базе RIS: проверить полную публикационную область, upstream, merge/recheck, non-force push, remote read-back; исключить Feature-gates.
- [x] Добавить сохранение результата, закрытие точного Task/Bug, отдельную Beads/Dolt-публикацию и существенную проверку родительского Epic.
- [x] Восстановление после частичного успеха: Git опубликован, Beads ещё открыт; Beads закрыт, публикация не подтверждена; повторный запуск не создаёт дублей/новую worktree.
- [x] Отчёт ✅ 🧪 📚 🔗 ⚠️ ➡️ с рекомендуемым следующим `/mis-run` либо `/mis-plan`, без самостоятельного запуска новой Task.
- [x] Полный e2e: `mis-plan` → `mis-run` → ревью → spec при необходимости → Git-push → Beads close/push → отчёт (модельный цикл в текущем авторском контексте, не fresh-session slash pilot; подробности ниже).

**Критерий завершения:** настоящие инструменты подтверждают оба независимых канала публикации и корректную повторную попытку; конфликт не маскируется как успех.

**Прогресс:** `completed` (реализация S4 проверена независимым review и опубликована; границы проверки ниже)  
**Результат и проверки:** Новый Git publisher, completion resource и полный run flow: whole-tree independent review, all outgoing history, merge/recheck, non-force explicit refspec, fresh remote confirmation; result-before-close exact Task/Bug, отсутствие native close CAS учтено, substantive Epic и отдельный Dolt S/R, confirmation-first recovery и один отчёт без auto-next. Источники/обоснованные отличия pinned RIS внесены в source-map; portable S1 не изменялись.

`python -B tests/s4_publication_smoke.py` — **PASS**, fixture `/tmp/opencode/mis-s4-contract-9bctzvrr`: реальные Git/bd 1.3.1/embedded Dolt; synthetic Task `s4-g2k.1`, Git S `dfa15a7cf5179438cd6b0e384a20ff4463e990e1`, Dolt required `jdiue2o1s12h3dnsksqis1s1asr3ioq7`. Проверены Git-published/Task-open → close; Task-closed/Dolt-absent → failed push на отсутствующий remote (без изменения destination) → разрешённый push; confirmation-only retry без новых notes/records/commits; сохранность foreign untracked; non-force rejection и реальный merge conflict сохраняются, remote не переписан. Epic `s4-g2k` оставлен открыт при закрытом единственном child: собственный критерий external approval не подтверждён. Соседний Bug не claim/close. Это **tool-contract smoke**, не модельное исполнение скиллов и не независимый review payload.

Отдельный **сквозной модельный цикл в текущем авторском контексте**, fixture `/tmp/opencode/mis-s4-e2e-ykk8_3z1/consumer`: прочитаны MIS flow/portable методы и реальные product/rules; содержание плана, тесты, реализация/spec и recovery выбраны моделью через отдельные вызовы инструментов, не фиксированным smoke executor. Test-only preparation создала только baseline/remotes/пустой Beads/копию пакета. Из полных требований без интервью созданы Epic `e4-vnf` и единственная Task `e4-vnf.1`; native parent и blockers прочитаны, план отдельно опубликован в Dolt S=R `qpuroi6s1plttfuftcf2f5923hl1rdip`. Затем atomic claim и **реальные native tools** `worktree_list/create`, `session_move` с отдельным read-back session/location/root/common-dir/branch/Beads routing. Копия `/home/aleksei/.local/share/opencode/worktree/b29619/e4-vnf.1`, branch `mis/e4-vnf.1`, base `6753664607d84fc3d589a4fd79a562c416c70b5a`. Два настоящих TDD-среза: integer multiplication RED assertion failures → GREEN; rejection bool/float/string/None/list/dict/int-subclass RED → GREEN, без runner/import errors. Финально **3 unittest tests OK**, `docs/spec/integer-doubling.md` + navigation, без изменения product/rules. Полный index/committed tree `4ec9d1bb73a59bba29dcc457523d23503a1be108` (все 13 versioned files, exclusions отсутствуют), отдельный reviewer `ses_e834663a7ffevwBhYxkhk8TllJ` — **pass**, high/medium/low пусты, самостоятельно повторил тесты. Commit/merge дали тот же tree (latest primary уже ancestor, новый review не требовался); Git explicit non-force S=R **`5e09f45915bc49c032bf1f1b54c70601e8a0b7f6`** в локальном bare origin `refs/heads/main`, fresh ls-remote/fetch/ancestry подтверждены. На границе Git yes/Task open восстановлены прежняя копия и receipt без повторного commit/push; result записан guarded append/read-back, exact Task close, Epic закрыт только после отдельного сопоставления его собственных criteria с code/tests/spec/review/Git и complete child read-back. На границе local closed/Dolt absent отправлена только недостающая общая история, required S=fresh R **`bu1blsel614l7en9tgioc13m4g5aalnb`** в `file:///tmp/opencode/mis-s4-e2e-ykk8_3z1/dolt-remote`, main. Повторный closed-ID confirmation не изменил notes/records/HEAD/worktree list/Dolt local head; ready пуст, рекомендация `/mis-plan следующая цель`, следующая Task не запускалась.

Регрессии `python -B tests/s2_beads_smoke.py` и `python -B tests/s3_execution_smoke.py` — **PASS**, fixtures `/tmp/opencode/mis-s2-qibzb_7l` и `/tmp/opencode/mis-s3-yzgo35e6`; discovery OpenCode **2.0.32** подтвердил **11** MIS skills с точными локальными paths/телами и оба command-фасада. Устаревшая S3 assertion description команды актуализирована, локальная S3 stop-boundary fixture сохранена. После добавления проверки ресурсов за move S3 regression повторно **PASS**, final fixture `/tmp/opencode/mis-s3-4_itv33y`.

**Границы проверки:** Это полный путь с настоящими инструментами, но **не** запуск slash-команд в свежем модельном контексте: методы прочитаны и выполнены текущим автором; review отдельно. Между partial boundaries не было новой модельной сессии/падения процесса. Только file/local Git и Dolt remotes, embedded engine; concurrent writers, network timeout, успешный изменяющий tree merge/re-review и server-mode не доказаны. Native move в ignored-copy установке скрывает package skills из registry новой worktree; уже прочитанные методы/ресурсы исходной установки остаются доступны по проверенному пути, переносимость обнаружения после move не считать доказанной. Acceptance 8–11 проверены инструментами на указанных случаях; full MVP/fresh-session два пилота и минимальная установка остаются **S5** и здесь не выполнялись.  
Наблюдение move учтено в run flow: **до** перехода сохранить verified installed root, при исчезновении ID читать методы/условные ресурсы той же установки по точному абсолютному пути; без автоматического install/config/copy. В S3 regression добавлена проверка доступности и байтов семи нужных файлов исходной установки после native move. Это исправление runtime recovery ресурса S4, не реализация установщика/пилота S5.

Независимый reviewer consumer отдельно после публикации подтвердил Git SHA/tree и применимость прежнего review, own Epic criteria, оба local close и fresh Dolt fetch/ancestry required revision — **pass**, без новых findings и без записей. Исходная заметка Task «Beads remote not yet confirmed» сохраняет исторический partial boundary; итоговое remote подтверждение дано отдельно, её переписывание/новый Dolt commit ради косметики не выполнялись.

Независимое read-only review пакета `ses_e8345847bffewwUd3sjref40UQ` и focused reassessment move-изменения — **pass**, high/medium нет. Полный prospective snapshot: 44 пути, baseline `57c8fbc75767f25444f0f66b87e5ab38269d4a28`, fingerprint **`828821bc47e9e0d55dc0a7ff3e512667ec589837d416a7d362da35f958e0d79b`** (`sorted path + NUL + Git mode + NUL + bytes + NUL`, у plan predeclared baseline bytes, progress-only edits исключены из runtime approval). Reviewer сам повторил S4 smoke **PASS** в `/tmp/opencode/mis-s4-contract-tsbit7vz`; Python AST, 11 names/resources/Markdown links и whitespace — PASS. Low **S4-R01** о старой фразе «изменена только assertion» устранён: выше отражены обе правки и финальный rerun S3 PASS. Отдельная test-only свежая Git-копия `/tmp/opencode/mis-s4-git-readback-fx5vdftd/consumer` подтвердила remote candidate SHA/tree и **3 tests OK**. Portable S1/resources и MIT notice повторно побайтово сверены с pinned RIS; scope/secret patterns/cache checks и whitespace — PASS. Итоговый package SHA256 алгоритмом S1 — **`e84307b7480770d6a2365c9ce696ff3cb6b3cab7d36090caec64773b22db3160`**. Публичность `atilla777/mis`, established origin/main и отсутствие посторонних outgoing commits проверены перед публикацией.

**Коммит:** [`4c14bd3`](https://github.com/atilla777/mis/commit/4c14bd3d7c9646f3f61556b662018d4ec504be79) — S4 implementation/проверки, опубликован обычным non-force push в публичный `origin/main`. Отдельный `git ls-remote` подтвердил полный SHA `4c14bd3d7c9646f3f61556b662018d4ec504be79`, после push рабочая копия была чистой. Эта финальная отметка публикуется отдельным docs-коммитом.  
**Блокер:** Нет для завершённого ограниченного результата S4. Следующая самостоятельная сессия — **S5**, не начиналась; fresh-session пилоты/MVP-приёмку не считать выполненными.

## S5 — Минимальная поставка и два пилота

**Цель:** пригодный к установке MIS без лишней инфраструктуры.

- [x] Подготовить минимальную инструкцию/скрипт установки пакета в OpenCode (только файлы MIS, `mis-plan.md`/`mis-run.md`, без RIS). Проверить реальные пути OpenCode 2.x.
- [x] Проверить запуск из новой OpenCode-сессии в *чистом* подготовленном проекте.
- [x] Пилот 1: техническая задача/веха (например, инструменты тестирования).
- [x] Пилот 2: небольшая продуктовая механика с `docs/spec/` и настоящим code review.
- [x] Проверить отсутствие лишних runtime-соглашений, старых RIS refs, Formulas, специальных config-файлов и обязательных промежуточных документов.
- [x] Сопоставить результат с [критериями MVP](acceptance.md); исправить только реальные несоответствия, зафиксировать ограничения.

**Критерий завершения:** пакет устанавливается, обе команды доступны, два пилота подтверждают функциональный и технический маршрут.

**Прогресс:** `completed` (минимальная поставка опубликована, оба fresh-session пилота проверены; границы приёмки ниже)  
**Результат и проверки:** Минимальный `scripts/install.py` и инструкция README: только 11 MIS skills/ресурсы/MIT notice и два фасада в `.opencode/{skills,commands}`, без config/init/dependencies. Идентичный повтор — no-op; конфликт и destination symlink/non-directory — отказ до копирования. `python -B -m unittest discover -s tests -p test_install.py -v` — **4 tests OK**. Подготовка `tests/s5_prepare_pilots.py` создаёт только test fixtures, не реализует planner/executor. В рекомендуемой установке package versioned, чтобы новые native worktree и новые сессии обнаруживали методы без runtime install. Документация OpenCode V2 skills/commands/API перечитана; реестр **2.0.32** на обеих новых копиях подтвердил точные paths/тела 11 skills и обе команды. Runtime skills/commands не изменены относительно S4; package SHA256 прежний **`e84307b7480770d6a2365c9ce696ff3cb6b3cab7d36090caec64773b22db3160`**. Python AST, frontmatter names, local Markdown links, whitespace — PASS; исполняемых RIS refs, config/Formulas/Worktrunk dependencies не найдено.

Регрессии S2/S3/S4 — **PASS**, fixtures `/tmp/opencode/mis-s2-lx090zpx`, `/tmp/opencode/mis-s3-dokjrap2`, `/tmp/opencode/mis-s4-contract-gxgdofdi`; как прежде, это CLI/API contract smokes, не модельные workflow и не новый independent review S3-кандидатов. S4 повторно подтвердил partial recovery, confirmation-only, сохранность foreign data, non-force rejection/merge conflict и открытый Epic с неподтверждённым собственным acceptance.

Новые модельные пилоты подготовлены в `/tmp/opencode/mis-s5-kpylc2jy/{technical,product}/consumer`: два разных Git/bd workspace, file/local remotes, package versioned и clean Git, пустой tracker до запуска. Корневые свежие сессии (не fork, не авторский контекст) вызвали настоящие slash-фасады через `session.command`: technical plan `ses_e833e3de7ffeFE4rPbk5qR3DA4` создал standalone `s5t-6om`, product plan `ses_e833e3c66ffezJY1BmZN6JgPdd` — standalone `s5p-kzq`; это допустимая минимизация одной небольшой работы, а не доказательство Epic-маршрута. Plan не менял Git/spec и не исполнял Task; оба отдельно подтвердили Dolt remote. Fresh product replan `ses_e833d2d36ffePG5sF7z8yNH8kU` по явному запросу создал native Epic `s5p-eaa` с own acceptance и переиспользовал прежнюю `s5p-kzq` как единственного child без дублей/blocks, Dolt S=R `e0ar3d2sa6i4vt84udk4vmb1dlnh99bs`. Модель выбрана средой автоматически (**openai/gpt-6.1-terra**), без package model override.

**Технический пилот:** fresh run `ses_e833d2de2ffeHH5fN7clNXcC5G` → atomic claim/native `worktree_list/create/session_move`, worktree `/home/aleksei/.local/share/opencode/worktree/005d29/s5t-6om`, branch `mis/s5t-6om`, base `a93000aeab71a9d72ee6a13b159a92e67a7603df`. В standard mode добавлен только README с Python 3 prerequisite и точной root-командой; **1 unittest test OK**, spec обоснованно не изменён. Независимый reviewer `ses_e833c3df7ffe7YczlKo78p4qm7` сначала честно вернул **unverified** (не прочитаны все inherited package files); автор не обошёл gate, запросил завершение инспекции того же кандидата, итог **pass**, без findings, собственный повтор теста. Снимок: полное baseline tree + README mode `100644`, blob `835c80707da3ee72b045d592fbeb421fd5c56582`, exclusions отсутствуют. Commit/merge не изменил проверенный tree; Git S=R **`85908888e949e4205cf46e062f0d32cc0dc73526`**, tree **`642c6e521cb27f76d92303e7699b561ba2bbbc8a`**, точный `origin/main` в local bare remote. Result сохранён до exact Task close; отдельный Dolt S=R **`d39g8homr0s0bpgf83n842njfik89t89`**, Task closed, Epic отсутствует. Отчёт дал обе публикации/проверки/spec no-op и одну рекомендацию, новую Task не запускал.

**Дополнительный read-back технического пилота:** из moved worktree API вернул точные локальные paths/тела всех **11** skills и обе команды; все references и MIT notice совпали побайтово с пакетом. Реальная run-сессия успешно загружала implement/sync-spec/review/publish через `skill` уже после move; отдельный `pwd/root/common-dir/branch/bd context` подтвердил новую location и прежний prepared workspace. Внешний повтор unittest — **1 test OK**, remote Git SHA/tree и closed Task подтверждены отдельно.

**Fresh-session recovery:** `ses_e833a5513ffe8N9Y4LXGzX05c9`, новая корневая сессия прямо в moved worktree, успешно нашла `mis-run`/методы без наследования installed root. Closed-ID вызов подтвердил Git и Dolt, вернул no-op. Сравнение до/после: точная Beads row (включая notes/revision), Git HEAD/remote, полный worktree inventory, Dolt head и bytes заранее созданного foreign sentinel **не изменились**. Fresh Dolt fetch/merge-base отдельно подтвердил required revision. Transcript не содержит patch, review delegation, create/claim/update/close/commit/push; это настоящее fresh-session confirmation recovery, но не новый fresh-session partial-publication fault test.

**Продуктовый пилот:** fresh run `ses_e833ac35fffeeSoIRV58x9xhAp` выполнил прежнюю Task `s5p-kzq` в native worktree `/home/aleksei/.local/share/opencode/worktree/a8616a/s5p-kzq`, branch `mis/s5p-kzq`, base `769460389c7170817695f74add07d7b8135de906`. Два наблюдённых TDD-среза: exact integer multiplication RED (3 assertion failures для negative/positive/large) → GREEN; TypeError rejection RED (6 assertion failures для bool/int-subclass/float/string/list) → GREEN. Runner/import errors отсутствовали; финально **3 unittest tests OK**, включая baseline, zero и `10**100`, rejection также None/object. Добавлены `docs/spec/integer-tripling.md` с Task linkage и spec navigation. Независимый read-only reviewer `ses_e83398547ffeKDLeRFX6hl61lT` — **pass**, findings отсутствуют; сам повторил 3 теста. Review полного staged tree **`f3dc057c9646c1977d678031b1ae037d6ddd8f8a`**, включая unchanged package/файлы/режимы, без exclusions. Latest primary был ancestor; commit/merge сохранил тот же tree, новый review не требовался. Git explicit non-force S=R **`ab2c3b47915f786168a0c5b1c8ce558147022370`** в local bare `origin/main`. Result сохранён до Task close; Epic `s5p-eaa` закрыт после отдельного чтения own acceptance, полного единственного child и сопоставления с tests/TDD/code/spec/review/Git. Отдельный Dolt S=R **`q8vp2lf211vmri7fv8j433s6df35gq3k`**. Следующая Task не запускалась.

Внешний read-back product: точные closed Task/Epic/sole-child перечитаны, fresh Dolt fetch/merge-base подтвердил required revision; Git delta ровно четыре implementation/test/spec файла, product/rules/package не менялись. Из **нового clone удалённой main** `/tmp/opencode/mis-s5-kpylc2jy/product/git-readback` подтверждены SHA/tree и **3 tests OK**, а не только исходная worktree. Реестр после move вернул 11 точных локальных skill paths/тел и обе команды; все ресурсы/лицензия побайтово совпали с пакетом. Исходные API transcripts и disposable fixtures сохранены локально, не включены в поставку.

**Коммит:** [`d63487f`](https://github.com/atilla777/mis/commit/d63487ff748b62afdc5ce4785ca5f52311657dbe) — установщик, документация и проверки S5; опубликован обычным non-force push в публичный `origin/main`. Отдельный `git ls-remote` подтвердил полный SHA **`d63487ff748b62afdc5ce4785ca5f52311657dbe`**, после push рабочая копия была чистой. Эта итоговая отметка приёмки публикуется отдельным docs-коммитом.  
**Блокер:** Нет для S5 и MVP в проверенной среде. Все S1–S5 завершены; последующее расширение по запросу пользователя — S6 ниже.

**Сопоставление с acceptance.md** (доказательства S2–S4 не заменяются заявлениями о fresh-session покрытии):

| Критерии | Наблюдаемое покрытие |
| --- | --- |
| 1–3: требования, техническая веха, standalone | S2 native Epic/Task/reconciliation и технические критерии; S5 fresh plan для двух standalone, explicit product Epic/replan с reuse без дублей |
| 4: native blocks | S2 цикл/external prerequisite и S3 blocked ready exclusion, повторные regression PASS; не отдельный fresh-model blocked pilot |
| 5–7: реализация, spec, независимость | S5 оба fresh run/native move, standard/TDD, spec/no-op, независимые full-tree review и повторные тесты; unverified gate не обходился |
| 8–9: обе публикации, собственные критерии Epic | S5 две пары Git/Dolt S/R, product own Epic acceptance + complete child; S4 regression partial recovery/conflict/Epic-not-achieved |
| 10: recovery | S3 сохранение копии/notes, S4 partial и confirmation-only; S5 fresh-session closed-ID no-op с сохранностью foreign sentinel и неизменностью row/HEAD/Dolt/worktrees |
| 11: отчёт и одно действие | S5 plan/run/recovery вернули реальные ID, раздельные результаты и одну рекомендацию; следующая Task не claim/execute |
| 12 и нефункциональные ограничения | 11 skills/2 commands, package/resources/license неизменны, нет RIS/config/обязательного design/нового runtime; язык/стратегия из правил fixture, installer Python — только способ поставки |

**Итог приёмки:** MVP принят в указанном проверенном контуре на основе S2–S4 contract/model evidence и двух S5 fresh-session slash pilots. Несоответствий, требующих переписывать runtime/portable-методы, S5 не выявила; реальный пробел поставки/обнаружения после move устранён установщиком и рекомендацией versioned package, без нового runtime-соглашения/config.

**Ограничения:** OpenCode **2.0.32**, bd **1.3.1**, embedded Dolt **2.4.1**, только file/local remotes в пилотах. Сетевой tracker remote, server-mode Dolt, concurrent writers, реальные network timeouts и успешный меняющий tree merge/re-review не доказаны. Fresh-session partial-publication fault recovery, adaptive interview и fresh-model blocked-task маршрут здесь не проверялись; их не подменять другими smoke cases. Ignored/untracked package по-прежнему не гарантирует discovery в новой независимой сессии после move; рекомендуемая versioned установка проверена на обоих пилотах. Установщик не проверяет готовность проекта/capabilities вместо flow, не обновляет конфликтующие файлы и не является transactional/concurrent installer. Independent reviews относятся к двум потребительским кандидатам, не к новому установщику: сам установщик проверен unit-тестами и авторским review. Test-only CLI ошибки (`dolt log -1` вместо `-n 1`, API limit 1000 вместо поддержанного 100) исправлены повторным read-back без ложного успеха или force. Неуспешная первая подготовка fixture (bd init сам создал Git-коммиты) сохранена локально; test script учитывает auto-commit. Секреты/кэши/случайные файлы не публиковались.

## S6 — Компактный статус и обновление snyrk

**Цель:** согласованный `/mis-status [ID]`: дерево незавершённых вех и Task/Bug,
только чтение; публикация MIS и установка обновления в соседний snyrk.

- [x] Добавить `mis-proj-op-show-plan` и command-фасад, обновить требования и установщик.
- [x] Проверить установку, реестр OpenCode и native read-only граф/поддерево/блокеры.
- [x] Опубликовать MIS, обновить установку snyrk без потери локальных изменений.

**Прогресс:** `completed` (MIS и обновление snyrk опубликованы, remote SHA проверены).
**Результат и проверки:** Новый read-only skill/command, установщик теперь поставляет
12 skills и 3 команды. Unit installer — **4 tests OK**; регрессии S2/S3 — **PASS**,
fixtures `/tmp/opencode/mis-s2-8qqodbbj` и `/tmp/opencode/mis-s3-owv5hln1`.
S3 API подтвердил точные paths/тела всех 12 skills в отдельной тестовой установке.
Отдельные readonly reads S2 fixture проверили 7 all-status rows, complete children,
exact-ID subtree, внешний directed blocker, standalone, закрытую историю и ошибку
missing ID; rows/Git HEAD+status/Dolt HEAD до и после совпали. Имена, ресурсы,
Python syntax, whitespace и portable S1 upstream parity — PASS.
Приёмка 13 проверена инструкциями и CLI-контрактом, не fresh-model slash e2e;
визуальное исполнение новой команды отдельной моделью не заявляется.
**Коммит MIS:** [`f94296f`](https://github.com/atilla777/mis/commit/f94296fb397707c8820ce197995ea0f422ea012f), обычный push в `origin/main`; отдельный `git ls-remote` подтвердил полный SHA, затем рабочая копия чистая.
**Обновление потребителя:** Все 20 файлов прежнего установленного пакета snyrk
побайтово совпали с pinned MIS `4852166`; конфликтов/локальных правок нет.
Native OpenCode создал отдельную worktree
`/home/aleksei/.local/share/opencode/worktree/c156d6/mis-status-update`, собственная
ветка `chore/mis-status-update`. Installer проверил все 22 файла обновления;
добавлены skill/command и проектная маршрутизация статуса, revision обновлена.
Реальный `skill` tool загрузил новый скилл из этой worktree, `/api/command`
подтвердил три MIS команды. Полный `/api/skill` CLI-ответ с Phaser-каталогом
обрезался: за полный consumer registry read-back не выдан; точная full-MIS
проверка registry выполнена отдельно в S3 fixture выше.
В snyrk `text:verify` и полный `npm run check` под Node **24.22.1** — **PASS**:
370 unit tests, browser dev/build/sample/localization **4/5/4/5**, playtests и
bundle check. Initial failures: отсутствовала pinned Python toolchain для шрифтов;
локальная ignored `.venv-fonts` подготовлена по hash-pinned requirements и проверки
повторены успешно, versioned fonts/game source не менялись. Зависимости npm для
проверки установлены offline, без изменения package/lock.
Consumer independent reviewer `ses_e82e6480effe7QJgT3fbj1PnxS` — **pass** для полного
tree `e5dee0eae4a2e2722af516877b3e1780386adf1b`, base
`e3097d951955d971a1eff72df7c5b5ccfa1d8a35`, без exclusions и high/medium.
Сам проверил 22/20 package parity, actual skill loading и live readonly Beads
inventory/subtree/edges. Переданные ему внутренние shell-log пути оказались
недоступны; точный full-check receipt повторён после commit с отдельным логом
`/tmp/opencode/snyrk-mis-status-publication-check.log`, без выдачи baseline-лога
за проверку нового снимка. Low wording/evidence замечания рассмотрены: английская
description нового upstream command оставлена, runtime-contract Bug не теряет;
evidence gap закрыт повторным прогоном: `text:verify` и полный `check` — **exit 0**,
в логе указаны точные commit/tree, versioned working copy после checks чистая. Consumer commit
`3e4925fa5cde461270dc08bccb00e5035d0e7df1` сохраняет ровно reviewed tree.
**Публикация потребителя:** [`3e4925f`](https://github.com/atilla777/snyrk/commit/3e4925fa5cde461270dc08bccb00e5035d0e7df1)
отправлен non-force explicit push в `origin/main`; отдельный `git ls-remote`
подтвердил полный SHA. Основной `/home/aleksei/plums/snyrk` fast-forward обновлён
после проверки чистоты, без перезаписи чужой работы; обе копии чистые. В основном
каталоге installer повторно подтвердил 22/22 идентичных файла (no-op), реальный
`/api/command` подтвердил `/mis-status` и обе прежние команды. Beads история
потребителя не менялась. Эта итоговая отметка публикуется отдельным docs-коммитом MIS.
**Блокер:** Нет. Следующей согласованной реализации нет; новая сессия потребителя
может вызвать `/mis-status` (либо `/mis-status <ID>`).

## S7 — Безопасное обновление MIS и поставка в snyrk

**Цель:** `/mis-update` с защитой локальных изменений, публикация MIS и обновление snyrk.

- [x] Добавить скилл, полный script resource и command-фасад; обновить установщик и контракт.
- [x] Проверить Git-snapshot preflight/apply/no-op, конфликты, удаления, unsafe paths и сторонние файлы.
- [x] Проверить реестр, опубликовать MIS и обновить snyrk в отдельной native worktree.

**Прогресс:** `completed` (MIS и обновление snyrk опубликованы, remote SHA проверены).
**Результат и проверки:** 13 skills/4 commands; unit suite — **14 tests OK**.
S3 regression PASS `/tmp/opencode/mis-s3-m7de690p`: реальные native API/CLI,
реестр 13 точных skills. S4 regression PASS `/tmp/opencode/mis-s4-contract-yp3pyezm`:
partial recovery, confirmation-only и сохранённый конфликт. Это contract smokes,
не fresh-model slash pilot нового update. Независимый reviewer
`ses_e82d5027effenwiA042IhoZFcV` нашёл UPD-R01 medium: hard-linked destination
мог изменять сторонний inode. До публикации исправлено полным preflight-отказом
для hard links payload/record; регрессионные тесты наблюдались failing → passing.
UPD-R02 low закрыт явным ограничением upstream mode `100644` и тестом отказа
executable payload; Python resources запускаются через interpreter.
Package re-review того же независимого контекста — **pass**, findings закрыты;
полный 53-path snapshot без exclusions, SHA256
`0b92d69a00d904516beabf6dd42bb523e834d0f0181ad3f275f4bba63fc74868`
(sorted path + NUL + Git mode + NUL + bytes + NUL) совпал с index перед commit.
Дополнительная S2 regression PASS `/tmp/opencode/mis-s2-f7ff2zxj`.
После hard-link fix S3 regression повторно PASS `/tmp/opencode/mis-s3-tjylqo_d`,
включая discovery финальных skill bodies; consumer-candidate reviews этого smoke
не запускались и не подменяют отдельное review обновления snyrk.
Python AST, Markdown links, matching frontmatter IDs, secrets/scope/whitespace
и неизменность portable S1/resources/license относительно предыдущей поставки — PASS.
**Коммит MIS:** [`0427956`](https://github.com/atilla777/mis/commit/0427956ab77fdc1dc272f35269a6dd5272ab5459),
обычный non-force push в публичный `origin/main`; отдельный `git ls-remote`
подтвердил полный SHA `0427956ab77fdc1dc272f35269a6dd5272ab5459`, после push
рабочая копия чистая. Публичность и default branch проверены через GitHub API.
**Обновление snyrk:** Native OpenCode list/create/session_move создали own worktree
`/home/aleksei/.local/share/opencode/worktree/c156d6/mis-safe-update`, branch
`chore/mis-safe-update`, base `913b62f8eee941f533db15a17f701d611a62ff16`
(свежая remote main; основной каталог чистый, отставал на два уже опубликованных коммита).
Preflight реального old package `f94296f` и apply изменили ровно четыре пути:
новый skill, его полный script resource, command и installation record; 25 package
files совпали с target Git objects, повтор — no-op. AGENTS/config/game/Phaser/grilling
и Beads не менялись. Реальный `skill` tool загрузил новый ID из consumer worktree.
Полный authenticated HTTP registry той же managed service подтвердил 13 точных
MIS paths/bodies и 4 command IDs/descriptions. CLI skill output обрезался на большом
Phaser-каталоге и не засчитан за успех; HTTP прочитан без обрезки с существующим
service auth, credentials не выводились. Command API не отдаёт templates:
они проверены побайтово в package parity, не выданы за API read-back.
`npm run text:verify` и полный `npm run check` под Node **24.22.1** — **PASS**:
416 unit tests, browser dev/build/sample/localization **4/5/4/5**, playtest dev/build
и bundle. Receipt `/tmp/opencode/snyrk-mis-update-check.log` фиксирует base и
candidate tree `ea23a6c0600c7a7f108d08a803605159c6e67501`. Dependencies установлены
offline из прежнего lock; pinned Python font environment переиспользовано для
проверок локально, затем скопировано в ignored directory, без versioned изменений.
Обычный build-playtest warning: production debug game не выставлена в window;
deep debug checks пропущены, не выданы за проверенные.
Consumer independent reviewer `ses_e82cf9bd9ffeTCSJ8pSjityF9r` — **pass** для
полного tree `ea23a6c0600c7a7f108d08a803605159c6e67501`, 273 paths, без exclusions
и unresolved high/medium. Сам повторил 416 tests/text:verify/format/i18n/typecheck,
проверил полный package blob/mode parity, реестр, механизм обновления/обратного
удаления и отказ unsafe fixtures. Low-only рекомендации: косметические сообщения
missing file/unknown SHA отложены; неизвестные отдельные mis-* directories сохраняются
как чужие, unknown resources **внутри управляемых** папок запрещены — контракт не расширяется;
пустые каталоги/локальные modes не нормализуются; consumer routing AGENTS сознательно
не меняется в package maintenance. Эти замечания не меняют checked bytes и не блокируют.
**Коммит потребителя:** [`71fc2dd`](https://github.com/atilla777/snyrk/commit/71fc2dd3ebac92e3a7104cd8cd51a32a88a10b29)
сохранил точный reviewed tree. Единственный outgoing commit; remote primary уже
ancestor, новой интеграции/tree change не было. Обычный explicit non-force push
в `origin/main` выполнил pre-push hook без bypass: `text:verify` и полный `check`
повторно **exit 0** под Node 24.22.1. Отдельный `git ls-remote` подтвердил полный SHA
`71fc2dd3ebac92e3a7104cd8cd51a32a88a10b29`, fresh fetch/ancestry — PASS;
own worktree чистая. Основной `/home/aleksei/plums/snyrk` после проверки чистоты
обновлён `merge --ff-only origin/main`, HEAD/tree совпали с опубликованным результатом,
повторный установленный updater вернул **Verified; no changes**, основная копия чистая.
FF также подтянул два ранее опубликованных игровых коммита; это не новые изменения S7.
Beads история потребителя не менялась, никаких tracker close/push не требовалось.
**Границы:** Acceptance 14 подтверждён source tests + настоящим обновлением snyrk,
независимым review и registry/publication read-back; отдельный fresh-model slash
`/mis-update` pilot не запускался. Source authenticity/freshness проверяет caller;
concurrent writers/transactional I/O rollback не поддерживаются. Новые зависимости
приложению не навязаны, только Python 3/Git для maintenance script. Этот итог —
отдельный progress-only docs-коммит после проверенных implementation публикаций.
**Блокер:** Нет. S7 завершена; следующей согласованной реализационной сессии нет.

## Рекомендуемое следующее действие

**S1–S7 завершены.** Новую реализацию автоматически не начинать.
Рекомендуемый запрос в новой сессии snyrk: «Покажи компактный статус через `/mis-status`».
