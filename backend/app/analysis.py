"""晶圆缺陷空间分析引擎。

- DBSCAN 聚类（纯 Python 实现，网格空间索引加速，无需 numpy/sklearn）
- 主成分分析（2D 协方差矩阵特征分解）判断线性缺陷（划伤 scratch）
- 缺陷空间模式识别：cluster / ring / center / scratch
"""
import math
from collections import deque

# 判定为“非缺陷”的缺陷类型代码（大小写不敏感）
GOOD_LABELS = {"", "good", "ok", "pass", "normal", "none", "null", "nan", "-", "0"}

# 严重程度阈值（相对缺陷率 = 簇内局部缺陷率 / 晶圆整体缺陷率）
SEVERITY_HIGH = 3.0
SEVERITY_MEDIUM = 1.5
# 聚集异常需同时满足的最低规模门槛；低缺陷率下的小簇不单独报警
ANOMALY_MIN_CLUSTER_SIZE = 10
# 边缘环判定：边缘区域缺陷占比，且其富集程度相对整体需达到的倍数
EDGE_FRACTION = 0.35
EDGE_ENRICHMENT = 1.3
EDGE_MIN_COUNT = 12
# 中心聚集判定（基于中心点的簇判断，避免小晶圆上全局占比天然偏高）
CENTER_FRACTION = 0.35
CENTER_CLUSTER_FRACTION = 0.6
# 线性（划伤）判定：主成分特征值比
LINEAR_EIGEN_RATIO = 6.0
LINEAR_MIN_SIZE = 8


def is_defect_label(label) -> bool:
    if label is None:
        return False
    return str(label).strip().lower() not in GOOD_LABELS


def dbscan(points, eps=10.0, min_samples=5):
    """对 [(id, x, y), ...] 做 DBSCAN 聚类。

    返回 labels 列表，-1 表示噪声，0..k-1 为簇编号（按大小降序）。
    采用网格分桶，邻居查询只检查周围 9 个桶，避免 O(n²)。
    """
    n = len(points)
    labels = [-1] * n
    # 均匀网格：桶边长 = eps。真实距离 <= eps 的两点所在桶索引差必不超过 1，
    # 因此检索周围 3x3 桶再按真实距离过滤即可，避免 O(n²)。
    cell = eps
    grid: dict = {}
    for i, (_, x, y) in enumerate(points):
        grid.setdefault((int(math.floor(x / cell)), int(math.floor(y / cell))), []).append(i)

    def neighbors(idx):
        _, x, y = points[idx]
        gx, gy = int(math.floor(x / cell)), int(math.floor(y / cell))
        out = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for j in grid.get((gx + dx, gy + dy), ()):
                    _, xj, yj = points[j]
                    if (xj - x) ** 2 + (yj - y) ** 2 <= eps * eps:
                        out.append(j)
        return out

    visited = [False] * n
    labels = [-1] * n
    cluster_id = -1
    clusters = []

    for i in range(n):
        if visited[i]:
            continue
        visited[i] = True
        nbrs = neighbors(i)
        if len(nbrs) < min_samples:
            continue  # 暂时视为噪声；后续仍可能被其它核心点密度可达而吸收
        cluster_id += 1
        members = []

        def assign(idx):
            if labels[idx] == -1:
                labels[idx] = cluster_id
                members.append(idx)

        queue = deque(nbrs)
        queued = set(nbrs)
        assign(i)
        while queue:
            j = queue.popleft()
            assign(j)
            if not visited[j]:
                visited[j] = True
                jnbrs = neighbors(j)
                if len(jnbrs) >= min_samples:
                    for k in jnbrs:
                        if k not in queued:
                            queued.add(k)
                            queue.append(k)
        clusters.append(members)

    # 按成员数量降序重新编号
    order = sorted(range(len(clusters)), key=lambda c: -len(clusters[c]))
    remapped = [-1] * n
    new_clusters = []
    for new_id, old_id in enumerate(order):
        members = clusters[old_id]
        new_clusters.append(members)
        for j in members:
            remapped[j] = new_id
    return remapped, new_clusters


def pca_linear_ratio(coords):
    """2D PCA，返回 (主方向角(弧度), 大特征值/小特征值)。点数不足时返回 (0, 1)。"""
    n = len(coords)
    if n < 2:
        return 0.0, 1.0
    mx = sum(x for x, _ in coords) / n
    my = sum(y for _, y in coords) / n
    sxx = syy = sxy = 0.0
    for x, y in coords:
        dx, dy = x - mx, y - my
        sxx += dx * dx
        syy += dy * dy
        sxy += dx * dy
    sxx /= n
    syy /= n
    sxy /= n
    trace = sxx + syy
    disc = math.sqrt(max(0.0, ((sxx - syy) / 2) ** 2 + sxy * sxy))
    lam1 = trace / 2 + disc
    lam2 = trace / 2 - disc
    angle = 0.5 * math.atan2(2 * sxy, sxx - syy)
    if lam2 <= 1e-9:
        return angle, float("inf")
    return angle, lam1 / lam2


def estimate_die_area(points, max_sample=200, search=30.0):
    """通过采样估计 die 平均面积（最近邻间距的平方）。"""
    n = len(points)
    if n < 2:
        return 100.0
    step = max(1, n // max_sample)
    cell = 5.0
    grid: dict = {}
    for i, p in enumerate(points):
        grid.setdefault((int(math.floor(p["x_mm"] / cell)),
                         int(math.floor(p["y_mm"] / cell))), []).append(i)
    dists = []
    for si in range(0, n, step):
        p = points[si]
        best = None
        gx = int(math.floor(p["x_mm"] / cell))
        gy = int(math.floor(p["y_mm"] / cell))
        reach = int(math.ceil(search / cell))
        for dx in range(-reach, reach + 1):
            for dy in range(-reach, reach + 1):
                for j in grid.get((gx + dx, gy + dy), ()):
                    if j == si:
                        continue
                    q = points[j]
                    d2 = (q["x_mm"] - p["x_mm"]) ** 2 + (q["y_mm"] - p["y_mm"]) ** 2
                    if best is None or d2 < best:
                        best = d2
        if best:
            dists.append(best)
    if not dists:
        return 100.0
    dists.sort()
    spacing2 = dists[len(dists) // 2]  # 中位数最近邻间距平方
    return max(spacing2, 1.0)


def analyze_wafer(points, radius_mm=150.0, eps=30.0, min_samples=5):
    """分析单片晶圆。

    points: [{"id","x_mm","y_mm","defect_type","is_defect"}, ...]
    返回完整分析结果 dict（含 clusters / patterns / summary）。
    """
    total = len(points)
    defect_pts = [p for p in points if p["is_defect"]]
    n_def = len(defect_pts)
    overall_rate = n_def / total if total else 0.0
    die_area = estimate_die_area(points) if total else 100.0

    # 缺陷类型分布
    type_counts: dict = {}
    for p in defect_pts:
        t = p["defect_type"]
        type_counts[t] = type_counts.get(t, 0) + 1

    labels, cluster_members = dbscan(
        [(p["id"], p["x_mm"], p["y_mm"]) for p in defect_pts],
        eps=eps,
        min_samples=min_samples,
    )

    clusters_out = []
    significant_cluster_count = 0
    for cid, members in enumerate(cluster_members):
        coords = [(defect_pts[j]["x_mm"], defect_pts[j]["y_mm"]) for j in members]
        cx = sum(x for x, _ in coords) / len(coords)
        cy = sum(y for _, y in coords) / len(coords)
        dist_c = math.sqrt(cx * cx + cy * cy)
        edge = sum(1 for x, y in coords if math.sqrt(x * x + y * y) >= radius_mm * 0.82)
        center = sum(1 for x, y in coords if math.sqrt(x * x + y * y) <= radius_mm * 0.33)
        angle, ratio = pca_linear_ratio(coords)
        # 缺陷密度：以簇覆盖范围（标准差半径）折算的 die 数为分母
        spread = math.sqrt(
            sum((x - cx) ** 2 + (y - cy) ** 2 for x, y in coords) / len(coords)
        )
        radius_die = max(spread / math.sqrt(die_area), 1.0)
        covered_dies = math.pi * radius_die ** 2
        local_rate = min(len(members) / covered_dies, 1.0)
        density = local_rate / die_area
        # 相对缺陷率 = 簇内局部缺陷率 / 晶圆整体缺陷率
        rel_density = local_rate / (overall_rate + 1e-12)

        ctypes: dict = {}
        for j in members:
            t = defect_pts[j]["defect_type"]
            ctypes[t] = ctypes.get(t, 0) + 1

        is_linear = ratio >= LINEAR_EIGEN_RATIO and len(members) >= LINEAR_MIN_SIZE
        pattern = "scratch" if is_linear else "cluster"
        # 线性划伤只要成带即为异常；普通簇需同时满足密度倍数与规模门槛
        if is_linear:
            is_anomaly = True
        else:
            is_anomaly = (
                rel_density >= SEVERITY_MEDIUM
                and len(members) >= ANOMALY_MIN_CLUSTER_SIZE
            )
        if is_anomaly:
            significant_cluster_count += 1

        if is_linear:
            severity = "high" if len(members) >= 12 else "medium"
        elif is_anomaly and rel_density >= SEVERITY_HIGH:
            severity = "high"
        elif is_anomaly:
            severity = "medium"
        else:
            severity = "low"

        clusters_out.append(
            {
                "cluster_id": cid,
                "size": len(members),
                "center_x": round(cx, 3),
                "center_y": round(cy, 3),
                "spread_mm": round(spread, 3),
                "defect_density": round(density, 6),
                "relative_density": round(rel_density, 3),
                "edge_fraction": round(edge / len(members), 3),
                "center_fraction": round(center / len(members), 3),
                "linear_ratio": round(ratio, 2) if math.isfinite(ratio) else None,
                "orientation_deg": round(math.degrees(angle), 1),
                "pattern": pattern,
                "is_anomaly": is_anomaly,
                "severity": severity,
                "defect_types": sorted(
                    ({"defect_type": t, "count": c} for t, c in ctypes.items()),
                    key=lambda d: -d["count"],
                ),
                "point_ids": [defect_pts[j]["id"] for j in members],
            }
        )

    # ---- 全局空间模式 ----
    patterns: list = []
    if n_def:
        edge_n = sum(
            1 for p in defect_pts if math.hypot(p["x_mm"], p["y_mm"]) >= radius_mm * 0.82
        )
        edge_frac = edge_n / n_def
        # 边缘区域可容纳的 die 约占整圆 (1-0.82²)=32.8%，需超过该基线才算“富集”
        edge_baseline = 1 - 0.82 ** 2
        edge_enriched = (
            edge_n >= EDGE_MIN_COUNT
            and edge_frac >= max(EDGE_FRACTION, edge_baseline * EDGE_ENRICHMENT)
        )

        # 划伤：取最大线性簇
        scratch = next((c for c in clusters_out if c["pattern"] == "scratch"), None)
        if scratch and scratch["is_anomaly"]:
            patterns.append(_pattern("scratch", "划伤/线性缺陷",
                                     scratch["severity"],
                                     f"检测到线性缺陷带，方向 {scratch['orientation_deg']}°，"
                                     f"含 {scratch['size']} 个缺陷点",
                                     scratch["cluster_id"]))
        # 边缘环
        if edge_enriched:
            sev = "high" if edge_frac >= 0.5 else "medium"
            patterns.append(_pattern("ring", "边缘环缺陷", sev,
                                     f"{edge_frac:.0%} 的缺陷点集中在晶圆边缘（边缘环），"
                                     "常见于夹持/刻蚀边缘效应"))
        # 中心聚集：以靠近中心且成员主要落在中心区域的簇判定
        center_cluster = next(
            (c for c in clusters_out
             if c["is_anomaly"]
             and math.hypot(c["center_x"], c["center_y"]) <= radius_mm * 0.33
             and c["center_fraction"] >= CENTER_CLUSTER_FRACTION),
            None,
        )
        if center_cluster and not (scratch and scratch["cluster_id"] == center_cluster["cluster_id"]):
            patterns.append(_pattern(
                "center", "中心聚集缺陷", center_cluster["severity"],
                f"晶圆中心区域发现高密度缺陷簇，含 {center_cluster['size']} 个缺陷点，"
                "常见于涂胶/研磨中心工艺异常",
                center_cluster["cluster_id"],
            ))
        # 局部聚集（非划伤、非中心聚集的其它异常簇）
        claimed = {p["cluster_id"] for p in patterns if p["cluster_id"] is not None}
        other_anomalies = [
            c for c in clusters_out
            if c["is_anomaly"] and c["cluster_id"] not in claimed
        ]
        if other_anomalies:
            worst = max(other_anomalies, key=lambda c: c["relative_density"])
            patterns.append(_pattern(
                "cluster", "局部聚集异常", worst["severity"],
                f"发现 {len(other_anomalies)} 个高密度缺陷簇，最大簇含 "
                f"{worst['size']} 个缺陷点，相对缺陷密度 {worst['relative_density']}x",
                worst["cluster_id"],
            ))

    if not patterns:
        patterns.append(_pattern("random", "随机分布/正常", "low",
                                 "缺陷点呈随机分布，未发现明显空间聚集异常"))

    highest = {"high": 3, "medium": 2, "low": 1}
    overall_severity = max((p["severity"] for p in patterns), key=lambda s: highest[s])

    return {
        "total_points": total,
        "defect_count": n_def,
        "yield_rate": round(1 - overall_rate, 6),
        "defect_rate": round(overall_rate, 6),
        "defect_type_counts": [
            {"defect_type": t, "count": c}
            for t, c in sorted(type_counts.items(), key=lambda kv: -kv[1])
        ],
        "cluster_count": len(clusters_out),
        "anomaly_cluster_count": significant_cluster_count,
        "clusters": clusters_out,
        "patterns": patterns,
        "overall_severity": overall_severity,
        "has_anomaly": overall_severity in ("high", "medium"),
        "params": {"eps": eps, "min_samples": min_samples, "radius_mm": radius_mm},
    }


def _pattern(code, name, severity, description, cluster_id=None):
    return {
        "code": code,
        "name": name,
        "severity": severity,
        "description": description,
        "cluster_id": cluster_id,
    }
