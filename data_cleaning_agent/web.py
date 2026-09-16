"""Local-only web interface for uploading, cleaning, reviewing, and downloading tables."""

import json
import threading
import uuid
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .pipeline import run_pipeline

ROOT = Path(__file__).resolve().parent.parent
GUI = ROOT / "gui"
OUTPUTS = ROOT / "outputs"
MAX_UPLOAD = 100 * 1024 * 1024
RUNS: dict[str, dict] = {}
LOCK = threading.Lock()
PROCESS_LOCK = threading.Lock()

app = FastAPI(title="Sift Data Cleaner", docs_url=None, redoc_url=None)
app.mount("/assets", StaticFiles(directory=GUI / "assets"), name="assets")


@app.get("/")
def index():
    return FileResponse(GUI / "index.html")


def _update(run_id: str, **values):
    with LOCK:
        RUNS[run_id].update(values)


def _work(run_id: str, input_dir: Path, output_dir: Path):
    def progress(event):
        total = max(event.get("total_tables", 1), 1)
        stage_order = {
            "reading": 0,
            "schema": 1,
            "adaptive": 2,
            "structured": 3,
            "categories": 4,
            "text": 5,
            "validation": 6,
            "complete": 7,
        }
        fraction = stage_order.get(event.get("stage"), 0) / 7
        percent = min(99, round(100 * (event.get("table_index", 0) + fraction) / total))
        _update(run_id, status="running", progress=percent, **event)

    try:
        with PROCESS_LOCK:
            summary = run_pipeline(input_dir, output_dir, progress=progress)
        _update(run_id, status="complete", progress=100, stage="complete", summary=summary)
    except Exception as exc:
        _update(
            run_id,
            status="failed",
            error=type(exc).__name__,
            message="The run stopped. Check the terminal for details, then try again.",
        )


@app.post("/api/runs")
async def create_run(files: list[UploadFile] = File(...)):
    if not files or len(files) > 20:
        raise HTTPException(400, "Choose between 1 and 20 CSV/XLSX files")
    invalid = [
        Path(upload.filename or "upload").name
        for upload in files
        if Path(upload.filename or "upload").suffix.lower() not in {".csv", ".xlsx"}
    ]
    if invalid:
        raise HTTPException(400, "Only CSV and XLSX files are supported")
    run_id = uuid.uuid4().hex[:12]
    run_root = OUTPUTS / f"gui-{run_id}"
    input_dir, output_dir = run_root / "input", run_root / "results"
    input_dir.mkdir(parents=True)
    names = set()
    for upload in files:
        name = Path(upload.filename or "upload").name
        if name in names:
            name = f"{Path(name).stem}-{len(names) + 1}{Path(name).suffix}"
        names.add(name)
        target = input_dir / name
        size = 0
        with target.open("wb") as handle:
            while chunk := await upload.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_UPLOAD:
                    target.unlink(missing_ok=True)
                    raise HTTPException(413, f"{name} exceeds 100 MB")
                handle.write(chunk)
    with LOCK:
        RUNS[run_id] = {
            "id": run_id,
            "status": "queued",
            "progress": 0,
            "stage": "queued",
            "file_count": len(names),
            "output_dir": str(output_dir),
        }
    threading.Thread(target=_work, args=(run_id, input_dir, output_dir), daemon=True).start()
    return {"id": run_id, "status_url": f"/api/runs/{run_id}"}


@app.get("/api/runs/{run_id}")
def run_status(run_id: str):
    with LOCK:
        run = RUNS.get(run_id)
        if not run:
            raise HTTPException(404, "Run not found")
        return {key: value for key, value in run.items() if key != "output_dir"}


@app.get("/api/runs/{run_id}/results")
def run_results(run_id: str):
    with LOCK:
        run = RUNS.get(run_id)
        if not run or run["status"] != "complete":
            raise HTTPException(404, "Completed run not found")
        output = Path(run["output_dir"])
        summary = run["summary"]
    tables = []
    for item in summary["tables"]:
        if "output" not in item:
            continue
        csv_path = output / item["output"]
        preview = pd.read_csv(csv_path, dtype=str, keep_default_na=False, nrows=6)
        report_path = output / item["output"].replace(".cleaned.csv", ".report.json")
        report = json.loads(report_path.read_text(encoding="utf-8"))
        changes = []
        for stage in report["stages"]:
            for change in stage["changes"][:12]:
                changes.append({"stage": stage["stage"], **change})
        tables.append(
            {
                **item,
                "columns_preview": list(preview.columns)[:8],
                "rows_preview": preview.iloc[:, :8].to_dict(orient="records"),
                "changes_preview": changes[:20],
                "download": f"/api/runs/{run_id}/files/{item['output']}",
            }
        )
    return {"summary": summary, "tables": tables}


@app.get("/api/runs/{run_id}/files/{filename}")
def download_result(run_id: str, filename: str):
    with LOCK:
        run = RUNS.get(run_id)
        if not run or run["status"] != "complete":
            raise HTTPException(404, "Completed run not found")
        output = Path(run["output_dir"])
    safe = Path(filename).name
    if safe != filename or not safe.endswith((".csv", ".json")):
        raise HTTPException(400, "Invalid result name")
    path = output / safe
    if not path.is_file():
        raise HTTPException(404, "Result not found")
    return FileResponse(path, filename=safe)
