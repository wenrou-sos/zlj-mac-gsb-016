"""缺陷聚集分析：DBSCAN 密度聚类 + 缺陷模式启发式分类。

不依赖 scikit-learn，使用 numpy 实现，保证镜像精简、测试快速。
"""
from __future__ import annotations

import numpy as np

# 缺陷模式 → 中文标签
PATTERN_LABELS = {
    "cluster": "团状聚集",
    "linear": "线状/划伤",
    "edge": "边缘聚集",
    "edge_ring": "边缘环状",
}


def dbscan(points: np.ndarray, eps: float, min_samples: int) -> np.ndarray:
    """DBSCAN 聚类。

    参数:
        points: (n, 2) 坐标数组
        eps: 邻域半径（单位：管芯）
        min_samples: 核心点所需最小邻居数（含自身）
    返回:
        (n,) 标签数组，-1 表示噪声点
    """
    n = len(points)
    labels = np.full(n, -1, dtype=int)
    if n == 0:
        return labels

    # 预计算邻接关系
    diff = points[:, None, :] - points[None, :, :]
    dist = np.sqrt((diff ** 2).sum(axis=-1))
    neighbors = [np.where(dist[i] <= eps)[0] for i in range(n)]

    visited = np.zeros(n, dtype=bool)
    cluster_id = 0
    for i in range(n):
        if visited[i]:
            continue
        visited[i] = True
        nbrs = neighbors[i]
        if len(nbrs) < min_samples:
            continue  # 暂记为噪声，后续可能被其他簇吸收
        labels[i] = cluster_id
        # 广度优先扩展簇
        queue = list(nbrs)
        in_queue = set(queue)
        head = 0
        while head < len(queue):
            j = queue[head]
            head += 1
            if not visited[j]:
                visited[j] = True
                nbrs_j = neighbors[j]
                if len(nbrs_j) >= min_samples:
                    for m in nbrs_j:
                        if m not in in_queue:
                            in_queue.add(m)
                            queue.append(m)
            if labels[j] == -1:
                labels[j] = cluster_id
        cluster_id += 1
    return labels


def _angular_span(angles: np.ndarray) -> float:
    """一组角度的最大覆盖跨度（弧度）。"""
    if len(angles) < 2:
        return 0.0
    a = np.sort(angles)
    gaps = np.diff(np.concatenate([a, a[:1] + 2 * np.pi]))
    return float(2 * np.pi - gaps.max())


def classify_pattern(points: np.ndarray, center: tuple[float, float],
                     radius: float) -> str:
    """根据簇的几何特征分类缺陷模式。

    - linear:    协方差主轴特征值比大 → 细长分布（典型划伤）
    - edge_ring: 点集整体位于边缘带且角度覆盖 > 180° → 环状（典型边缘污染）
    - edge:      点集整体位于边缘带
    - cluster:   其他（团状聚集）
    """
    if len(points) < 4:
        return "cluster"

    centroid = points.mean(axis=0)
    cov = np.cov((points - centroid).T)
    eigvals = np.linalg.eigvalsh(cov)  # 升序
    if eigvals[-1] / max(eigvals[0], 1e-9) >= 8.0:
        return "linear"

    c = np.asarray(center, dtype=float)
    if radius > 0:
        # 用点的平均径向距离判定边缘带（环状分布质心仍在圆心，不能用质心）
        rel = points - c
        mean_r = float(np.linalg.norm(rel, axis=1).mean()) / radius
        if mean_r >= 0.7:
            angles = np.arctan2(rel[:, 1], rel[:, 0])
            if _angular_span(angles) > np.pi:
                return "edge_ring"
            return "edge"
    return "cluster"


def analyze_clusters(points: np.ndarray, labels: np.ndarray,
                     type_codes: list[str], center: tuple[float, float],
                     radius: float) -> list[dict]:
    """汇总每个簇的统计信息，按规模降序返回。"""
    clusters = []
    for cid in sorted(set(labels.tolist()) - {-1}):
        idx = np.where(labels == cid)[0]
        pts = points[idx]
        centroid = pts.mean(axis=0)
        r = float(np.linalg.norm(pts - centroid, axis=1).max(initial=0.0))
        codes = [type_codes[i] for i in idx]
        dominant = max(set(codes), key=codes.count)
        pattern = classify_pattern(pts, center, radius)
        clusters.append({
            "id": int(cid),
            "size": int(len(idx)),
            "centroid": {"x": round(float(centroid[0]), 2),
                         "y": round(float(centroid[1]), 2)},
            "bbox": {
                "x_min": int(pts[:, 0].min()), "x_max": int(pts[:, 0].max()),
                "y_min": int(pts[:, 1].min()), "y_max": int(pts[:, 1].max()),
            },
            "radius": round(r, 2),
            "pattern": pattern,
            "pattern_label": PATTERN_LABELS[pattern],
            "dominant_type": dominant,
            "defects": [{"x": int(points[i][0]), "y": int(points[i][1]),
                         "code": type_codes[i]} for i in idx],
        })
    clusters.sort(key=lambda c: c["size"], reverse=True)
    return clusters
