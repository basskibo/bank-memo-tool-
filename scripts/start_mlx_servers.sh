#!/usr/bin/env bash
# Manual dual-resident mode. The app default (POC_MLX_AUTOSWAP=1) starts/stops
# 14B and VL itself — you usually do not need this script.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PY="${ROOT}/.venv/bin/python"

echo "mlx_lm 14B → http://127.0.0.1:8080"
"$PY" -m mlx_lm server \
  --model mlx-community/Qwen2.5-14B-Instruct-4bit \
  --port 8080 &

echo "mlx_vlm 7B → http://127.0.0.1:8081"
"$PY" -m mlx_vlm server \
  --model mlx-community/Qwen2.5-VL-7B-Instruct-4bit \
  --port 8081 \
  --host 127.0.0.1 &

wait
