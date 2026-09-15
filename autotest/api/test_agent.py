"""测试助手 Agent 接口：SSE 对话流、历史持久化与清空、项目隔离。

服务端处于 mock 模式，对话走固定剧本（检索知识库 + 统计用例数），结果确定。
"""

import json

import pytest


def _chat_events(client, project_id: int, question: str) -> list[dict]:
    """调用对话接口并解析 SSE 事件流。"""
    resp = client.request(
        "POST",
        f"/projects/{project_id}/agent/chat",
        json={"question": question},
        stream=True,
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    events = []
    for line in resp.iter_lines(decode_unicode=True):
        if line and line.startswith("data:"):
            events.append(json.loads(line[5:]))
    return events


@pytest.mark.smoke
def test_chat_stream_event_sequence(client, project):
    events = _chat_events(client, project["id"], "这个项目的通过率怎么样？")

    types = [e["type"] for e in events]
    # 服务端先持久化用户消息（user_message），再进入工具循环
    assert types[0] == "user_message"
    assert "tool_start" in types
    assert events[types.index("tool_start")]["name"] == "search_knowledge"
    assert "tool_end" in types
    assert "token" in types
    assert types[-1] == "done"

    done = events[-1]
    assert "Mock 模式" in done["content"]
    assert done["tool_calls"] == [{"name": "search_knowledge"}]


def test_chat_persists_history(client, project):
    _chat_events(client, project["id"], "第一个问题")

    rows = client.get(f"/projects/{project['id']}/agent/messages").json()
    assert len(rows) == 2
    assert rows[0]["role"] == "user"
    assert rows[0]["content"] == "第一个问题"
    assert rows[1]["role"] == "assistant"
    assert "Mock 模式" in rows[1]["content"]
    assert rows[1]["tool_calls"] == [{"name": "search_knowledge"}]


def test_history_empty_initially(client, project):
    rows = client.get(f"/projects/{project['id']}/agent/messages").json()
    assert rows == []


def test_clear_messages(client, project):
    _chat_events(client, project["id"], "先聊一句")
    resp = client.delete(f"/projects/{project['id']}/agent/messages")
    assert resp.status_code == 204
    assert client.get(f"/projects/{project['id']}/agent/messages").json() == []


def test_history_isolated_between_projects(client, project):
    other = client.create_project("AT-agent-隔离", "隔离验证")
    try:
        _chat_events(client, project["id"], "只属于项目A的问题")
        assert client.get(f"/projects/{other['id']}/agent/messages").json() == []
    finally:
        client.delete_project(other["id"])


def test_chat_nonexistent_project_404(client):
    resp = client.post("/projects/9999999/agent/chat", json={"question": "在吗"})
    assert resp.status_code == 404


def test_chat_empty_question_rejected(client, project):
    resp = client.post(f"/projects/{project['id']}/agent/chat", json={"question": ""})
    assert resp.status_code == 422


def test_chat_with_design_attachment_parses_without_auto_merge(client, project, confirmed_doc):
    """有截图附件时 Mock 走解析剧本，返回 pending_insight_ids，且不自动合并功能点。"""
    png_bytes = b"\x89PNG\r\n\x1a\nmock-design-image"
    upload = client.post(
        f"/projects/{project['id']}/designs/upload",
        data={"document_id": confirmed_doc["id"]},
        files={"file": ("design.png", png_bytes, "image/png")},
    )
    assert upload.status_code == 201, upload.text
    asset = upload.json()

    before_count = len(confirmed_doc.get("items") or [])
    resp = client.request(
        "POST",
        f"/projects/{project['id']}/agent/chat",
        json={
            "question": "",
            "document_id": confirmed_doc["id"],
            "asset_ids": [asset["id"]],
            "attachments": [{
                "asset_id": asset["id"],
                "asset_type": "image",
                "title": asset["title"],
                "filename": asset["filename"],
            }],
        },
        stream=True,
    )
    assert resp.status_code == 200
    events = []
    for line in resp.iter_lines(decode_unicode=True):
        if line and line.startswith("data:"):
            events.append(json.loads(line[5:]))
    done = events[-1]
    assert done["type"] == "done"
    assert done["tool_calls"] == [{"name": "parse_design_asset"}]
    assert done.get("pending_insight_ids")
    assert "确认" in done["content"]

    docs = client.get(f"/projects/{project['id']}/requirements").json()
    doc = next(d for d in docs if d["id"] == confirmed_doc["id"])
    design_items = [i for i in doc["items"] if i.get("source_type") == "design"]
    assert not design_items
    assert len(doc["items"]) == before_count

    rows = client.get(f"/projects/{project['id']}/agent/messages").json()
    assert rows[-1]["pending_insight_ids"]
    assert rows[0]["attachments"]


def test_mock_answer_uses_knowledge(client, project):
    """有知识库时，Mock 回答应命中并引用最相关分块。"""
    client.create_knowledge_doc(
        project["id"], "退款规则",
        "# 退款规则\n用户在支付后 24 小时内可全额退款，超过 24 小时收取百分之五手续费。",
    )
    events = _chat_events(client, project["id"], "退款手续费是多少")
    done = events[-1]
    assert "命中" in done["content"]
    assert "退款规则" in done["content"]
