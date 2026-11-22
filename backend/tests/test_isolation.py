from __future__ import annotations

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient
from app.main import app, db, init_db

client = TestClient(app)

def test_database_tables():
    print("Testing SQLite schema...")
    conn = db()
    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    assert "chat_threads" in tables, "chat_threads table missing"
    assert "chat_messages" in tables, "chat_messages table missing"

    threads = [r["module_id"] for r in conn.execute("SELECT module_id FROM chat_threads").fetchall()]
    for expected in ["overview", "assistant", "budget", "assignments", "events", "recovery", "behaviour"]:
        assert expected in threads, f"Thread for {expected} not pre-seeded"
    print("✓ Schema and thread seeding verified including 'assistant'.")

def test_restful_module_thread_endpoints():
    print("Testing /api/modules/{apiId}/threads/main routes...")
    # Reset assistant and budget
    client.delete("/api/modules/assistant/threads/main")
    client.delete("/api/modules/budget/threads/main")

    # Send turn to assistant
    res1 = client.post("/api/modules/assistant/threads/main/chat", json={"message": "Hello assistant"})
    assert res1.status_code == 200, res1.text
    data1 = res1.json()
    assert "reply" in data1
    assert data1["role"] == "assistant"

    # Send turn to budget
    res2 = client.post("/api/modules/budget/threads/main/chat", json={"message": "Audit my monthly budget"})
    assert res2.status_code == 200, res2.text
    data2 = res2.json()
    assert "reply" in data2

    # Verify assistant messages
    m1 = client.get("/api/modules/assistant/threads/main/messages").json()["messages"]
    assert len(m1) >= 2
    for m in m1:
        assert m["module_id"] == "assistant"

    # Verify budget messages
    m2 = client.get("/api/modules/budget/threads/main/messages").json()["messages"]
    assert len(m2) >= 2
    for m in m2:
        assert m["module_id"] == "budget"

    # Reset assistant thread
    del_res = client.delete("/api/modules/assistant/threads/main")
    assert del_res.status_code == 200

    # Assistant should now be empty
    m1_after = client.get("/api/modules/assistant/threads/main/messages").json()["messages"]
    assert len(m1_after) == 0

    # Budget must remain untouched
    m2_after = client.get("/api/modules/budget/threads/main/messages").json()["messages"]
    assert len(m2_after) == len(m2)
    print("✓ /api/modules routes and assistant isolation verified.")

if __name__ == "__main__":
    init_db()
    test_database_tables()
    test_restful_module_thread_endpoints()
    print("\nALL TESTS PASSED!")
