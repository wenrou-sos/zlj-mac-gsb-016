"""聚集分析引擎单元测试：DBSCAN、划伤线性判定、边缘环/中心聚集、良率统计。"""
import math

from app.analysis import analyze_wafer, dbscan, is_defect_label, pca_linear_ratio


def _grid_points():
    """31x31 范围内的圆形晶圆点位（die 间距 10mm）。"""
    pts = []
    pid = 0
    for ix in range(-15, 16):
        for iy in range(-15, 16):
            x, y = ix * 10.0, iy * 10.0
            if math.hypot(x, y) <= 145:
                pid += 1
                pts.append({"id": pid, "x_mm": x, "y_mm": y,
                            "defect_type": "GOOD", "is_defect": False})
    return pts


def test_good_label_recognition():
    assert not is_defect_label("GOOD")
    assert not is_defect_label(" good ")
    assert not is_defect_label("")
    assert not is_defect_label(None)
    assert not is_defect_label("NULL")
    assert is_defect_label("PARTICLE")
    assert is_defect_label("划伤")


def test_dbscan_finds_dense_cluster():
    # 12 个紧密排列的点 + 几个孤立噪声
    pts = [(i, float(i) * 2, 0.0) for i in range(12)]
    pts += [(100, 100.0, 100.0), (101, -100.0, -80.0), (102, 50.0, -60.0)]
    labels, clusters = dbscan(pts, eps=10, min_samples=5)
    assert len(clusters) == 1
    assert len(clusters[0]) == 12
    # 噪声点标签为 -1
    assert labels[12] == -1
    assert labels[13] == -1
    assert labels[14] == -1


def test_dbscan_noise_only():
    pts = [(i, float(i) * 50, 0.0) for i in range(5)]
    labels, clusters = dbscan(pts, eps=10, min_samples=3)
    assert clusters == []
    assert all(l == -1 for l in labels)


def test_pca_linear_detection():
    # 沿 x 轴排列的点 -> 高特征值比，角度接近 0
    coords = [(float(i) * 5, 0.0) for i in range(-5, 6)]
    angle, ratio = pca_linear_ratio(coords)
    assert ratio > 10
    assert abs(angle) < math.radians(5) or abs(abs(angle) - math.pi) < math.radians(5)

    # 近似圆形分布 -> 低特征值比
    import random
    rng = random.Random(42)
    coords = [(rng.uniform(-1, 1) * 20, rng.uniform(-1, 1) * 20) for _ in range(40)]
    _, ratio = pca_linear_ratio(coords)
    assert ratio < 3


def test_wafer_random_defects_is_normal():
    import random
    rng = random.Random(1)
    points = _grid_points()
    for p in points:
        if rng.random() < 0.02:
            p["is_defect"] = True
            p["defect_type"] = "PARTICLE"
    result = analyze_wafer(points)
    assert result["has_anomaly"] is False
    assert result["overall_severity"] == "low"
    codes = {pat["code"] for pat in result["patterns"]}
    assert "random" in codes
    assert result["yield_rate"] > 0.95


def test_wafer_edge_ring_detected():
    import random
    rng = random.Random(2)
    points = _grid_points()
    for p in points:
        if math.hypot(p["x_mm"], p["y_mm"]) >= 123 and rng.random() < 0.5:
            p["is_defect"] = True
            p["defect_type"] = "CRACK"
    result = analyze_wafer(points, eps=10, min_samples=5)
    codes = {pat["code"] for pat in result["patterns"]}
    assert "ring" in codes
    assert result["has_anomaly"] is True


def test_wafer_local_cluster_detected():
    points = _grid_points()
    # 在 (-30, 20) 附近人为制造 15 个紧密缺陷
    center = (-30.0, 20.0)
    made = 0
    for p in points:
        if made < 15 and math.hypot(p["x_mm"] - center[0], p["y_mm"] - center[1]) <= 25:
            p["is_defect"] = True
            p["defect_type"] = "MISSING_DIE"
            made += 1
    assert made == 15
    result = analyze_wafer(points, eps=10, min_samples=5)
    assert result["anomaly_cluster_count"] >= 1
    big = max(result["clusters"], key=lambda c: c["size"])
    assert big["is_anomaly"] is True
    assert big["relative_density"] >= 1.5


def test_wafer_scratch_detected():
    points = _grid_points()
    # 45° 对角划伤：相邻对角 die 间距约 14mm，可被 DBSCAN 连成带
    theta = math.radians(45)
    n = 0
    for p in points:
        dist = abs(p["y_mm"] * math.cos(theta) - p["x_mm"] * math.sin(theta))
        if dist <= 4 and -120 <= p["x_mm"] <= 120:
            p["is_defect"] = True
            p["defect_type"] = "SCRATCH"
            n += 1
    assert n >= 10
    result = analyze_wafer(points)
    codes = {pat["code"] for pat in result["patterns"]}
    assert "scratch" in codes
    scratch = next(p for p in result["patterns"] if p["code"] == "scratch")
    assert scratch["severity"] == "high"


def test_yield_rate_calculation():
    points = _grid_points()
    for i, p in enumerate(points):
        if i % 4 == 0:
            p["is_defect"] = True
            p["defect_type"] = "STAIN"
    result = analyze_wafer(points)
    expected = sum(1 for p in points if p["is_defect"])
    assert result["total_points"] == len(points)
    assert result["defect_count"] == expected
    assert abs(result["yield_rate"] - (1 - expected / len(points))) < 0.01
    assert result["yield_rate"] < 0.8


def test_empty_wafer():
    result = analyze_wafer([])
    assert result["total_points"] == 0
    assert result["yield_rate"] == 1.0
    assert result["has_anomaly"] is False
