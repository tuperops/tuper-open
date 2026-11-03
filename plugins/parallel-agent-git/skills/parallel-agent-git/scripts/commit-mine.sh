#!/usr/bin/env bash
# commit-mine.sh: commit ONLY the given paths through a private index, safe with parallel agents.
#   commit-mine.sh -m "message" [--blob path=versionfile ...] [--expect-base path=commit ...] -- path...
# - Private index = HEAD read at commit time; the shared index's staged entries are untouched.
# - Paths take their working-tree content (deleted in the tree -> deleted in the commit),
#   unless --blob gives another file whose content to commit for that path.
# - Afterwards the committed paths are reset in the shared index (new files included).
set -euo pipefail
msg=""; declare -A blob=(); declare -A base=(); paths=()
while [ $# -gt 0 ]; do
  case "$1" in
    -m) msg="$2"; shift 2;;
    --blob) blob["${2%%=*}"]="${2#*=}"; shift 2;;
    --expect-base) base["${2%%=*}"]="${2#*=}"; shift 2;;
    --) shift; paths=("$@"); break;;
    *) echo "unknown arg $1" >&2; exit 2;;
  esac
done
[ -n "$msg" ] && [ ${#paths[@]} -gt 0 ] || { echo 'usage: commit-mine.sh -m "msg" [--blob p=f] [--expect-base p=hash] -- paths...' >&2; exit 2; }
top=$(git rev-parse --show-toplevel); cd "$top"
for p in "${!base[@]}"; do
  now=$(git log -1 --format=%H -- "$p" || true)
  case "$now" in "${base[$p]}"*) ;; *) echo "REFUSED: $p last changed in $now, you built on ${base[$p]}: rebuild on HEAD" >&2; exit 3;; esac
done
idx=$(mktemp "${TMPDIR:-/tmp}/idx-mine.XXXXXX"); trap 'rm -f "$idx"' EXIT
export GIT_INDEX_FILE="$idx"
git read-tree HEAD
for p in "${paths[@]}"; do
  if [ -n "${blob[$p]:-}" ]; then
    mode=100644; [ -x "${blob[$p]}" ] && mode=100755
    h=$(git hash-object -w -- "${blob[$p]}")
    git update-index --add --cacheinfo "$mode,$h,$p"
  elif [ -e "$p" ]; then
    git add -- "$p"
  else
    git rm -q --cached --ignore-unmatch -r -- "$p"
  fi
done
if git diff --cached --quiet HEAD; then echo "nothing to commit for these paths"; exit 0; fi
git commit -q -m "$msg"
unset GIT_INDEX_FILE
git reset -q HEAD -- "${paths[@]}" 2>/dev/null || true
git log -1 --stat --format='committed %h %s'
