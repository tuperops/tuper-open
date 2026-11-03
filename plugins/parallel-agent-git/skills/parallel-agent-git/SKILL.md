---
name: parallel-agent-git
description: Commit safely when several AI agents (parallel Claude Code sessions, loops, sub-agents) share ONE git working tree and index. Commits only your own paths, never sweeps another agent's staged or unfinished files, never uses git stash, and leaves the shared index clean. Use whenever you commit in a repo where other agents may be working at the same time, or before you queue work that another agent will pick up.
---

# Parallel-agent git

When parallel agents share one checkout, the usual habits destroy work: `git add -A` commits
another agent's half-written file, a bare `git commit` takes whatever someone else staged,
`git stash` briefly deletes every other agent's uncommitted changes, and a commit built from an
old copy of a shared file silently reverts a newer commit.

## The rules

1. **Commit only your paths, in one command.** Never `git add -A`, `git add .`, `git add <dir>`,
   `git commit -a`, or a `git add` now and a bare `git commit` later.
   Use the script: `scripts/commit-mine.sh -m "message" -- path1 path2 ...`
   It commits exactly those paths (new, modified or deleted) through a private index built from
   HEAD at that moment, so whatever is staged in the shared index is neither committed nor lost,
   and afterwards it resets those paths in the shared index so no stale "staged" entries remain
   (new files would otherwise show up as staged deletions for the next agent).
2. **A file that also holds another agent's unfinished lines:** write your intended version to a
   separate file and commit that blob for the path:
   `scripts/commit-mine.sh -m "msg" --blob src/game.js=/tmp/my-game.js -- src/game.js`
   The working-tree file is not touched; only your version goes into the commit. Build your version
   from HEAD at that moment, e.g. `git show HEAD:src/game.js > /tmp/my-game.js`, then apply your edit.
3. **Base on HEAD at commit time, not minutes earlier.** If you built your version of a shared file
   from an earlier HEAD, check `git log -1 --format=%H -- <file>` against the hash you started
   from. If it moved, rebuild your version on the new HEAD (the script refuses with
   `--expect-base <hash>` when the file's last commit changed).
4. **Never `git stash` in a shared tree.** To compare with HEAD use `git show HEAD:<file>` or
   `git worktree add /tmp/wt-<you> HEAD` (remove it after with `git worktree remove`).
   Build and test release artifacts from a worktree or from your own commit, never from the
   shared working tree, which may hold another agent's half-done edit.
5. **Commit before you hand work on.** Commit your scripts and state files before you queue a
   follow-up task that uses them: another agent can pick the task up within minutes and start
   editing your uncommitted files.
6. **Check before assuming your work is uncommitted.** Another agent's commit may already have
   taken your file: `git log -1 -- <file>` for each path (new files too).
7. **State files are written atomically** (write `<file>.tmp`, then rename), so two processes never
   leave a half-written JSON.

## Source incidents (tuper operation standing rules, 2026)

- Rule 19 (31 Oct-1 Nov): parallel rounds share one tree and index; commits swept other rounds' files.
- Rule 102 (1 Nov): `git stash` used to compare with HEAD removed every parallel round's work for a moment.
- Rule 161 (2 Nov): a follow-up task queued before committing; a parallel round started editing the
  uncommitted scripts and running them against the same state file.
- Rule 181 (2 Nov): after a private-index commit only modified files were reset; new files showed as
  staged deletions in the shared index.
- Rule 201 (2 Nov): a version built from HEAD at 05:09 was committed at 05:18 and reverted a commit
  made at 05:15.
- Rules 203, 206 (2 Nov): a portal build copied from the shared tree mid-edit threw at load.
