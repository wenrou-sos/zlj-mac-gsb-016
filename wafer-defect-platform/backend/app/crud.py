"""通用数据访问与统计辅助函数。"""
from sqlalchemy import func
from sqlalchemy.orm import Session

from .models import Defect, Lot, Wafer


def wafer_stats(db: Session, wafer: Wafer) -> dict:
    """计算单片晶圆的良率统计。

    良率 = 1 - 失效管芯数 / 总管芯数；同一管芯上多个缺陷只计一次失效。
    """
    total = wafer.die_rows * wafer.die_cols
    defective = (db.query(Defect.x, Defect.y)
                 .filter(Defect.wafer_id == wafer.id)
                 .distinct().count())
    defect_count = (db.query(func.count(Defect.id))
                    .filter(Defect.wafer_id == wafer.id).scalar() or 0)
    y = (total - defective) / total if total else 0.0
    return {
        "total_dies": total,
        "defective_dies": defective,
        "defect_count": defect_count,
        "yield": round(y, 4),
    }


def lot_summary(db: Session, lot: Lot) -> dict:
    """批次级汇总：晶圆数、缺陷总数、平均良率。"""
    wafers = db.query(Wafer).filter(Wafer.lot_id == lot.id).all()
    yields, defect_total = [], 0
    for w in wafers:
        s = wafer_stats(db, w)
        yields.append(s["yield"])
        defect_total += s["defect_count"]
    return {
        "id": lot.id,
        "name": lot.name,
        "product": lot.product,
        "wafer_count": len(wafers),
        "defect_count": defect_total,
        "avg_yield": round(sum(yields) / len(yields), 4) if yields else None,
    }
