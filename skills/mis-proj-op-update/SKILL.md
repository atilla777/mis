---
name: mis-proj-op-update
description: Safely update the installed MIS package from a verified upstream Git revision without overwriting local modifications. Use for /mis-update or requests to update MIS in a consumer project.
---

# Update installed MIS

Update only MIS skills/resources/license, command facades and `.opencode/mis-installation`.
Do not update OpenCode, RIS, dependencies, project configuration, AGENTS.md or Beads.
This is package maintenance, not a Task execution or a reason to claim/create tracker records.

1. Read consumer AGENTS.md, Git status/log, existing installation record and publication rules.
   Preserve all unrelated work. Follow required native OpenCode worktree/session rules;
   never modify the primary copy when the project requires a dedicated worktree.
2. Locate a trusted external checkout of `https://github.com/atilla777/mis`.
   Verify its origin before fetching. Resolve the requested revision, or freshly fetched
   `origin/main` when none was requested, to a full commit SHA. Do not execute scripts
   from an unreviewed source or install from a moving branch name.
3. Use this skill's `scripts/update.py` by its verified absolute installed path:

   ```sh
   python3 /absolute/installed/mis-proj-op-update/scripts/update.py /consumer/worktree --source /external/mis --revision FULL_SHA
   ```

   The default is read-only preflight. The source checkout must contain both target
   and installed commits. An installation record identifies the baseline. For a legacy
   installation without one, establish its exact upstream revision by full package
   comparison and pass `--from-revision FULL_OLD_SHA`; never guess or use the target
   as baseline merely to bypass a conflict. The script verifies the complete baseline.
4. Inspect the proposed add/replace/delete list and scope. On local modifications,
   missing baseline files, unknown files inside managed skill directories, unsafe paths
   hard links or conflicting additions, stop and report exact paths. No force/automatic merge.
   An identical target file is accepted for confirmation/retry; it is not proof of authorship.
5. With update authorization, repeat the same command with `--apply`. The complete
   preflight runs again before writing; obsolete unchanged upstream files are removed,
   never whole directories. The installation record is written last. Re-run without
   `--apply` and inspect Git diff: target bytes and recorded SHA must agree.
   Do not run concurrently with another writer. This is not a transactional installer;
   on I/O interruption preserve the copy and investigate, never reset local work.
6. Verify the real OpenCode registry for this consumer location: exact target MIS IDs,
   paths/bodies and command templates, not just counts or an unfiltered truncated list.
   Run relevant consumer checks. Before publication obtain independent read-only review
   when required by the project, bound to the complete candidate tree; preserve project
   authorization boundaries. Commit only the requested update and publish non-force
   only when authorized, then independently verify the remote SHA/reachability and status.
7. Report old → new SHA, changed files, checks, Git publication separately, limitations
   and one next action. Do not start a Task. A new session is recommended to avoid mixing
   already loaded old instructions with the updated methods.

The script reads Git objects, not the source working tree. Source trust and remote
freshness are caller responsibilities; it does not fetch, create worktrees, commit or push.
Only non-executable regular upstream files (Git mode 100644) are supported; Python
resources are invoked explicitly with python3, never by executable-bit assumptions.
