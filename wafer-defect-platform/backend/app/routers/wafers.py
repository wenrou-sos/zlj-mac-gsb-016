"""晶圆接口：创建、列表、缺陷分布图数据、聚集分析。"""
import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..clustering import analyze_clusters, dbscan
from ..crud import wafer_stats
from ..database import get_db
from ..models import Defect, Lot, Wafer
from ..schemas import WaferCreate

router = APIRouter(prefix="/api/wafers", tags=["wafers"])


def _get_wafer_or_404(db: Session, wafer_id: int) -> Wafer:
    wafer = db.get(Wafer, wafer_id)
    if not wafer:
        raise HTTPException(404, "晶圆不存在")
    return wafer


@router.get("")
def list_wafers(lot_id: int | None = None, db: Session = Depends(get_db)):
    q = db.query(Wafer).order_by(Wafer.lot_id, Wafer.wafer_number)
    if lot_id is not None:
        q = q.filter(Wafer.lot_id == lot_id)
    return [{"id": w.id, "lot_id": w.lot_id, "lot_name": w.lot.name,
             "wafer_number": w.wafer_number,
             "die_rows": w.die_rows, "die_cols": w.die_cols,
             **wafer_stats(db, w)} for w in q.all()]


@router.post("", status_code=201)
def create_wafer(payload: WaferCreate, db: Session = Depends(get_db)):
    if not db.get(Lot, payload.lot_id):
        raise HTTPException(404, "批次不存在")
    dup = db.query(Wafer).filter(Wafer.lot_id == payload.lot_id,
                                 Wafer.wafer_number == payload.wafer_number).first()
    if dup:
        raise HTTPException(409, "该批次下晶圆编号已存在")
    wafer = Wafer(**payload.model_dump())
    db.add(wafer)
    db.commit()
    db.refresh(wafer)
    return {"id": wafer.id, "lot_id": wafer.lot_id,
            "wafer_number": wafer.wafer_number,
            "die_rows": wafer.die_rows, "die_cols": wafer.die_cols,
            **wafer_stats(db, wafer)}


@router.get("/{wafer_id}/map")
def wafer_map(wafer_id: int, db: Session = Depends(get_db)):
    """晶圆分布图数据：网格尺寸 + 失效管芯 + 缺陷明细 + 良率。"""
    wafer = _get_wafer_or_404(db, wafer_id)
    defects = db.query(Defect).filter(Defect.wafer_id == wafer_id).all()

    die_map: dict[tuple[int, int], list] = {}
    for d in defects:
        die_map.setdefault((d.x, d.y), []).append(d)

    return {
        "wafer_id": wafer.id,
        "lot_id": wafer.lot_id,
        "lot_name": wafer.lot.name,
        "wafer_number": wafer.wafer_number,
        "die_rows": wafer.die_rows,
        "die_cols": wafer.die_cols,
        **wafer_stats(db, wafer),
        "dies": [{"x": x, "y": y, "defect_count": len(ds),
                  "types": sorted({d.defect_type.code for d in ds})}
                 for (x, y), ds in sorted(die_map.items())],
        "defects": [{"x": d.x, "y": d.y, "code": d.defect_type.code,
                     "name": d.defect_type.name, "color": d.defect_type.color}
                    for d in defects],
    }


@router.get("/{wafer_id}/clusters")
def wafer_clusters(wafer_id: int,
                   eps: float = Query(3.0, gt=0, le=50,
                                      description="邻域半径（管芯数）"),
                   min_samples: int = Query(4, ge=2, le=100,
                                            description="核心点最小邻居数"),
                   db: Session = Depends(get_db)):
    """DBSCAN 聚集识别，返回簇列表及模式分类。"""
    wafer = _get_wafer_or_404(db, wafer_id)
    defects = db.query(Defect).filter(Defect.wafer_id == wafer_id).all()
    if not defects:
        return {"wafer_id": wafer_id, "params": {"eps": eps, "min_samples": min_samples},
                "total_defects": 0, "cluster_count": 0, "noise_count": 0,
                "clusters": []}

    points = np.array([[d.x, d.y] for d in defects], dtype=float)
    type_codes = [d.defect_type.code for d in defects]
    labels = dbscan(points, eps, min_samples)
    center = ((wafer.die_cols - 1) / 2, (wafer.die_rows - 1) / 2)
    radius = min(wafer.die_rows, wafer.die_cols) / 2
    clusters = analyze_clusters(points, labels, type_codes, center, radius)

    return {
        "wafer_id": wafer_id,
        "params": {"eps": eps, "min_samples": min_samples},
        "total_defects": len(defects),
        "cluster_count": len(clusters),
        "noise_count": int((labels == -1).sum()),
        "clusters": clusters,
    }
