from fastapi.testclient import TestClient

from backend.main import app


client = TestClient(app)


def test_health_reports_registered_tools():
    response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["mode"] in {"mock", "llm"}


def test_equipment_query_returns_demo_data():
    response = client.post("/api/chat", json={"message": "现在有哪些设备告警？"})

    assert response.status_code == 200
    body = response.json()
    assert body["response"]
    assert "get_alarm_equipment" in {item["tool_name"] for item in body["tool_calls"]}
    assert "CNC-001" in body["response"]


def test_sop_query_works_without_vector_model():
    response = client.post("/api/chat", json={"message": "怎么换模？"})

    assert response.status_code == 200
    body = response.json()
    assert "search_sop" in {item["tool_name"] for item in body["tool_calls"]}
    assert "SOP" in body["response"]


def test_work_order_draft_is_read_only_and_requires_confirmation():
    response = client.post("/api/chat", json={"message": "帮我创建一个工单"})

    assert response.status_code == 200
    body = response.json()
    assert body["pending_confirmation"]["tool"] == "create_work_order_draft"
    assert "草稿" in body["response"]


def test_empty_message_is_rejected():
    response = client.post("/api/chat", json={"message": "   "})

    assert response.status_code == 400
