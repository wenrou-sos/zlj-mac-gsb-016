"""初始数据：缺陷类型字典 + 可复现的演示数据。

演示数据包含三种典型良率水平与典型聚集模式（线状划伤、团状聚集、边缘环状），
便于开箱即用地展示图谱渲染与聚集识别能力。
"""
import numpy as np
from sqlalchemy.orm import Session

from .models import Defect, DefectType, Lot, Wafer

DEFAULT_DEFECT_TYPES = [
    # code, 名称, 颜色, 严重度
    ("SCR", "划痕", "#e74c3c", 4),
    ("PRT", "颗粒", "#e67e22", 2),
    ("CRK", "裂纹", "#9b59b6", 5),
    ("CNT", "污染", "#3498db", 2),
    ("PAT", "图形缺陷", "#2ecc71", 3),
    ("UNK", "未知", "#95a5a6", 1),
]

DEMO_LOT_NAMES = ("DEMO-2024A", "DEMO-2024B", "DEMO-2024C")


def seed_defect_types(db: Session) -> int:
    """补齐缺失的缺陷类型，返回新增数量（幂等）。"""
    existing = {t.code for t in db.query(DefectType).all()}
    added = 0
    for code, name, color, severity in DEFAULT_DEFECT_TYPES:
        if code not in existing:
            db.add(DefectType(code=code, name=name, color=color, severity=severity))
            added += 1
    if added:
        db.commit()
    return added


def seed_demo(db: Session, rows: int = 20, cols: int = 20) -> dict:
    """生成 3 个演示批次 × 5 片晶圆。已存在演示批次时跳过（幂等）。"""
    if db.query(Lot).filter(Lot.name.in_(DEMO_LOT_NAMES)).count():
        return {"created": False, "lots": list(DEMO_LOT_NAMES)}

    seed_defect_types(db)
    type_ids = {t.code: t.id for t in db.query(DefectType).all()}
    rng = np.random.default_rng(42)
    codes = ["SCR", "PRT", "CNT", "PAT", "CRK"]
    weights = [0.20, 0.35, 0.25, 0.15, 0.05]

    def clip(pts):
        pts[:, 0] = np.clip(pts[:, 0], 0, cols - 1)
        pts[:, 1] = np.clip(pts[:, 1], 0, rows - 1)
        return pts

    def add_defects(wafer_id, pts, pt_codes):
        db.add_all([Defect(wafer_id=wafer_id, x=int(p[0]), y=int(p[1]),
                           defect_type_id=type_ids[c])
                    for p, c in zip(pts, pt_codes)])

    def add_random(wafer_id, n):
        pts = np.column_stack([rng.integers(0, cols, n), rng.integers(0, rows, n)])
        add_defects(wafer_id, pts, rng.choice(codes, n, p=weights))

    def add_blob(wafer_id, cx, cy, spread, n, code="PRT"):
        pts = clip(rng.normal([cx, cy], spread, (n, 2)).round().astype(int))
        add_defects(wafer_id, pts, [code] * n)

    def add_line(wafer_id, p0, p1, n, code="SCR"):
        t = rng.random(n)[:, None]
        pts = np.array(p0) * (1 - t) + np.array(p1) * t
        pts += rng.normal(0, 0.6, pts.shape)
        add_defects(wafer_id, clip(pts.round().astype(int)), [code] * n)

    def add_ring(wafer_id, radius, n, code="CNT"):
        ang = rng.uniform(0, 2 * np.pi, n)
        r = rng.normal(radius, 0.8, n)
        pts = np.column_stack([
            (cols - 1) / 2 + r * np.cos(ang),
            (rows - 1) / 2 + r * np.sin(ang),
        ])
        add_defects(wafer_id, clip(pts.round().astype(int)), [code] * n)

    # (批次名, 产品, 每片随机缺陷基数, 图案生成函数)
    plan = [
        ("DEMO-2024A", "MCU-32bit", (6, 12), lambda wid, i: None),
        ("DEMO-2024B", "MCU-32bit", (14, 22),
         lambda wid, i: add_line(wid, (2, 3), (17, 15), 18) if i in (1, 3) else None),
        ("DEMO-2024C", "PMIC-90nm", (24, 34),
         lambda wid, i: (add_blob(wid, 10, 10, 2.0, 22) if i % 2 == 0
                         else add_ring(wid, 8.5, 26))),
    ]

    for name, product, (lo, hi), pattern_fn in plan:
        lot = Lot(name=name, product=product)
        db.add(lot)
        db.flush()
        for i in range(5):
            wafer = Wafer(lot_id=lot.id, wafer_number=i + 1,
                          die_rows=rows, die_cols=cols)
            db.add(wafer)
            db.flush()
            add_random(wafer.id, int(rng.integers(lo, hi)))
            pattern_fn(wafer.id, i)
    db.commit()
    return {"created": True, "lots": list(DEMO_LOT_NAMES)}
