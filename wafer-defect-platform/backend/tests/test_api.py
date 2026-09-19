"""API 端到端测试：启动、CRUD、导入、图谱、聚集、良率。"""


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_openapi_available(client):
    """应用正常启动并暴露 API 文档。"""
    r = client.get("/openapi.json")
    assert r.status_code == 200
    paths = r.json()["paths"]
    for p in ("/api/lots", "/api/wafers/{wafer_id}/map",
              "/api/wafers/{wafer_id}/clusters", "/api/analytics/yield"):
        assert p in paths


def test_defect_types_seeded(client):
    r = client.get("/api/defect-types")
    assert r.status_code == 200
    codes = {t["code"] for t in r.json()}
    assert {"SCR", "PRT", "CRK", "CNT", "PAT", "UNK"} <= codes


def test_create_lot_and_wafer(client):
    r = client.post("/api/lots", json={"name": "LOT-CRUD", "product": "TEST"})
    assert r.status_code == 201
    lot_id = r.json()["id"]

    # 重名批次应冲突
    assert client.post("/api/lots", json={"name": "LOT-CRUD"}).status_code == 409

    r = client.post("/api/wafers",
                    json={"lot_id": lot_id, "wafer_number": 1,
                          "die_rows": 10, "die_cols": 10})
    assert r.status_code == 201
    assert r.json()["yield"] == 1.0

    # 重复晶圆编号应冲突
    assert client.post("/api/wafers", json={"lot_id": lot_id,
                                            "wafer_number": 1}).status_code == 409


def test_import_csv_and_wafer_map(client, csv_payload):
    r = client.post("/api/import/csv?die_rows=20&die_cols=20",
                    files={"file": ("defects.csv", csv_payload, "text/csv")})
    assert r.status_code == 200
    body = r.json()
    assert body["defects_imported"] == 14
    assert body["lots_created"] == 1
    assert body["wafers_created"] == 2

    # 晶圆分布图
    lots = {l["name"]: l for l in client.get("/api/lots").json()}
    lot_t = lots["LOT-T"]
    wafers = client.get(f"/api/wafers?lot_id={lot_t['id']}").json()
    assert len(wafers) == 2
    w1 = next(w for w in wafers if w["wafer_number"] == 1)

    m = client.get(f"/api/wafers/{w1['id']}/map").json()
    assert m["die_rows"] == 20 and m["die_cols"] == 20
    assert m["defect_count"] == 13
    assert m["defective_dies"] == 13  # 13 个不同管芯
    assert m["yield"] == round(1 - 13 / 400, 4)
    assert len(m["defects"]) == 13
    assert all("color" in d for d in m["defects"])


def test_import_csv_out_of_bounds_skipped(client):
    csv_text = "lot,wafer,die_x,die_y,defect_code\nLOT-OOB,1,99,99,SCR\nLOT-OOB,1,1,1,SCR\n"
    r = client.post("/api/import/csv?die_rows=20&die_cols=20",
                    files={"file": ("x.csv", csv_text, "text/csv")})
    body = r.json()
    assert body["defects_imported"] == 1
    assert body["rows_skipped"] == 1
    assert body["errors"]


def test_import_json(client):
    records = [
        {"lot": "LOT-JSON", "wafer": 1, "die_x": 3, "die_y": 4, "defect_code": "PAT"},
        {"lot": "LOT-JSON", "wafer": 1, "die_x": 5, "die_y": 6},  # 缺省 UNK
    ]
    r = client.post("/api/import/json", json=records)
    assert r.status_code == 200
    assert r.json()["defects_imported"] == 2


def test_cluster_detection(client, csv_payload):
    """导入的紧密聚集应被 DBSCAN 识别为一个簇。"""
    lots = {l["name"]: l for l in client.get("/api/lots").json()}
    wafers = client.get(f"/api/wafers?lot_id={lots['LOT-T']['id']}").json()
    w1 = next(w for w in wafers if w["wafer_number"] == 1)

    r = client.get(f"/api/wafers/{w1['id']}/clusters?eps=2.5&min_samples=3")
    assert r.status_code == 200
    body = r.json()
    assert body["total_defects"] == 13
    assert body["cluster_count"] >= 1
    biggest = body["clusters"][0]
    assert biggest["size"] >= 8
    assert biggest["pattern"] == "cluster"
    assert biggest["dominant_type"] == "PRT"
    assert body["noise_count"] >= 5


def test_cluster_empty_wafer(client):
    r = client.post("/api/lots", json={"name": "LOT-EMPTY"})
    wid = client.post("/api/wafers", json={"lot_id": r.json()["id"],
                                           "wafer_number": 1}).json()["id"]
    body = client.get(f"/api/wafers/{wid}/clusters").json()
    assert body["cluster_count"] == 0
    assert body["clusters"] == []


def test_yield_analytics(client):
    """两个批次：已知缺陷数 → 校验良率计算与对比结构。"""
    for name, defects in [("LOT-Y1", 0), ("LOT-Y2", 40)]:
        lot_id = client.post("/api/lots", json={"name": name}).json()["id"]
        wid = client.post("/api/wafers", json={"lot_id": lot_id, "wafer_number": 1,
                                               "die_rows": 20, "die_cols": 20}
                          ).json()["id"]
        if defects:
            recs = [{"lot": name, "wafer": 1, "die_x": i % 20, "die_y": i // 20,
                     "defect_code": "PRT"} for i in range(defects)]
            assert client.post("/api/import/json", json=recs).json()[
                "defects_imported"] == defects

    lots = {l["name"]: l for l in client.get("/api/lots").json()}
    ids = f"{lots['LOT-Y1']['id']},{lots['LOT-Y2']['id']}"
    body = client.get(f"/api/analytics/yield?lot_ids={ids}").json()
    assert len(body["lots"]) == 2
    y1, y2 = body["lots"]
    assert y1["avg_yield"] == 1.0
    assert y2["avg_yield"] == round(1 - 40 / 400, 4)
    assert y2["wafers"][0]["defective_dies"] == 40


def test_pareto(client):
    body = client.get("/api/analytics/pareto").json()
    assert body["total"] > 0
    items = body["items"]
    counts = [i["count"] for i in items]
    assert counts == sorted(counts, reverse=True)  # 已按数量降序
    assert abs(sum(i["ratio"] for i in items) - 1.0) < 0.01


def test_summary(client):
    body = client.get("/api/analytics/summary").json()
    assert body["lot_count"] >= 1
    assert body["wafer_count"] >= 1
    assert 0 <= body["avg_yield"] <= 1


def test_demo_seed_idempotent(client):
    r1 = client.post("/api/demo/seed").json()
    assert r1["created"] is True
    r2 = client.post("/api/demo/seed").json()
    assert r2["created"] is False  # 幂等

    # 演示数据应能被聚集分析识别出簇
    lots = {l["name"]: l for l in client.get("/api/lots").json()}
    demo_c = lots["DEMO-2024C"]
    wafers = client.get(f"/api/wafers?lot_id={demo_c['id']}").json()
    body = client.get(f"/api/wafers/{wafers[0]['id']}/clusters").json()
    assert body["cluster_count"] >= 1


def test_wafer_not_found(client):
    assert client.get("/api/wafers/999999/map").status_code == 404
    assert client.get("/api/wafers/999999/clusters").status_code == 404
