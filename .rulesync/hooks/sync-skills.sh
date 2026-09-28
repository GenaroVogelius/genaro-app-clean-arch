#!/usr/bin/env bash
# PostToolUse hook (Write|Edit): regenerate Claude Code files from .rulesync/
# whenever a skill under .rulesync/skills/ is created or edited.
#
# Skills written directly in .claude/skills/ are ignored on purpose: .claude/
# is generated output and rulesync.jsonc has `delete: true`, so they would be
# wiped by the next generate. Author skills in .rulesync/skills/ instead.
#
# Exit 2 on failure so Claude sees the error; the edit itself is never blocked.
set -uo pipefail

project_dir="${CLAUDE_PROJECT_DIR:-$(pwd)}"
input="$(cat)"

file_path="$(jq -r '.tool_input.file_path // empty' <<<"$input" 2>/dev/null)"
[[ -z "$file_path" ]] && exit 0
[[ "$file_path" != /* ]] && file_path="$project_dir/$file_path"

case "$file_path" in
  "$project_dir"/.rulesync/skills/*/*) ;;
  *) exit 0 ;;
esac

if ! command -v rulesync >/dev/null 2>&1; then
  export PATH="${PNPM_HOME:-$HOME/.local/share/pnpm}:$HOME/.local/share/pnpm/bin:$PATH"
fi
if ! command -v rulesync >/dev/null 2>&1; then
  echo "sync-skills hook: skill changed but 'rulesync' is not installed (pnpm install -g rulesync). Run 'rulesync generate --targets claudecode' manually." >&2
  exit 2
fi

if ! output="$(cd "$project_dir" && rulesync generate --targets claudecode 2>&1)"; then
  echo "sync-skills hook: 'rulesync generate --targets claudecode' failed:" >&2
  echo "$output" >&2
  exit 2
fi

echo "sync-skills hook: regenerated .claude/ from .rulesync/ after editing ${file_path#"$project_dir"/}"
exit 0
