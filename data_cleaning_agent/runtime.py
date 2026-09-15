"""Download the configured Qwen GGUF when needed and start a local server."""

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import httpx
from huggingface_hub import hf_hub_download
from huggingface_hub.errors import LocalEntryNotFoundError

ROOT = Path(__file__).resolve().parent.parent
MODEL_REPO = "unsloth/Qwen3.5-2B-GGUF"
MODEL_FILE = "Qwen3.5-2B-Q4_K_M.gguf"
MODEL_REVISION = "71370273a6eb90707b83b71a09d64fb99c288639"


def ensure_model(*, offline=False) -> Path:
    """Use the pinned cache first; the Hub handles interrupted/atomic downloads."""
    kwargs = {
        "repo_id": os.getenv("QWEN_MODEL_REPO", MODEL_REPO),
        "filename": os.getenv("QWEN_MODEL_FILE", MODEL_FILE),
        "revision": os.getenv("QWEN_MODEL_REVISION", MODEL_REVISION),
        "cache_dir": str(ROOT / "models" / "hub"),
    }
    try:
        path = hf_hub_download(**kwargs, local_files_only=True)
    except LocalEntryNotFoundError:
        if offline:
            raise RuntimeError("Qwen is not cached. Run startup once without --offline.") from None
        print(
            f"Downloading {kwargs['filename']} from Hugging Face; this may take several minutes.",
            flush=True,
        )
        path = hf_hub_download(**kwargs)
    path = Path(path)
    with path.open("rb") as handle:
        if handle.read(4) != b"GGUF":
            raise RuntimeError(
                "Cached model is not a GGUF file. Remove the corrupt model cache and retry."
            )
    return path


def server_command(model_path: Path, port: int, context_size: int) -> list[str]:
    binary = os.getenv("LLAMA_SERVER", "llama-server")
    executable = shutil.which(binary)
    if not executable:
        raise RuntimeError(
            "llama-server was not found. Install llama.cpp (see README), "
            "or set LLAMA_SERVER to the full executable path. Qwen weights remain cached."
        )
    return [
        executable,
        "--model",
        str(model_path),
        "--alias",
        os.getenv("QWEN_MODEL_ALIAS", "qwen-cleaner"),
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--ctx-size",
        str(context_size),
        "--parallel",
        "1",
        "--n-gpu-layers",
        os.getenv("QWEN_GPU_LAYERS", "999"),
        "--jinja",
        "--chat-template-kwargs",
        '{"enable_thinking":false}',
    ]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download-only", action="store_true")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--context-size", type=int, default=16384)
    parser.add_argument("--gui-port", type=int, default=7860)
    parser.add_argument("--no-gui", action="store_true", help="Start only the model API")
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535 or not 1 <= args.gui_port <= 65535 or args.context_size < 1024:
        parser.error("Choose a valid port and a context size of at least 1024")
    try:
        model = ensure_model(offline=args.offline)
        print(f"Qwen model ready: {model}", flush=True)
        if args.download_only:
            return 0
        command = server_command(model, args.port, args.context_size)
        print(f"Starting Qwen at http://127.0.0.1:{args.port}.", flush=True)
        if args.no_gui:
            return subprocess.call(command)
        model_process = subprocess.Popen(command)
        gui_process = None
        try:
            for _ in range(120):
                if model_process.poll() is not None:
                    raise RuntimeError("llama-server exited before becoming ready")
                try:
                    response = httpx.get(
                        f"http://127.0.0.1:{args.port}/health", timeout=2, trust_env=False
                    )
                    if response.status_code == 200:
                        break
                except httpx.HTTPError:
                    pass
                time.sleep(1)
            else:
                raise RuntimeError("llama-server did not become ready within 120 seconds")
            gui_process = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "data_cleaning_agent.web:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(args.gui_port),
                ],
                cwd=ROOT,
            )
            print("\nData Cleaner is ready", flush=True)
            print(f"Open http://127.0.0.1:{args.gui_port} in your browser.", flush=True)
            print("Keep this terminal open while using the app.\n", flush=True)
            return gui_process.wait()
        finally:
            if gui_process and gui_process.poll() is None:
                gui_process.terminate()
            if model_process.poll() is None:
                model_process.terminate()
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        print(f"Startup failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
