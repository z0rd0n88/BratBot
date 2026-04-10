# BratBot — RunPod Deployment Guide

Developer reference for deploying and operating BratBot on RunPod GPU Pods.

---

## Architecture

The pod runs all services in a single stateless container. Redis is hosted externally (Upstash) so the pod can be stopped or replaced without losing state.

```
RunPod GPU Pod (stateless)
├── supervisord
│   ├── ollama serve          (GPU, port 11434)
│   ├── model (uvicorn)       (port 8000)
│   ├── bot (bratbot)         (outbound WebSocket)
│   └── bonniebot             (outbound WebSocket)
└── /workspace (Network Volume)
    ├── models/               ← custom GGUF files (optional)
    └── ollama/               ← Ollama model cache (persistent)

External Services:
└── Upstash Redis (free tier)
```

---

## GPU Recommendations

| GPU | VRAM | ~Cost/hr | ~Cost/mo | Notes |
|---|---|---|---|---|
| RTX 3070 | 8 GB | $0.10 | ~$72 | Good for 4–8B models |
| RTX A4000 | 16 GB | $0.20 | ~$144 | Cheapest viable for 14B Q4_K_M |
| L4 | 24 GB | $0.28 | ~$202 | Good balance of cost and headroom |
| RTX 4090 | 24 GB | $0.44 | ~$317 | Fastest inference |

> **WARNING:** Never stop the RTX 4090 pod unless absolutely necessary — stopping releases the GPU and another user may claim it before you can restart. Prefer off-peak hours (2–6 AM ET, weekends) if a stop/start is unavoidable.

---

## Prerequisites

1. **Upstash Redis** — Create a free account at [upstash.com](https://upstash.com), create a Redis database. Note the `rediss://` connection string (TLS).
2. **RunPod account** with a container registry (GHCR or Docker Hub) for pushing images.
3. **SSH key** registered with RunPod for pod access.

---

## Step 1: Build and push the image

```bash
# One-time config
cp .env.runpod.example .env.runpod
# Edit .env.runpod: REGISTRY_IMAGE, RUNPOD_POD_ID, RUNPOD_SSH_KEY, RUNPOD_SSH_USER

# Build and push
./scripts/deploy-runpod.sh build
./scripts/deploy-runpod.sh push
```

The image is `Dockerfile.runpod` — includes Ollama, supervisord, BratBot, BonnieBot, and the model API all-in-one.

---

## Step 2: Network Volume

1. Create a **Network Volume** (15 GB minimum) in your preferred RunPod region.
2. Attach it at `/workspace` when creating the pod.

```
/workspace/
├── ollama/models/   ← Ollama model cache (auto-populated on first pull)
└── models/          ← Custom GGUF files (optional, manual upload)
```

On first boot the entrypoint pulls the model specified by `OLLAMA_MODEL` (~2–10 min). Subsequent starts load from the volume cache (~30 seconds).

---

## Step 3: Pod Template

Create a Pod Template in the RunPod console:

- **Image:** `ghcr.io/z0rd0n88/bratbot:runpod-latest`
- **GPU:** RTX 3070 for ≤8B models, RTX A4000 for 14B
- **Container Disk:** 5 GB (models live on network volume; image is ~900 MB)
- **Volume:** Attach your network volume at `/workspace`
- **Exposed Ports:** `8000/http` (Discord interactions webhook)

**Environment Variables:**

| Variable | Value |
|---|---|
| `DISCORD_BOT_TOKEN` | BratBot token |
| `DISCORD_CLIENT_ID` | BratBot application ID |
| `DISCORD_PUBLIC_KEY` | BratBot Ed25519 key |
| `BONNIEBOT_DISCORD_BOT_TOKEN` | BonnieBot token |
| `BONNIEBOT_DISCORD_CLIENT_ID` | BonnieBot application ID |
| `BONNIEBOT_DISCORD_PUBLIC_KEY` | BonnieBot Ed25519 key |
| `OLLAMA_BASE_URL` | `http://localhost:11434` |
| `OLLAMA_MODEL` | e.g. `mannix/llama3.1-8b-abliterated:q8_0` |
| `LLM_API_URL` | `http://localhost:8000` |
| `REDIS_URL` | `rediss://default:xxx@xxx.upstash.io:6379` |
| `TERMS_URL` | URL to terms of service page |
| `PRIVACY_URL` | URL to privacy policy page |
| `PROMPTS_ENCRYPTION_KEY` | Base64-url 32-byte SecretBox key (see [Personality Prompts (Encrypted)](#personality-prompts-encrypted) below) |

---

## Step 4: Deploy and verify

```bash
# Check all services are running
./scripts/deploy-runpod.sh status

# SSH in for manual inspection
./scripts/deploy-runpod.sh ssh

# Verify model is loaded and API is healthy
ollama list
curl http://localhost:8000/health
```

---

## Switching models

Switch models on a running pod without rebuilding or stopping the pod:

```bash
# See recommendations
./scripts/deploy-runpod.sh switch-model

# Pull from Ollama registry and activate
./scripts/deploy-runpod.sh switch-model qwen3:8b

# Import a custom GGUF from the network volume
./scripts/deploy-runpod.sh switch-model my-model --gguf /workspace/models/my-model.gguf

# List what's loaded
./scripts/deploy-runpod.sh models
```

> `switch-model` activates immediately but doesn't persist across pod restarts. Update `OLLAMA_MODEL` in your pod template to make it permanent.

---

## Recommended models by cost

| Model | VRAM | Quality | Min GPU | ~Cost/mo |
|---|---|---|---|---|
| `llama3.2:3b` | ~2 GB | Decent | RTX 3070 | ~$72 |
| `qwen3:4b` | ~3 GB | Good | RTX 3070 | ~$72 |
| `phi4-mini` | ~3 GB | Good | RTX 3070 | ~$72 |
| `gemma3:4b` | ~3 GB | Good | RTX 3070 | ~$72 |
| `qwen3:8b` | ~5 GB | Great | RTX 3070 | ~$72 |
| `gemma3:12b` | ~8 GB | Excellent | RTX A4000 | ~$144 |
| `qwen3:14b` | ~9 GB | Excellent | RTX A4000 | ~$144 |

---

## Personality Prompts (Encrypted)

The personality prompts in `model/prompts/*.txt` contain custom voice content the maintainer doesn't want in public git history. They are gitignored. To make them survive a fresh clone or pod rebuild without exposing them, the repo commits **encrypted** `*.txt.enc` files (base64-encoded PyNaCl SecretBox / XSalsa20-Poly1305 ciphertext). The model server decrypts them at startup using `PROMPTS_ENCRYPTION_KEY` from the env.

A `.dockerignore` excludes `model/prompts/*.txt` from the build context so stale local plaintext can never leak into the image — only the `.enc` and `.example` files ship.

### First-time setup

```bash
# 1. Generate a fresh 32-byte SecretBox key
python scripts/encrypt-prompts.py keygen

# 2. Store the printed key in your password manager (LOSING THIS KEY MAKES
#    THE COMMITTED .txt.enc FILES UNRECOVERABLE)

# 3. Add to your local .env
echo 'PROMPTS_ENCRYPTION_KEY=<paste-key-here>' >> .env

# 4. Encrypt your local plaintext prompts
python scripts/encrypt-prompts.py encrypt

# 5. Commit the encrypted blobs
git add model/prompts/*.txt.enc
git commit -m "feat(prompts): seed encrypted personality blobs"
git push

# 6. Add the SAME key to the RunPod pod template env vars (Step 3 above)
```

### Edit workflow

```bash
# Edit the plaintext (gitignored, local only)
$EDITOR model/prompts/bonnie.txt

# Re-encrypt (idempotent — no-op if content unchanged)
python scripts/encrypt-prompts.py encrypt

# Commit and push the updated .enc
git add model/prompts/bonnie.txt.enc
git commit -m "tweak bonnie's voice"
git push
```

To make the change live on the pod without rebuilding the image, hot-fix it (see [Hot-fix new .enc files onto a running pod](#hot-fix-new-enc-files-onto-a-running-pod) below).

### Fresh-clone recovery

```bash
cp .env.example .env
# Paste PROMPTS_ENCRYPTION_KEY from your password manager into .env

# Materialize plaintext .txt files for editing (optional — the model server
# will also decrypt directly from .enc at startup)
python scripts/encrypt-prompts.py decrypt
```

### Hot-fix new .enc files onto a running pod

After pushing updated `.enc` files to GitHub, pull them onto the running pod via curl from `raw.githubusercontent.com` (SCP doesn't work through RunPod's gateway):

```bash
./scripts/deploy-runpod.sh ssh
# Then on the pod:
for f in brat_level3 cami bonnie; do
  curl -fsSL "https://raw.githubusercontent.com/z0rd0n88/BratBot/main/model/prompts/${f}.txt.enc" \
    -o "/model/prompts/${f}.txt.enc"
done
supervisorctl restart model
```

The model server's lifespan hook will load and decrypt all 3 prompts at startup, failing loud if the key is wrong or any `.enc` file is missing.

### First-rollout dance (when adding `PROMPTS_ENCRYPTION_KEY` for the first time)

The very first deployment of `PROMPTS_ENCRYPTION_KEY` to a running pod hits a chicken-and-egg problem: supervisord (PID 1) inherits its environment from the container at container start, so a NEW env var added to the pod template doesn't reach supervisord until the next container start. The `%(ENV_PROMPTS_ENCRYPTION_KEY)s` interpolation in `supervisord.runpod.conf`'s `[program:model]` section won't resolve to anything, and the model service crashes at boot.

Two ways to handle this on the FIRST rollout (subsequent rollouts work via the pod template normally):

**Option A (recommended): one-time hot-edit of `/etc/supervisor/conf.d/supervisord.conf`** — Edit the file ON the running pod (NOT in git) to hardcode the literal key value:

```bash
./scripts/deploy-runpod.sh ssh
# Then on the pod (replace <KEY> with the actual key value):
python3 -c "
p='/etc/supervisor/conf.d/supervisord.conf'
t=open(p).read()
old='directory=/model'
new=old + '\nenvironment=PROMPTS_ENCRYPTION_KEY=\"<KEY>\"'
open(p,'w').write(t.replace(old, new, 1))
print('patched')
"
supervisorctl reread && supervisorctl update model
```

The hot-edit lives only on the running container — next time the container restarts (from the docker image), the pristine `supervisord.runpod.conf` from the image is used and `%(ENV_PROMPTS_ENCRYPTION_KEY)s` resolves correctly because the pod template env var IS now in supervisord's environment by then. The hot-edit self-heals.

**Option B (last resort): stop and start the pod** — Stops the container, container starts again with the new env var inherited from the pod template, supervisord starts with the var in its environment, `%(ENV_...)s` resolves. Releases the GPU though, so use only when Option A isn't available.

### Key rotation

If `PROMPTS_ENCRYPTION_KEY` is compromised:

```bash
# 1. Generate a new key
python scripts/encrypt-prompts.py keygen

# 2. Update local .env with the new key
$EDITOR .env

# 3. Re-encrypt all prompts with the new key (idempotency check ensures
#    every .enc file gets a fresh nonce + new ciphertext under the new key)
python scripts/encrypt-prompts.py encrypt

# 4. Commit and push
git add model/prompts/*.txt.enc
git commit -m "rotate(prompts): new encryption key"
git push

# 5. Update RunPod pod template env var with the new key
# 6. Update password manager with the new key
# 7. Hot-fix the running pod with new .enc files (see above)
# 8. Restart the model service so it picks up the new key:
#    - If using Option A: re-run the hot-edit with the NEW key value
#    - If using Option B: stop/start the pod
```

The old key value is no longer usable to decrypt anything in git — the next container start with the new pod template value picks up the new key cleanly.

### Optional: drift-check pre-commit hook

To prevent accidentally committing a stale `.txt.enc` after editing the plaintext:

```bash
cp scripts/pre-commit-encrypt-check.sh .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

The hook calls `scripts/encrypt-prompts.py verify` on every staged `.txt.enc` and aborts the commit if it doesn't decrypt to match the working-copy `.txt`. The same drift check also runs in `./scripts/deploy-runpod.sh build`.

---

## Updating code

### Code-only changes (no new dependencies)

SCP is not supported through RunPod's SSH gateway. Instead, commit and push, then pull files onto the pod via `curl`:

```bash
# 1. Push changes to GitHub
git push origin main

# 2. SSH into the pod
./scripts/deploy-runpod.sh ssh

# 3. Pull updated files
curl -fsSL "https://raw.githubusercontent.com/z0rd0n88/BratBot/main/model/app.py" -o /model/app.py
curl -fsSL "https://raw.githubusercontent.com/z0rd0n88/BratBot/main/src/bratbot/commands/bratchat.py" -o /app/src/bratbot/commands/bratchat.py
# ... repeat for each changed file

# 4. Restart affected services (Ollama stays up)
supervisorctl restart model bot bonniebot
```

Or in one SSH command:

```bash
printf 'curl -fsSL "https://raw.githubusercontent.com/z0rd0n88/BratBot/main/model/app.py" -o /model/app.py && supervisorctl restart model bot bonniebot && supervisorctl status 2>&1\nexit\n' | \
  MSYS_NO_PATHCONV=1 /c/Windows/System32/OpenSSH/ssh.exe -tt \
  -i "C:\Users\sneak\.ssh\id_ed25519" \
  -o StrictHostKeyChecking=no -o UserKnownHostsFile=NUL -o LogLevel=ERROR \
  -p 22 "$RUNPOD_SSH_USER@ssh.runpod.io" 2>&1
```

### Dependency changes (`pyproject.toml` or `model/requirements.txt` changed)

Hotfix the running pod directly (avoids stopping the pod and losing the GPU):

```bash
# SSH in and install missing package
./scripts/deploy-runpod.sh ssh
pip install <package>
supervisorctl restart <service>
```

### Full image rebuild (Dockerfile or base image changes)

**Last resort only** — requires stopping the pod, which releases the GPU.

```bash
./scripts/deploy-runpod.sh build
./scripts/deploy-runpod.sh push
# Then stop and start the pod from the RunPod console
```

Prefer off-peak hours (2–6 AM ET, weekends) to minimize the risk of losing the GPU allocation.

---

## Checking what's deployed

The pod has no git. To verify which code is running:

```bash
# Interactive shell
./scripts/deploy-runpod.sh ssh

# Read a specific file
printf 'cat /app/src/bratbot/commands/bratchat.py 2>&1\nexit\n' | \
  MSYS_NO_PATHCONV=1 /c/Windows/System32/OpenSSH/ssh.exe -tt \
  -i "C:\Users\sneak\.ssh\id_ed25519" \
  -o StrictHostKeyChecking=no -o UserKnownHostsFile=NUL -o LogLevel=ERROR \
  -p 22 "$RUNPOD_SSH_USER@ssh.runpod.io" 2>&1

# Grep for a signature line to confirm a specific change is live
printf 'grep -n "verbosity" /model/app.py | head -5 2>&1\nexit\n' | ...
```

On Windows, `./scripts/deploy-runpod.sh ssh` routes through `C:\Windows\System32\OpenSSH\ssh.exe` automatically via `runpod-ssh-wrapper.py`.

---

## Deploy script reference

```bash
./scripts/deploy-runpod.sh build           # Build Docker image
./scripts/deploy-runpod.sh push            # Push to registry
./scripts/deploy-runpod.sh update          # Build + push + supervisorctl restart
./scripts/deploy-runpod.sh switch-model    # Change active Ollama model
./scripts/deploy-runpod.sh status          # Check services + health
./scripts/deploy-runpod.sh ssh             # SSH into the pod
./scripts/deploy-runpod.sh logs [service]  # Tail logs
./scripts/deploy-runpod.sh models          # List loaded models
```

---

## SSH details (Windows)

`.env.runpod` connection fields:

| Field | Example |
|---|---|
| `RUNPOD_SSH_USER` | `e0h517h6y7ziv8-644116d0` (includes session token — expires on pod stop/restart) |
| `RUNPOD_SSH_KEY` | `/c/Users/sneak/.ssh/id_ed25519` (Git Bash format; wrapper converts to Windows) |
| `RUNPOD_SSH_HOST` | `ssh.runpod.io` |
| `RUNPOD_SSH_PORT` | `22` |

After a pod stop/start, get the new `RUNPOD_SSH_USER` from the RunPod console and update `.env.runpod`.

---

## Troubleshooting

**`deploy-runpod.sh hot-update` fails with "subsystem request failed"**
RunPod's SSH gateway doesn't support SCP. Use the GitHub raw URL method above instead.

**`python3` not found when running deploy script locally (Windows)**
The deploy script calls `python3` but Windows Git Bash may only have `python`. Use `runpod-ssh-wrapper.py` directly: `/c/Python314/python scripts/runpod-ssh-wrapper.py ...`

**Models not persisting after pod restart**
Verify the network volume is mounted: `df /workspace`. If empty, the volume wasn't attached — recreate the pod with the volume properly configured. Model cache should be at `/workspace/ollama/models/`.

**SSH session token expired**
`RUNPOD_SSH_USER` embeds a token that becomes stale after pod stop/restart. Get the new connection string from the RunPod console and update `.env.runpod`.

**Services fail to start after code hotfix**
If the new code reads an env var not set on the pod, add it to the relevant `[program:]` section's `environment=` line in supervisord, then `supervisorctl reread && supervisorctl update <service>`.

**"Connection refused" or SSH hangs**
Verify the pod is running in the RunPod console. If the pod is running but SSH times out, the SSH service may still be starting — wait 30 seconds and retry.
