"""Start Qwen inside a GPU allocation, run the pipeline, then stop the server."""

import argparse
import os
import subprocess
import time
from pathlib import Path

import httpx

from .pipeline import run_pipeline
from .runtime import ensure_model, server_command


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("data"))
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args(argv)
    if not os.getenv("CUDA_VISIBLE_DEVICES"):
        parser.error("Run this command inside a Slurm GPU allocation")
    model = ensure_model()
    process = subprocess.Popen(server_command(model, args.port, 16384))
    try:
        url = f"http://127.0.0.1:{args.port}"
        for _ in range(120):
            if process.poll() is not None:
                raise RuntimeError("llama-server exited before becoming ready")
            try:
                if httpx.get(f"{url}/health", timeout=2, trust_env=False).status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            time.sleep(1)
        else:
            raise RuntimeError("llama-server did not become ready within 120 seconds")
        os.environ["QWEN_BASE_URL"] = url
        summary = run_pipeline(args.input, args.output_dir)
        return 0 if summary["failed_tables"] == 0 else 2
    finally:
        process.terminate()
        try:
            process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            process.kill()


if __name__ == "__main__":
    raise SystemExit(main())
