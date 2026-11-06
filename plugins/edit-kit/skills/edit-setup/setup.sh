#!/bin/bash
# Edit Kit workspace setup (macOS). Idempotent: safe to run again.
# Prints one status line per step; exit 2 = needs the editor (Homebrew), exit 1 = failed.
set -u
WS="${EDIT_WORKSPACE:-$HOME/aditor-edits}"
MODEL_DIR="$HOME/.cache/whisper-cpp"
MODEL="$MODEL_DIR/ggml-large-v3-turbo-q5_0.bin"
MODEL_URL="https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-turbo-q5_0.bin"
HERE="$(cd "$(dirname "$0")" && pwd)"

[ "$(uname)" = "Darwin" ] || { echo "FAIL  macOS only in v1"; exit 1; }

BREW="$(command -v brew || ls /opt/homebrew/bin/brew /usr/local/bin/brew 2>/dev/null | head -1)"
if [ -z "$BREW" ]; then
  echo "NEEDS_EDITOR  Homebrew missing. The editor runs this once (asks for the Mac password):"
  echo '  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
  exit 2
fi
echo "OK    homebrew"

for pkg in ffmpeg whisper-cpp; do
  if "$BREW" list --versions "$pkg" >/dev/null 2>&1; then echo "OK    $pkg"
  else "$BREW" install "$pkg" >/dev/null 2>&1 && echo "OK    $pkg (installed)" || { echo "FAIL  brew install $pkg"; exit 1; }
  fi
done

mkdir -p "$MODEL_DIR"
if [ -s "$MODEL" ]; then echo "OK    whisper model"
else
  curl -fL --retry 3 -o "$MODEL.part" "$MODEL_URL" && mv "$MODEL.part" "$MODEL" \
    && echo "OK    whisper model (downloaded)" || { echo "FAIL  model download: $MODEL_URL"; exit 1; }
fi

mkdir -p "$WS/inbox" "$WS/jobs"
[ -f "$WS/CLAUDE.md" ] && echo "OK    workspace $WS (kept existing CLAUDE.md)" \
  || { cp "$HERE/workspace-CLAUDE.md" "$WS/CLAUDE.md" && echo "OK    workspace $WS"; }

if command -v claude >/dev/null && claude mcp list 2>/dev/null | grep -q '^gen'; then echo "OK    gen connected"
else echo "TODO  gen not connected (optional): gen.aditor.ai → Connect Claude → copy the command → paste it in a terminal"
fi
