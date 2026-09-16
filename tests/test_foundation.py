import json
from pathlib import Path

import httpx
import pytest
from huggingface_hub.errors import LocalEntryNotFoundError

from data_cleaning_agent import runtime
from data_cleaning_agent.contracts import SchemaReport
from data_cleaning_agent.model import LocalModel, ModelError, load_prompt


def test_cached_model_does_not_download(tmp_path, monkeypatch):
    path = tmp_path / "qwen.gguf"
    path.write_bytes(b"GGUFtest")
    calls = []

    def download(**kwargs):
        calls.append(kwargs)
        return str(path)

    monkeypatch.setattr(runtime, "hf_hub_download", download)
    assert runtime.ensure_model() == path
    assert len(calls) == 1 and calls[0]["local_files_only"] is True


def test_missing_model_downloads_once(tmp_path, monkeypatch):
    path = tmp_path / "qwen.gguf"
    path.write_bytes(b"GGUFtest")
    calls = []

    def download(**kwargs):
        calls.append(kwargs)
        if kwargs.get("local_files_only"):
            raise LocalEntryNotFoundError("missing")
        return str(path)

    monkeypatch.setattr(runtime, "hf_hub_download", download)
    assert runtime.ensure_model() == path
    assert len(calls) == 2
    with pytest.raises(RuntimeError, match="not cached"):
        runtime.ensure_model(offline=True)
    assert len(calls) == 3  # Offline path makes only the local lookup.


def test_corrupt_model_and_missing_runtime(tmp_path, monkeypatch):
    path = tmp_path / "qwen.gguf"
    path.write_text("interrupted")
    monkeypatch.setattr(runtime, "hf_hub_download", lambda **kwargs: str(path))
    with pytest.raises(RuntimeError, match="not a GGUF"):
        runtime.ensure_model()
    monkeypatch.setattr(runtime.shutil, "which", lambda binary: None)
    with pytest.raises(RuntimeError, match="llama-server"):
        runtime.server_command(path, 8080, 16384)


def test_local_runtime_command(monkeypatch):
    monkeypatch.setattr(runtime.shutil, "which", lambda binary: "/bin/llama-server")
    cmd = runtime.server_command(Path("model with spaces.gguf"), 8081, 16384)
    assert cmd[cmd.index("--host") + 1] == "127.0.0.1"
    assert cmd[cmd.index("--model") + 1] == "model with spaces.gguf"
    assert int(cmd[cmd.index("--threads") + 1]) >= 1
    assert cmd[cmd.index("--batch-size") + 1] == "512"


def test_client_validates_structured_response():
    calls = 0

    def handler(request):
        nonlocal calls
        calls += 1
        body = json.loads(request.content)
        assert body["response_format"]["schema"]["properties"]["columns"]
        assert body["chat_template_kwargs"] == {"enable_thinking": False}
        return httpx.Response(
            200,
            json={"choices": [{"finish_reason": "stop", "message": {"content": '{"columns":[]}'}}]},
        )

    client = LocalModel(transport=httpx.MockTransport(handler))
    result = client.analyze("schema", [], SchemaReport)
    cached = client.analyze("schema", [], SchemaReport)
    assert result.columns == []
    assert cached.columns == [] and calls == 1
    assert client.metrics == {
        "requests": 1,
        "cache_hits": 1,
        "request_seconds": pytest.approx(0, abs=1),
    }


@pytest.mark.parametrize(
    "content,finish",
    [("not JSON", "stop"), ('{"columns":[]}', "length"), ('{"columns":[],"extra":1}', "stop")],
)
def test_client_rejects_bad_output(content, finish):
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200, json={"choices": [{"finish_reason": finish, "message": {"content": content}}]}
        )
    )
    with pytest.raises(ModelError):
        LocalModel(transport=transport).analyze("schema", [], SchemaReport)


def test_client_reports_unavailable_server():
    def fail(request):
        raise httpx.ConnectError("unavailable")

    with pytest.raises(ModelError, match="Local Qwen request failed"):
        LocalModel(transport=httpx.MockTransport(fail)).analyze("schema", [], SchemaReport)


def test_no_external_model_endpoint():
    with pytest.raises(ValueError, match="local HTTP"):
        LocalModel("https://example.com")


@pytest.mark.parametrize(
    "role", ["schema", "structured", "categories", "text", "validation", "adaptive"]
)
def test_prompt_exists(role):
    assert load_prompt(role).startswith("#")
