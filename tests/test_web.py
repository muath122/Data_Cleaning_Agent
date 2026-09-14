from fastapi.testclient import TestClient

from data_cleaning_agent import web


class IdleThread:
    def __init__(self, **_kwargs):
        pass

    def start(self):
        pass


def test_gui_loads():
    response = TestClient(web.app).get("/")
    assert response.status_code == 200
    assert "Sift" in response.text


def test_upload_queues_supported_table(tmp_path, monkeypatch):
    monkeypatch.setattr(web, "OUTPUTS", tmp_path)
    monkeypatch.setattr(web.threading, "Thread", IdleThread)
    response = TestClient(web.app).post(
        "/api/runs", files=[("files", ("sample.csv", b"Name,Email\nA,a@example.com\n", "text/csv"))]
    )
    assert response.status_code == 200
    run_id = response.json()["id"]
    status = TestClient(web.app).get(f"/api/runs/{run_id}").json()
    assert status["status"] == "queued"
    assert status["file_count"] == 1


def test_upload_rejects_unsupported_file(tmp_path, monkeypatch):
    monkeypatch.setattr(web, "OUTPUTS", tmp_path)
    response = TestClient(web.app).post(
        "/api/runs", files=[("files", ("notes.txt", b"private", "text/plain"))]
    )
    assert response.status_code == 400
    assert not list(tmp_path.iterdir())
