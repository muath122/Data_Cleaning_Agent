#!/usr/bin/env bash
#SBATCH --job-name=data-cleaner
#SBATCH --account=pi-albarass
#SBATCH --partition=debug
#SBATCH --gres=gpu:v100:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=02:00:00
#SBATCH --output=slurm-%j.out

set -euo pipefail
cd "${SLURM_SUBMIT_DIR:?Submit this script with sbatch from the repository root}"

if [[ ! -x .venv/bin/python ]]; then
  uv venv --python 3.11 .venv
fi
uv pip install --python .venv/bin/python -r requirements.txt

LLAMA_ROOT="$PWD/tools/llama.cpp"
CUDA_ROOT="/sw/rl9g/cuda/12.4.1/rl9_binary"
export PATH="$CUDA_ROOT/bin:$PATH"
export LD_LIBRARY_PATH="$CUDA_ROOT/lib64:${LD_LIBRARY_PATH:-}"
if [[ ! -x "$LLAMA_ROOT/build/bin/llama-server" ]]; then
  mkdir -p "$PWD/tools"
  if [[ ! -d "$LLAMA_ROOT/.git" ]]; then
    git clone --depth 1 https://github.com/ggml-org/llama.cpp.git "$LLAMA_ROOT"
  fi
  cmake -S "$LLAMA_ROOT" -B "$LLAMA_ROOT/build" -DGGML_CUDA=ON \
    -DCUDAToolkit_ROOT="$CUDA_ROOT" -DCMAKE_BUILD_TYPE=Release
  cmake --build "$LLAMA_ROOT/build" --config Release --target llama-server -j "${SLURM_CPUS_PER_TASK:-8}"
fi

export LLAMA_SERVER="$LLAMA_ROOT/build/bin/llama-server"
export QWEN_GPU_LAYERS=999
RUN_ID="${SLURM_JOB_ID:-manual}"
uv run --no-project python -m data_cleaning_agent.hpc --input data --output-dir "outputs/run-$RUN_ID"
