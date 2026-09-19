"""统计分析接口：总览、批次良率对比、缺陷帕累托。"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..crud import lot_summary, wafer_stats
from ..database import get_db
from ..models import Defect, DefectType, Lot, Wafer

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/summary")
def summary(db: Session = Depends(get_db)):
    """平台级 KPI 总览。"""
    lots = db.query(Lot).all()
    wafers = db.query(Wafer).all()
    yields = [wafer_stats(db, w)["yield"] for w in wafers]
    return {
        "lot_count": len(lots),
        "wafer_count": len(wafers),
        "defect_count": db.query(func.count(Defect.id)).scalar() or 0,
        "avg_yield": round(sum(yields) / len(yields), 4) if yields else None,
    }


@router.get("/yield")
def yield_compare(lot_ids: str | None = Query(None, description="逗号分隔的批次ID"),
                  db: Session = Depends(get_db)):
    """批次良率对比：每片晶圆良率 + 批次均值。"""
    q = db.query(Lot).order_by(Lot.id)
    if lot_ids:
        ids = [int(x) for x in lot_ids.split(",") if x.strip()]
        q = q.filter(Lot.id.in_(ids))
    lots = []
    for lot in q.all():
        wafers = db.query(Wafer).filter(Wafer.lot_id == lot.id) \
                    .order_by(Wafer.wafer_number).all()
        wafer_items = []
        for w in wafers:
            s = wafer_stats(db, w)
            wafer_items.append({"wafer_id": w.id, "wafer_number": w.wafer_number,
                                **s})
        avg = (sum(i["yield"] for i in wafer_items) / len(wafer_items)
               if wafer_items else None)
        lots.append({"lot_id": lot.id, "name": lot.name, "product": lot.product,
                     "wafer_count": len(wafer_items),
                     "avg_yield": round(avg, 4) if avg is not None else None,
                     "wafers": wafer_items})
    return {"lots": lots}


@router.get("/pareto")
def defect_pareto(lot_id: int | None = None, db: Session = Depends(get_db)):
    """缺陷类型帕累托分析（可按批次过滤）。"""
    q = (db.query(DefectType.code, DefectType.name, DefectType.color,
                  func.count(Defect.id).label("cnt"))
         .join(Defect, Defect.defect_type_id == DefectType.id))
    if lot_id is not None:
        q = q.join(Wafer, Defect.wafer_id == Wafer.id).filter(Wafer.lot_id == lot_id)
    rows = q.group_by(DefectType.id).order_by(func.count(Defect.id).desc()).all()

    total = sum(r.cnt for r in rows) or 1
    items, cumulative = [], 0.0
    for r in rows:
        ratio = r.cnt / total
        cumulative += ratio
        items.append({"code": r.code, "name": r.name, "color": r.color,
                      "count": r.cnt, "ratio": round(ratio, 4),
                      "cumulative": round(cumulative, 4)})
    return {"total": total, "items": items}
