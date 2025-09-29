#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT="10000"
MARKER="# >>> codex-plus setup >>>"

if [[ ! -x "${SCRIPT_DIR}/proxy.sh" ]]; then
  chmod +x "${SCRIPT_DIR}/proxy.sh"
fi

expand_path() {
  local path="$1"
  if [[ "$path" == ~* ]]; then
    echo "${HOME}${path:1}"
  else
    echo "$path"
  fi
}

choose_shell_rc() {
  local default_shell="${SHELL:-}"
  local -a candidates=()

  case "$default_shell" in
    *zsh)
      candidates=("~/.zshrc" "~/.zprofile" "~/.profile" "~/.bashrc" "~/.bash_profile")
      ;;
    *bash)
      candidates=("~/.bashrc" "~/.bash_profile" "~/.profile" "~/.zshrc")
      ;;
    *)
      candidates=("~/.bashrc" "~/.bash_profile" "~/.zshrc" "~/.profile")
      ;;
  esac

  local resolved=""
  for candidate in "${candidates[@]}"; do
    local expanded
    expanded="$(expand_path "$candidate")"
    if [[ -f "$expanded" ]]; then
      resolved="$expanded"
      break
    fi
  done

  if [[ -z "$resolved" ]]; then
    resolved="$(expand_path "${candidates[0]}")"
    touch "$resolved"
  fi

  echo "$resolved"
}

append_snippet() {
  local rc_file="$1"
  if grep -Fq "$MARKER" "$rc_file"; then
    echo "Codex-Plus snippet already present in $rc_file"
    return
  fi

  cat <<EOF_SNIPPET >> "$rc_file"
$MARKER
# Automatically added by codex_plus/install.sh on $(date)
export CODEX_PLUS_REPO="${SCRIPT_DIR}"
export CODEX_PLUS_PROXY_PORT="${PORT}"

codex_plus_proxy() {
  local cmd="\${1:-status}"
  if [[ \$# -gt 0 ]]; then
    shift
  fi
  "\${CODEX_PLUS_REPO}/proxy.sh" "\$cmd" "\$@"
}

codex() {
  local pid_file="/tmp/codex_plus/proxy.pid"
  local port="\${CODEX_PLUS_PROXY_PORT:-${PORT}}"
  if [[ -f "\$pid_file" ]] && kill -0 "\$(cat "\$pid_file" 2>/dev/null)" 2>/dev/null; then
    OPENAI_BASE_URL="http://localhost:\${port}" command codex "\$@"
  else
    command codex "\$@"
  fi
}

alias codexd='codex --yolo'
alias codex-plus-proxy='codex_plus_proxy'
# <<< codex-plus setup <<<
EOF_SNIPPET

  echo "Configured Codex-Plus shell helpers in $rc_file"
}

main() {
  local rc_file
  rc_file="$(choose_shell_rc)"
  echo "Using shell configuration: $rc_file"
  append_snippet "$rc_file"
  printf '\nNext steps:\n'
  echo "  1. source \"$rc_file\" (or restart your shell)."
  echo "  2. Run \"codex-plus-proxy enable\" to start the proxy (aliases to proxy.sh)."
  echo "  3. Use \"codex\" or \"codexd\" to automatically route through Codex-Plus when the proxy is running."
}

main "$@"
