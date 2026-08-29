"""设计稿节点：图片/Figma 导入、视觉解析、编辑与功能点合并。"""

PNG_BYTES = b"\x89PNG\r\n\x1a\nmock-design-image"


def _structured_document(client, project_id):
    doc = client.create_requirement(
        project_id,
        "设计稿测试需求",
        "用户可以填写信息并提交表单。",
    )
    return client.structure_requirement(project_id, doc["id"])


def test_rejects_fake_image_and_invalid_figma(client, project):
    doc = _structured_document(client, project["id"])
    response = client.post(
        f"/projects/{project['id']}/designs/upload",
        data={"document_id": doc["id"]},
        files={"file": ("fake.png", b"not-an-image", "image/png")},
    )
    assert response.status_code == 400

    response = client.post(
        f"/projects/{project['id']}/designs/figma",
        json={
            "document_id": doc["id"],
            "url": "https://evil.example.com/design/abc",
            "title": "伪造链接",
        },
    )
    assert response.status_code == 400


def test_design_image_parse_edit_merge_and_delete(client, project):
    doc = _structured_document(client, project["id"])
    base = f"/projects/{project['id']}/designs"

    upload = client.post(
        f"{base}/upload",
        data={"document_id": doc["id"]},
        files={"file": ("login.png", PNG_BYTES, "image/png")},
    )
    assert upload.status_code == 201
    asset = upload.json()
    assert asset["asset_type"] == "image"
    assert client.get(f"{base}/{asset['id']}/content").content == PNG_BYTES

    parsed = client.post(f"{base}/{asset['id']}/parse")
    assert parsed.status_code == 200
    parsed_asset = parsed.json()
    assert parsed_asset["status"] == "parsed"
    insight = parsed_asset["insights"][0]

    updated = client.patch(
        f"{base}/insights/{insight['id']}",
        json={"feature": "设计稿提交表单", "selected": True},
    )
    assert updated.status_code == 200
    assert updated.json()["feature"] == "设计稿提交表单"

    merged = client.post(
        f"{base}/merge",
        params={"document_id": doc["id"]},
        json={"insight_ids": [insight["id"]]},
    )
    assert merged.status_code == 200
    design_items = [item for item in merged.json()["items"] if item["source_type"] == "design"]
    assert len(design_items) == 1
    assert design_items[0]["source_ref_id"] == asset["id"]
    assert merged.json()["status"] == "structured"

    duplicate = client.post(
        f"{base}/merge",
        params={"document_id": doc["id"]},
        json={"insight_ids": [insight["id"]]},
    )
    assert duplicate.status_code == 200
    assert len([item for item in duplicate.json()["items"] if item["source_type"] == "design"]) == 1

    assert client.delete(f"{base}/{asset['id']}").status_code == 400

    disposable = client.post(
        f"{base}/upload",
        data={"document_id": doc["id"]},
        files={"file": ("disposable.png", PNG_BYTES, "image/png")},
    ).json()
    assert client.delete(f"{base}/{disposable['id']}").status_code == 204
    remaining = client.get(base, params={"document_id": doc["id"]}).json()
    assert [item["id"] for item in remaining] == [asset["id"]]


def test_figma_link_is_stored_without_parsing(client, project):
    doc = _structured_document(client, project["id"])
    base = f"/projects/{project['id']}/designs"
    response = client.post(
        f"{base}/figma",
        json={
            "document_id": doc["id"],
            "url": "https://www.figma.com/design/abc/demo",
            "title": "登录页",
        },
    )
    assert response.status_code == 201
    asset = response.json()
    assert asset["status"] == "linked"
    assert client.post(f"{base}/{asset['id']}/parse").status_code == 400
