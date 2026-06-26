#!/usr/bin/env sh
# ──────────────────────────────────────────────────────────
# fortress 多机器环境适配 — 确保 .venv/bin/python3 可用
# macOS / Linux 通用，支持 system python / conda / pyenv / uv
# ──────────────────────────────────────────────────────────
set -eu

# Resolve project root from script location (supports running from anywhere)
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENV_PYTHON="${PROJECT_ROOT}/.venv/bin/python3"
cd "${PROJECT_ROOT}"

# Shell function avoids word-splitting issues with paths containing spaces
pip_cmd() { "${VENV_PYTHON}" -m pip "$@"; }

# ── Check if .venv is already healthy ─────────────────────
if [ -x "${VENV_PYTHON}" ]; then
    if ${VENV_PYTHON} -c "import akshare, scipy, langgraph, mcp" 2>/dev/null; then
        echo "✅ .venv/bin/python3 ready, all dependencies present"
        exit 0
    else
        echo "⚠️  .venv exists but missing dependencies, installing..."
        pip_cmd install -e ".[dev]" --quiet
        echo "✅ Dependencies installed"
        exit 0
    fi
fi

# ── Find a Python >= 3.12 on the system ───────────────────
PYTHON=""
for candidate in python3 python; do
    if command -v "${candidate}" >/dev/null 2>&1; then
        if "${candidate}" -c "import sys; sys.exit(0 if sys.version_info >= (3,12) else 1)" 2>/dev/null; then
            PYTHON="${candidate}"
            break
        fi
    fi
done

if [ -z "${PYTHON}" ]; then
    echo "❌ Cannot find Python >= 3.12"
    echo "   Install Python 3.12+ then retry:"
    echo "   macOS:  brew install python@3.13"
    echo "   Ubuntu: sudo apt install python3.12 python3.12-venv"
    echo "   CentOS: sudo dnf install python3.12"
    exit 1
fi

echo "🔧 Using ${PYTHON} ($(${PYTHON} --version)) to create .venv..."

# ── Clean stale .venv before creating a fresh one ─────────
# All three paths below need a clean target directory.
rm -rf .venv

# ── Create or link .venv ──────────────────────────────────
# 1) conda environment → symlink (conda doesn't use stdlib venv)
if command -v conda >/dev/null 2>&1 \
   && ${PYTHON} -c "import sys; sys.exit(0 if 'conda' in sys.version or 'Anaconda' in sys.version else 1)" 2>/dev/null \
   && [ -d "$(${PYTHON} -c "import sys; print(sys.prefix)")/conda-meta" ]; then
    CONDA_PREFIX="$(${PYTHON} -c "import sys; print(sys.prefix)")"
    echo "🔗 Detected conda environment: ${CONDA_PREFIX}"
    ln -s "${CONDA_PREFIX}" .venv
    echo "✅ .venv → conda env symlink complete"

# 2) uv available → uv venv
elif command -v uv >/dev/null 2>&1; then
    uv venv --python "${PYTHON}" .venv
    echo "✅ uv venv complete"

# 3) Fallback: stdlib venv
else
    ${PYTHON} -m venv .venv
    echo "✅ stdlib venv complete"
fi

# ── Install dependencies ──────────────────────────────────
pip_cmd install -e ".[dev]" --quiet
echo "✅ Dependencies installed"
echo ""
echo "🎯 .mcp.json configured to use ./.venv/bin/python3"
echo "   Run /reload-plugins in Claude Code to activate the MCP server"
