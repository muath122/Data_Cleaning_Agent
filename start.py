"""Cross-platform bootstrap: uv environment, requirements, Qwen cache, llama.cpp."""

from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent


def main() -> int:
    uv = shutil.which("uv")
    if not uv:
        print("Install uv first: https://docs.astral.sh/uv/getting-started/installation/")
        return 1
    python = ROOT / ".venv" / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    try:
        if not python.exists():
            subprocess.run([uv, "venv", "--python", "3.11", str(ROOT / ".venv")], check=True, cwd=ROOT)
        subprocess.run([uv, "pip", "install", "--python", str(python), "-r",
                        str(ROOT / "requirements.txt")], check=True, cwd=ROOT)
        return subprocess.call([str(python), "-m", "data_cleaning_agent.runtime", *sys.argv[1:]], cwd=ROOT)
    except subprocess.CalledProcessError as exc:
        return exc.returncode
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
