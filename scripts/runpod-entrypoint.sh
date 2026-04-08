#!/usr/bin/env bash
set -euo pipefail

# ─── RunPod Entrypoint ───────────────────────────────────────────────
# Starts supervisord, waits for Ollama, and loads the model.
# ─────────────────────────────────────────────────────────────────────

OLLAMA_MODEL="${OLLAMA_MODEL:-mannix/llama3.1-8b-abliterated:q8_0}"
OLLAMA_BASE_URL="${OLLAMA_BASE_URL:-http://localhost:11434}"
WORKSPACE="${WORKSPACE:-/workspace}"
GGUF_PATH="${GGUF_PATH:-}"

echo "==> Starting supervisord..."
supervisord -c /etc/supervisor/conf.d/supervisord.conf &
SUPERVISOR_PID=$!

# ─── Wait for Ollama ─────────────────────────────────────────────────
echo "==> Waiting for Ollama to be ready..."
for i in $(seq 1 60); do
    if curl -sf "${OLLAMA_BASE_URL}/" > /dev/null 2>&1; then
        echo "==> Ollama is ready."
        break
    fi
    if [ "$i" -eq 60 ]; then
        echo "ERROR: Ollama failed to start within 60 seconds."
        exit 1
    fi
    sleep 1
done

# ─── Load model ──────────────────────────────────────────────────────
# Check if the model is already loaded
if ollama list 2>/dev/null | grep -q "${OLLAMA_MODEL}"; then
    echo "==> Model '${OLLAMA_MODEL}' already available."
else
    if [ -n "${GGUF_PATH}" ] && [ -f "${GGUF_PATH}" ]; then
        # Import from local GGUF file via Modelfile
        echo "==> Importing model from GGUF: ${GGUF_PATH}"
        MODELFILE_TMP=$(mktemp)
        echo "FROM ${GGUF_PATH}" > "${MODELFILE_TMP}"
        ollama create "${OLLAMA_MODEL}" -f "${MODELFILE_TMP}"
        rm -f "${MODELFILE_TMP}"
    else
        # Pull from Ollama registry
        echo "==> Pulling model '${OLLAMA_MODEL}' from registry..."
        ollama pull "${OLLAMA_MODEL}"
    fi
    echo "==> Model '${OLLAMA_MODEL}' ready."
fi

# ─── Keep alive ──────────────────────────────────────────────────────
echo "==> All services started. Waiting on supervisord (PID ${SUPERVISOR_PID})..."
wait "${SUPERVISOR_PID}"
