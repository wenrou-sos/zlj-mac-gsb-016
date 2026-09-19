"""API 端到端集成测试：健康检查、导入、图谱分析、批次对比、删除。"""
import io
import math

from app.seed import seed_demo_data


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_openapi_docs_available(client):
    assert client.get("/openapi.json").status_code == 200
    assert client.get("/docs").status_code == 200


def test_empty_list(client):
    assert client.get("/api/batches").json() == []


def _edge_ring_csv():
    rows = ["batch,wafer,x,y,defect_type"]
    for ix in range(-15, 16):
        for iy in range(-15, 16):
            x, y = ix * 10.0, iy * 10.0
            if math.hypot(x, y) > 145:
                continue
            dtype = "GOOD"
            if math.hypot(x, y) >= 123 and (ix + iy) % 2 == 0:
                dtype = "CRACK"
            rows.append(f"LOT-R,W01,{x},{y},{dtype}")
    return "\n".join(rows).encode()


def _normal_csv():
    rows = ["batch,wafer,x,y,defect_type"]
    for ix in range(-15, 16):
        for iy in range(-15, 16):
            x, y = ix * 10.0, iy * 10.0
            if math.hypot(x, y) > 145:
                continue
            dtype = "PARTICLE" if (ix * 31 + iy) % 47 == 0 else "GOOD"
            rows.append(f"LOT-N,W01,{x},{y},{dtype}")
    return "\n".join(rows).encode()


def test_csv_upload_and_persistence(client):
    resp = client.post(
        "/api/import/file",
        files={"file": ("wafer.csv", io.BytesIO(_edge_ring_csv()), "text/csv")},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["batch_name"] == "LOT-R"
    assert data["wafer_count"] == 1
    assert data["point_count"] > 600
    assert data["defect_count"] > 30

    # 批次列表
    batches = client.get("/api/batches").json()
    assert len(batches) == 1
    assert batches[0]["name"] == "LOT-R"
    assert 0 < batches[0]["yield_rate"] < 1


def test_wafer_map_analysis(client):
    client.post(
        "/api/import/file",
        files={"file": ("ring.csv", io.BytesIO(_edge_ring_csv()), "text/csv")},
    )
    wafers = client.get("/api/wafers").json()
    wafer_id = wafers[0]["id"]
    resp = client.get(f"/api/wafers/{wafer_id}/map")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["points"]) == body["analysis"]["total_points"]
    codes = {p["code"] for p in body["analysis"]["patterns"]}
    assert "ring" in codes
    assert body["analysis"]["has_anomaly"] is True
    # 每个簇都有中心点坐标与缺陷类型明细
    for c in body["analysis"]["clusters"]:
        assert "center_x" in c and "severity" in c


def test_batch_compare(client):
    client.post(
        "/api/import/file",
        files={"file": ("normal.csv", io.BytesIO(_normal_csv()), "text/csv")},
    )
    client.post(
        "/api/import/file",
        files={"file": ("ring.csv", io.BytesIO(_edge_ring_csv()), "text/csv")},
    )
    resp = client.get("/api/batches/compare")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 2
    by_name = {i["batch_name"]: i for i in items}
    normal = by_name["LOT-N"]
    ring = by_name["LOT-R"]
    # 边缘环批次良率应显著低于正常批次
    assert ring["yield_rate"] < normal["yield_rate"]
    assert ring["anomaly_wafer_count"] >= 1
    assert ring["severity"] in ("high", "medium")
    # 良率、标准差字段存在且数值合法
    assert 0 <= normal["yield_rate"] <= 1
    assert normal["yield_stddev"] >= 0
    assert sum(tc["count"] for tc in ring["defect_type_counts"]) == ring["defect_count"]


def test_compare_with_id_filter(client):
    client.post(
        "/api/import/file",
        files={"file": ("a.csv", io.BytesIO(_normal_csv()), "text/csv")},
    )
    resp = client.get("/api/batches/compare?batch_ids=999")
    assert resp.json() == []
    resp = client.get("/api/batches/compare?batch_ids=abc")
    assert resp.status_code == 400


def test_json_import(client):
    payload = {
        "batch": "LOT-JSON",
        "wafers": [
            {"name": "W1", "points": [
                {"x_mm": 0, "y_mm": 0, "defect_type": "GOOD"},
                {"x_mm": 10, "y_mm": 10, "defect_type": "SCRATCH"},
            ]}
        ],
    }
    resp = client.post("/api/import/json", json=payload)
    assert resp.status_code == 200
    assert resp.json()["defect_count"] == 1


def test_import_validation_error(client):
    resp = client.post(
        "/api/import/file",
        files={"file": ("bad.csv", io.BytesIO(b"a,b\n1,2\n"), "text/csv")},
    )
    assert resp.status_code == 422

    resp = client.post(
        "/api/import/file",
        files={"file": ("empty.csv", io.BytesIO(b""), "text/csv")},
    )
    assert resp.status_code == 400


def test_wafer_not_found(client):
    assert client.get("/api/wafers/4242/map").status_code == 404


def test_delete_batch(client):
    client.post(
        "/api/import/file",
        files={"file": ("n.csv", io.BytesIO(_normal_csv()), "text/csv")},
    )
    batches = client.get("/api/batches").json()
    bid = batches[0]["id"]
    assert client.delete(f"/api/batches/{bid}").status_code == 200
    assert client.get("/api/batches").json() == []
    assert client.delete(f"/api/batches/{bid}").status_code == 404


def test_seed_demo_endpoint(client):
    resp = client.post("/api/admin/seed")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "seeded"
    assert len(body["batches"]) == 3
    # 再次播种应跳过，避免重复
    again = client.post("/api/admin/seed").json()
    assert again["status"] == "skipped"

    batches = client.get("/api/batches").json()
    assert {b["name"] for b in batches} == {"LOT-A", "LOT-B", "LOT-C"}


def test_demo_data_contains_expected_patterns(client, db):
    seed_demo_data(db)
    compare = client.get("/api/batches/compare").json()
    by_name = {i["batch_name"]: i for i in compare}
    # LOT-B 应识别出边缘环；LOT-C 应识别出空间异常（划伤 / 中心聚集 / 局部聚集）
    lotb_patterns = {p for w in by_name["LOT-B"]["wafers"] for p in w["patterns"]}
    lotc_patterns = {p for w in by_name["LOT-C"]["wafers"] for p in w["patterns"]}
    assert "ring" in lotb_patterns
    assert {"scratch", "cluster", "center"} & lotc_patterns
    # 良率排序：正常批次 > 异常批次
    assert by_name["LOT-A"]["yield_rate"] > by_name["LOT-B"]["yield_rate"]
