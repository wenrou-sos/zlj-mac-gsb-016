"""演示数据生成：3 个批次，覆盖正常/边缘环/聚集+划伤三种典型场景。"""
import math
import random

from sqlalchemy.orm import Session

from .analysis import is_defect_label
from .models import Batch, InspectionPoint, Wafer

RADIUS = 150.0
DIE = 10.0  # die 间距 10mm

DEFECT_TYPES = ["PARTICLE", "SCRATCH", "CRACK", "STAIN", "MISSING_DIE", "ETCH_DEFECT"]


def _all_die_positions():
    pts = []
    for ix in range(-15, 16):
        for iy in range(-15, 16):
            x, y = ix * DIE, iy * DIE
            # 留一点边距，模拟可检测区域
            if math.hypot(x, y) <= RADIUS - DIE * 0.5:
                pts.append((float(x), float(y)))
    return pts


def _mark(positions, rng, random_rate=0.02, pattern=None):
    """在网格点位上标注缺陷类型。

    random_rate: 基础随机缺陷比例
    pattern: None | "ring" | "cluster"
    """
    result = {}
    ring_positions = [p for p in positions if math.hypot(*p) >= RADIUS * 0.82]
    center_positions = [p for p in positions if math.hypot(*p) <= RADIUS * 0.35]

    for p in positions:
        result[p] = "GOOD"

    # 全局随机散点缺陷
    for p in positions:
        if rng.random() < random_rate:
            result[p] = rng.choice(["PARTICLE", "STAIN", "ETCH_DEFECT"])

    if pattern == "ring":
        # 边缘环：约 30% 的边缘 die 出现缺陷
        for p in ring_positions:
            if rng.random() < 0.3:
                result[p] = rng.choice(["PARTICLE", "CRACK", "ETCH_DEFECT"])
    elif pattern == "cluster":
        # 中心局部聚集 + 一条划伤线
        cx, cy = -20.0, 15.0
        for p in center_positions:
            if math.hypot(p[0] - cx, p[1] - cy) <= 25 and rng.random() < 0.5:
                result[p] = rng.choice(["PARTICLE", "MISSING_DIE"])
        # 划伤：过晶圆中部的 45° 对角线附近（对角 die 可连成连续带）
        x0, x1 = -110.0, 110.0
        theta = math.radians(45)
        for p in positions:
            dist = abs(p[1] * math.cos(theta) - p[0] * math.sin(theta))
            if x0 <= p[0] <= x1 and dist <= 5.0 and rng.random() < 0.6:
                result[p] = "SCRATCH"
    return result


def seed_demo_data(db: Session) -> dict:
    if db.query(Batch).count() > 0:
        return {"status": "skipped", "reason": "数据库中已存在批次数据"}

    positions = _all_die_positions()
    plan = [
        ("LOT-A", "正常批次（随机散点缺陷）", None),
        ("LOT-B", "边缘环异常批次", "ring"),
        ("LOT-C", "聚集/划伤异常批次", "cluster"),
    ]
    summary = []
    for batch_index, (batch_name, _desc, pattern) in enumerate(plan):
        batch = Batch(name=batch_name, product="MCU-7nm")
        db.add(batch)
        db.flush()
        total = defective = 0
        for wi in range(2):
            wafer = Wafer(batch_id=batch.id, name=f"{batch_name}-W{wi + 1:02d}", diameter_mm=300.0)
            db.add(wafer)
            db.flush()
            rng = random.Random(1000 + batch_index * 100 + wi)
            marks = _mark(positions, rng, random_rate=0.02, pattern=pattern)
            rows = [
                InspectionPoint(
                    wafer_id=wafer.id, x_mm=x, y_mm=y,
                    defect_type=dtype, is_defect=is_defect_label(dtype),
                )
                for (x, y), dtype in marks.items()
            ]
            db.bulk_save_objects(rows)
            total += len(rows)
            defective += sum(1 for r in rows if r.is_defect)
        summary.append({"batch": batch_name, "points": total,
                        "yield_rate": round(1 - defective / total, 4)})
    db.commit()
    return {"status": "seeded", "batches": summary}
