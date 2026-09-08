"""Download the configured Qwen GGUF when needed and start a local server."""

import argparse
import os
from pathlib import Path
import shutil
import subprocess

from huggingface_hub import hf_hub_download
from huggingface_hub.errors import LocalEntryNotFoundError

ROOT = Path(__file__).resolve().parent.parent
MODEL_REPO = "unsloth/Qwen3.5-2B-GGUF"
MODEL_FILE = "Qwen3.5-2B-UD-IQ2_XXS.gguf"
MODEL_REVISION = "f6d5376be1edb4d416d56da11e5397a961aca8ae"


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
        print(f"Downloading {kwargs['filename']} from Hugging Face; this may take several minutes.", flush=True)
        path = hf_hub_download(**kwargs)
    path = Path(path)
    with path.open("rb") as handle:
        if handle.read(4) != b"GGUF":
            raise RuntimeError("Cached model is not a GGUF file. Remove the corrupt model cache and retry.")
    return path


def server_command(model_path: Path, port: int, context_size: int) -> list[str]:
    binary = os.getenv("LLAMA_SERVER", "llama-server")
    executable = shutil.which(binary)
    if not executable:
        raise RuntimeError(
            "llama-server was not found. Install llama.cpp (see README), "
            "or set LLAMA_SERVER to the full executable path. Qwen weights remain cached."
        )
    return [executable, "--model", str(model_path), "--alias",
            os.getenv("QWEN_MODEL_ALIAS", "qwen-cleaner"), "--host", "127.0.0.1",
            "--port", str(port), "--ctx-size", str(context_size), "--parallel", "1",
            "--jinja", "--chat-template-kwargs", '{"enable_thinking":false}']


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download-only", action="store_true")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--context-size", type=int, default=16384)
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535 or args.context_size < 1024:
        parser.error("Choose a valid port and a context size of at least 1024")
    try:
        model = ensure_model(offline=args.offline)
        print(f"Qwen model ready: {model}", flush=True)
        if args.download_only:
            return 0
        command = server_command(model, args.port, args.context_size)
        print(f"Starting Qwen at http://127.0.0.1:{args.port}. Keep this terminal open.", flush=True)
        return subprocess.call(command)
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        print(f"Startup failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
