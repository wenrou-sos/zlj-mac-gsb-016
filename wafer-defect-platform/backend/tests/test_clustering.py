"""聚类算法单元测试：DBSCAN 正确性与模式分类。"""
import numpy as np

from app.clustering import (PATTERN_LABELS, analyze_clusters, classify_pattern,
                            dbscan)


def _blob(cx, cy, n=10, spread=0.5, seed=0):
    rng = np.random.default_rng(seed)
    return rng.normal([cx, cy], spread, (n, 2))


def test_dbscan_two_clusters_and_noise():
    pts = np.vstack([_blob(0, 0, seed=1), _blob(20, 20, seed=2),
                     np.array([[10.0, 10.0]])])  # 中间孤立点
    labels = dbscan(pts, eps=2.0, min_samples=3)
    assert set(labels[:-1]) == {0, 1}
    assert labels[-1] == -1  # 噪声


def test_dbscan_empty():
    labels = dbscan(np.empty((0, 2)), eps=1.0, min_samples=3)
    assert len(labels) == 0


def test_dbscan_all_noise():
    pts = np.array([[0, 0], [10, 0], [0, 10], [10, 10]], dtype=float)
    labels = dbscan(pts, eps=1.0, min_samples=2)
    assert (labels == -1).all()


def test_dbscan_chain_connects():
    """链式可达的点应归入同一簇。"""
    pts = np.array([[i * 0.9, 0.0] for i in range(10)])
    labels = dbscan(pts, eps=1.0, min_samples=2)
    assert len(set(labels)) == 1


def test_classify_linear():
    rng = np.random.default_rng(7)
    t = rng.random(30)[:, None]
    pts = np.hstack([t * 20, rng.normal(0, 0.3, (30, 1))])  # 水平长线
    assert classify_pattern(pts, center=(10, 10), radius=10) == "linear"


def test_classify_center_blob():
    pts = _blob(10, 10, n=30, spread=1.5, seed=3)
    assert classify_pattern(pts, center=(10, 10), radius=10) == "cluster"


def test_classify_edge_ring():
    rng = np.random.default_rng(11)
    ang = rng.uniform(0, 2 * np.pi, 40)
    pts = np.column_stack([10 + 9 * np.cos(ang), 10 + 9 * np.sin(ang)])
    assert classify_pattern(pts, center=(10, 10), radius=10) == "edge_ring"


def test_classify_edge_cluster():
    pts = _blob(19, 10, n=20, spread=1.0, seed=5)
    assert classify_pattern(pts, center=(10, 10), radius=10) == "edge"


def test_analyze_clusters_summary():
    pts = np.vstack([_blob(5, 5, n=8, seed=8), _blob(15, 15, n=5, seed=9)])
    labels = dbscan(pts, eps=2.0, min_samples=3)
    codes = ["PRT"] * 8 + ["SCR"] * 5
    clusters = analyze_clusters(pts, labels, codes, center=(10, 10), radius=10)
    assert len(clusters) == 2
    assert clusters[0]["size"] == 8  # 按规模降序
    assert clusters[0]["dominant_type"] == "PRT"
    assert clusters[0]["pattern_label"] == PATTERN_LABELS[clusters[0]["pattern"]]
    assert len(clusters[0]["defects"]) == 8
