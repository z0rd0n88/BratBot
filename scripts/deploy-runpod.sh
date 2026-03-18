#!/usr/bin/env bash
set -euo pipefail

# ─── BratBot RunPod Deployment Script ────────────────────────────────
#
# Usage:
#   ./scripts/deploy-runpod.sh build          Build and push the Docker image
#   ./scripts/deploy-runpod.sh push           Push a pre-built image
#   ./scripts/deploy-runpod.sh switch-model   Switch the active Ollama model on the pod
#   ./scripts/deploy-runpod.sh update         Full deploy: build, push, restart pod
#   ./scripts/deploy-runpod.sh ssh            SSH into the pod
#   ./scripts/deploy-runpod.sh status         Check service status on the pod
#   ./scripts/deploy-runpod.sh logs           Tail logs from the pod
#   ./scripts/deploy-runpod.sh models         List available models on the pod
#
# Environment variables (set in .env.runpod or export before running):
#   RUNPOD_POD_ID       — RunPod pod ID (required for remote commands)
#   RUNPOD_SSH_KEY      — Path to SSH private key (default: ~/.ssh/id_ed25519)
#   REGISTRY_IMAGE      — Full image name (default: ghcr.io/<user>/bratbot)
#   IMAGE_TAG           — Image tag (default: runpod-latest)
#
# ─────────────────────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "${SCRIPT_DIR}")"

# Load config from .env.runpod if it exists
if [ -f "${PROJECT_DIR}/.env.runpod" ]; then
    set -a
    source "${PROJECT_DIR}/.env.runpod"
    set +a
fi

# ─── Defaults ────────────────────────────────────────────────────────
REGISTRY_IMAGE="${REGISTRY_IMAGE:-ghcr.io/your-org/bratbot}"
IMAGE_TAG="${IMAGE_TAG:-runpod-latest}"
RUNPOD_SSH_KEY="${RUNPOD_SSH_KEY:-${HOME}/.ssh/id_ed25519}"
RUNPOD_POD_ID="${RUNPOD_POD_ID:-}"
RUNPOD_SSH_PORT="${RUNPOD_SSH_PORT:-22}"

FULL_IMAGE="${REGISTRY_IMAGE}:${IMAGE_TAG}"

# ─── Recommended small models for cost savings ───────────────────────
# These models run well on cheaper GPUs (RTX 3070/A4000, 8-16GB VRAM):
#
#   Model               VRAM    Speed   Quality   Best GPU
#   ─────────────────────────────────────────────────────────
#   qwen3:8b            ~5GB    Fast    Great     RTX 3070 ($0.10/hr)
#   qwen3:4b            ~3GB    V.Fast  Good      RTX 3070 ($0.10/hr)
#   phi4-mini           ~3GB    V.Fast  Good      RTX 3070 ($0.10/hr)
#   gemma3:4b           ~3GB    V.Fast  Good      RTX 3070 ($0.10/hr)
#   llama3.2:3b         ~2GB    V.Fast  Decent    RTX 3070 ($0.10/hr)
#   qwen3:14b           ~9GB    Medium  Excellent RTX A4000 ($0.20/hr)
#   gemma3:12b          ~8GB    Medium  Excellent RTX A4000 ($0.20/hr)
#
# Switch with: ./scripts/deploy-runpod.sh switch-model qwen3:8b

# ─── Helpers ─────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

info()  { echo -e "${CYAN}==>${NC} $*"; }
ok()    { echo -e "${GREEN}==>${NC} $*"; }
warn()  { echo -e "${YELLOW}WARNING:${NC} $*"; }
err()   { echo -e "${RED}ERROR:${NC} $*" >&2; }

require_pod_id() {
    if [ -z "${RUNPOD_POD_ID}" ]; then
        err "RUNPOD_POD_ID is not set."
        echo "Set it in .env.runpod or export it:"
        echo "  export RUNPOD_POD_ID=abc123xyz"
        exit 1
    fi
}

# Get the SSH connection string for the RunPod pod
pod_ssh() {
    require_pod_id
    # RunPod SSH format: root@<pod-id>-ssh.runpod.io or via runpodctl
    local host="${RUNPOD_SSH_HOST:-${RUNPOD_POD_ID}-ssh.runpod.io}"
    ssh -i "${RUNPOD_SSH_KEY}" \
        -o StrictHostKeyChecking=no \
        -o UserKnownHostsFile=/dev/null \
        -o LogLevel=ERROR \
        -p "${RUNPOD_SSH_PORT}" \
        "root@${host}" \
        "$@"
}

# ─── Commands ────────────────────────────────────────────────────────

cmd_build() {
    info "Building ${FULL_IMAGE}..."
    docker build \
        -f "${PROJECT_DIR}/Dockerfile.runpod" \
        -t "${FULL_IMAGE}" \
        "${PROJECT_DIR}"
    ok "Image built: ${FULL_IMAGE}"
}

cmd_push() {
    info "Pushing ${FULL_IMAGE}..."
    docker push "${FULL_IMAGE}"
    ok "Image pushed: ${FULL_IMAGE}"
}

cmd_switch_model() {
    local new_model="${1:-}"
    if [ -z "${new_model}" ]; then
        echo ""
        echo "Usage: $0 switch-model <model-name>"
        echo ""
        echo "Recommended models (cost savings):"
        echo ""
        echo "  Tiny (2-3GB VRAM, ~\$0.10/hr on RTX 3070):"
        echo "    qwen3:4b        — Best quality at this size"
        echo "    phi4-mini        — Microsoft, strong reasoning"
        echo "    gemma3:4b        — Google, well-rounded"
        echo "    llama3.2:3b      — Meta, fast and capable"
        echo ""
        echo "  Small (5-6GB VRAM, ~\$0.10-0.15/hr on RTX 3070):"
        echo "    qwen3:8b         — Best balance of speed and quality"
        echo ""
        echo "  Medium (8-10GB VRAM, ~\$0.20/hr on RTX A4000):"
        echo "    qwen3:14b        — Current default, excellent quality"
        echo "    gemma3:12b       — Strong alternative"
        echo ""
        echo "  Custom GGUF:"
        echo "    Provide a GGUF path on the pod's network volume:"
        echo "    $0 switch-model my-model --gguf /workspace/models/my-model.gguf"
        echo ""
        exit 1
    fi

    local gguf_path=""
    if [ "${2:-}" = "--gguf" ] && [ -n "${3:-}" ]; then
        gguf_path="${3}"
    fi

    require_pod_id

    info "Switching model to '${new_model}' on pod ${RUNPOD_POD_ID}..."

    if [ -n "${gguf_path}" ]; then
        # Import from GGUF on the pod
        info "Importing from GGUF: ${gguf_path}"
        pod_ssh bash -c "
            echo 'FROM ${gguf_path}' > /tmp/Modelfile.tmp && \
            ollama create '${new_model}' -f /tmp/Modelfile.tmp && \
            rm -f /tmp/Modelfile.tmp
        "
    else
        # Pull from registry
        info "Pulling '${new_model}' from Ollama registry..."
        pod_ssh ollama pull "${new_model}"
    fi

    # Update the OLLAMA_MODEL env var by restarting the model + bot processes
    info "Restarting model API and bot with new model..."
    pod_ssh bash -c "
        export OLLAMA_MODEL='${new_model}'
        supervisorctl stop bot model
        supervisorctl start model
        sleep 3
        supervisorctl start bot
    "

    ok "Switched to '${new_model}'."
    warn "To persist across pod restarts, update OLLAMA_MODEL in your RunPod pod template."
    echo ""
    echo "  OLLAMA_MODEL=${new_model}"
    echo ""
}

cmd_update() {
    info "Full deploy: build -> push -> restart pod"
    cmd_build
    cmd_push

    if [ -n "${RUNPOD_POD_ID}" ]; then
        info "Restarting pod services..."
        pod_ssh bash -c "
            supervisorctl stop all
            supervisorctl start all
        "
        ok "Pod services restarted."
        warn "If the Dockerfile changed significantly, stop and restart the pod from the RunPod console."
    else
        warn "RUNPOD_POD_ID not set — image pushed but pod not restarted."
        echo "Restart the pod manually from the RunPod console."
    fi
}

cmd_ssh() {
    require_pod_id
    info "Connecting to pod ${RUNPOD_POD_ID}..."
    pod_ssh
}

cmd_status() {
    require_pod_id
    info "Checking service status on pod ${RUNPOD_POD_ID}..."
    echo ""
    echo "─── supervisord ─────────────────────────────"
    pod_ssh supervisorctl status
    echo ""
    echo "─── ollama models ──────────────────────────"
    pod_ssh ollama list
    echo ""
    echo "─── health check ────────────────────────────"
    pod_ssh curl -sf http://localhost:8000/health 2>/dev/null || echo "Health check failed"
    echo ""
}

cmd_logs() {
    require_pod_id
    local service="${1:-all}"
    info "Tailing logs from pod (${service})..."
    if [ "${service}" = "all" ]; then
        pod_ssh tail -f /dev/stderr /dev/stdout
    else
        pod_ssh supervisorctl tail -f "${service}"
    fi
}

cmd_models() {
    require_pod_id
    info "Models available on pod ${RUNPOD_POD_ID}:"
    echo ""
    pod_ssh ollama list
}

cmd_help() {
    echo ""
    echo "BratBot RunPod Deployment Script"
    echo ""
    echo "Usage: $0 <command> [args]"
    echo ""
    echo "Commands:"
    echo "  build                        Build the Docker image"
    echo "  push                         Push the image to registry"
    echo "  switch-model <name> [--gguf] Switch the active Ollama model on the pod"
    echo "  update                       Full deploy: build, push, restart"
    echo "  ssh                          SSH into the pod"
    echo "  status                       Check services, models, and health"
    echo "  logs [service]               Tail logs (all, ollama, model, bot)"
    echo "  models                       List Ollama models on the pod"
    echo "  help                         Show this help"
    echo ""
    echo "Configuration (.env.runpod):"
    echo "  RUNPOD_POD_ID=<pod-id>       RunPod pod ID"
    echo "  REGISTRY_IMAGE=ghcr.io/...   Docker image name"
    echo "  IMAGE_TAG=runpod-latest       Image tag"
    echo "  RUNPOD_SSH_KEY=~/.ssh/...     SSH key path"
    echo ""
}

# ─── Main ────────────────────────────────────────────────────────────
case "${1:-help}" in
    build)         cmd_build ;;
    push)          cmd_push ;;
    switch-model)  shift; cmd_switch_model "$@" ;;
    update)        cmd_update ;;
    ssh)           cmd_ssh ;;
    status)        cmd_status ;;
    logs)          shift; cmd_logs "$@" ;;
    models)        cmd_models ;;
    help|--help|-h) cmd_help ;;
    *)
        err "Unknown command: $1"
        cmd_help
        exit 1
        ;;
esac
