import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from unittest.mock import patch
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)


def test_health():
    """GET /health должен возвращать status ok."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["version"] == "1.0.0"


def test_chat_empty_company():
    """POST /chat с пустым company должен возвращать 422."""
    response = client.post("/chat", json={"company": "", "language": "Russian"})
    assert response.status_code == 422


def test_chat_missing_company():
    """POST /chat без поля company должен возвращать 422."""
    response = client.post("/chat", json={"language": "Russian"})
    assert response.status_code == 422


def test_chat_company_too_long():
    """POST /chat с company > 200 символов должен возвращать 422."""
    response = client.post("/chat", json={"company": "a" * 201, "language": "Russian"})
    assert response.status_code == 422


def test_chat_success():
    """POST /chat с валидными данными должен возвращать SSE поток."""
    mock_report = "## SWOT Analysis\n### Strengths\n- Strong product"

    with patch("backend.app.agents.agent.run_agent", return_value=mock_report):
        with client.stream("POST", "/chat", json={"company": "Notion", "language": "Russian"}) as response:
            assert response.status_code == 200
            assert "text/event-stream" in response.headers["content-type"]

            chunks = []
            for line in response.iter_lines():
                if line.startswith("data: "):
                    chunks.append(line)

            assert any('"type": "start"' in c for c in chunks)
            assert any('"type": "done"' in c for c in chunks)


def test_chat_agent_error():
    """POST /chat когда агент падает — должен вернуть SSE с type error."""
    with patch("backend.app.agents.agent.run_agent", side_effect=Exception("LLM unavailable")):
        with client.stream("POST", "/chat", json={"company": "Notion", "language": "Russian"}) as response:
            assert response.status_code == 200

            events = []
            for line in response.iter_lines():
                if line.startswith("data: "):
                    events.append(line)

            assert any('"type": "error"' in e for e in events)


def test_chat_language_passed():
    """POST /chat должен передавать язык агенту."""
    with patch("backend.app.agents.agent.run_agent", return_value="report") as mock_agent:
        with client.stream("POST", "/chat", json={"company": "Linear", "language": "English"}) as response:
            response.read()

        mock_agent.assert_called_once_with("Linear", "English")