import time
from typing import List, Optional

from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import Integer, func
from sqlalchemy.orm import Session, joinedload

from . import importer
from .analysis import analyze_wafer
from .config import settings
from .database import Base, SessionLocal, engine, get_db
from .models import Batch, InspectionPoint, Wafer
from .schemas import (
    BatchCompareItem,
    BatchCompareWafer,
    BatchOut,
    ImportResult,
    WaferMapOut,
    WaferOut,
)
from .seed import seed_demo_data

app = FastAPI(title="晶圆缺陷图谱分析平台 API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)
    if settings.SEED_DEMO:
        db = SessionLocal()
        try:
            seed_demo_data(db)
        finally:
            db.close()


# ---------------- 统计辅助 ----------------

def _wafer_stats(db: Session, wafer_id: int):
    total = db.query(func.count(InspectionPoint.id)).filter_by(wafer_id=wafer_id).scalar() or 0
    defects = (
        db.query(func.count(InspectionPoint.id))
        .filter_by(wafer_id=wafer_id, is_defect=True)
        .scalar()
    ) or 0
    return total, defects


def _wafer_out(db: Session, wafer: Wafer) -> WaferOut:
    total, defects = _wafer_stats(db, wafer.id)
    return WaferOut(
        id=wafer.id,
        name=wafer.name,
        diameter_mm=wafer.diameter_mm,
        point_count=total,
        defect_count=defects,
        yield_rate=round(1 - defects / total, 6) if total else 1.0,
        created_at=wafer.created_at,
    )


def _batch_out(db: Session, batch: Batch) -> BatchOut:
    q = (
        db.query(func.count(InspectionPoint.id), func.coalesce(func.sum(
            func.cast(InspectionPoint.is_defect, Integer)
        ), 0))
        .join(Wafer, Wafer.id == InspectionPoint.wafer_id)
        .filter(Wafer.batch_id == batch.id)
    )
    total, defects = q.one()
    return BatchOut(
        id=batch.id,
        name=batch.name,
        product=batch.product,
        wafer_count=len(batch.wafers),
        point_count=total or 0,
        defect_count=int(defects or 0),
        yield_rate=round(1 - int(defects or 0) / total, 6) if total else 1.0,
        created_at=batch.created_at,
    )


def _wafer_analysis(db: Session, wafer: Wafer):
    points = (
        db.query(InspectionPoint)
        .filter_by(wafer_id=wafer.id)
        .order_by(InspectionPoint.id)
        .all()
    )
    point_dicts = [
        {"id": p.id, "x_mm": p.x_mm, "y_mm": p.y_mm,
         "defect_type": p.defect_type, "is_defect": p.is_defect}
        for p in points
    ]
    return analyze_wafer(
        point_dicts,
        radius_mm=wafer.diameter_mm / 2,
        eps=settings.CLUSTER_EPS,
        min_samples=settings.CLUSTER_MIN_SAMPLES,
    )


# ---------------- 健康检查 / 根 ----------------

@app.get("/health")
def health():
    return {"status": "ok", "service": "wafer-defect-map", "time": int(time.time())}


@app.get("/")
def root():
    return {"name": "晶圆缺陷图谱分析平台 API", "docs": "/docs", "health": "/health"}


# ---------------- 批次 ----------------

@app.get("/api/batches", response_model=List[BatchOut], tags=["batches"])
def list_batches(db: Session = Depends(get_db)):
    batches = db.query(Batch).options(joinedload(Batch.wafers)).order_by(Batch.created_at).all()
    return [_batch_out(db, b) for b in batches]


@app.delete("/api/batches/{batch_id}", tags=["batches"])
def delete_batch(batch_id: int, db: Session = Depends(get_db)):
    batch = db.get(Batch, batch_id)
    if not batch:
        raise HTTPException(404, f"批次 {batch_id} 不存在")
    db.delete(batch)
    db.commit()
    return {"deleted": batch_id, "name": batch.name}


# ---------------- 晶圆图谱 ----------------

@app.get("/api/wafers", response_model=List[WaferOut], tags=["wafers"])
def list_wafers(batch_id: Optional[int] = None, db: Session = Depends(get_db)):
    q = db.query(Wafer)
    if batch_id is not None:
        q = q.filter(Wafer.batch_id == batch_id)
    wafers = q.order_by(Wafer.batch_id, Wafer.name).all()
    return [_wafer_out(db, w) for w in wafers]


@app.get("/api/wafers/{wafer_id}/map", response_model=WaferMapOut, tags=["wafers"])
def wafer_map(wafer_id: int, db: Session = Depends(get_db)):
    wafer = db.get(Wafer, wafer_id)
    if not wafer:
        raise HTTPException(404, f"晶圆 {wafer_id} 不存在")
    analysis = _wafer_analysis(db, wafer)
    points = (
        db.query(InspectionPoint)
        .filter_by(wafer_id=wafer.id)
        .order_by(InspectionPoint.id)
        .all()
    )
    return WaferMapOut(wafer=_wafer_out(db, wafer), analysis=analysis, points=points)


# ---------------- 批次良率对比 ----------------

@app.get("/api/batches/compare", response_model=List[BatchCompareItem], tags=["analysis"])
def compare_batches(batch_ids: Optional[str] = Query(None, description="逗号分隔的批次 ID，不传则对比全部"),
                    db: Session = Depends(get_db)):
    query = db.query(Batch).options(joinedload(Batch.wafers)).order_by(Batch.created_at)
    if batch_ids:
        try:
            ids = [int(x) for x in batch_ids.split(",") if x.strip()]
        except ValueError:
            raise HTTPException(400, "batch_ids 必须是逗号分隔的数字")
        query = query.filter(Batch.id.in_(ids))
    batches = query.all()

    items = []
    for batch in batches:
        wafer_views = []
        yields = []
        anomaly_count = 0
        severities = []
        type_counts: dict = {}
        total_all = defect_all = 0
        for wafer in batch.wafers:
            analysis = _wafer_analysis(db, wafer)
            wtotal = analysis["total_points"]
            wdef = analysis["defect_count"]
            wyr = analysis["yield_rate"]
            yields.append(wyr)
            total_all += wtotal
            defect_all += wdef
            if analysis["has_anomaly"]:
                anomaly_count += 1
            severities.append(analysis["overall_severity"])
            for tc in analysis["defect_type_counts"]:
                type_counts[tc["defect_type"]] = type_counts.get(tc["defect_type"], 0) + tc["count"]
            wafer_views.append(BatchCompareWafer(
                id=wafer.id,
                name=wafer.name,
                point_count=wtotal,
                defect_count=wdef,
                yield_rate=wyr,
                defect_rate=analysis["defect_rate"],
                has_anomaly=analysis["has_anomaly"],
                overall_severity=analysis["overall_severity"],
                patterns=[p["code"] for p in analysis["patterns"]],
            ))
        n = len(yields)
        avg = sum(yields) / n if n else 1.0
        stddev = (sum((y - avg) ** 2 for y in yields) / n) ** 0.5 if n else 0.0
        rank = {"high": 3, "medium": 2, "low": 1}
        severity = max(severities, key=lambda s: rank[s]) if severities else "low"
        items.append(BatchCompareItem(
            batch_id=batch.id,
            batch_name=batch.name,
            product=batch.product,
            wafer_count=len(batch.wafers),
            point_count=total_all,
            defect_count=defect_all,
            yield_rate=round(1 - defect_all / total_all, 6) if total_all else 1.0,
            avg_wafer_yield=round(avg, 6),
            yield_stddev=round(stddev, 6),
            anomaly_wafer_count=anomaly_count,
            severity=severity,
            defect_type_counts=[
                {"defect_type": t, "count": c}
                for t, c in sorted(type_counts.items(), key=lambda kv: -kv[1])
            ],
            wafers=wafer_views,
        ))
    return items


# ---------------- 数据导入 ----------------

def _persist_import(db: Session, parsed: dict, batch_name: Optional[str], product: Optional[str]):
    name = batch_name or parsed.get("default_batch") or f"LOT-IMPORT-{int(time.time())}"
    if db.query(Batch).filter_by(name=name).first():
        base = name
        i = 2
        while db.query(Batch).filter_by(name=name).first():
            name = f"{base}-{i}"
            i += 1
    batch = Batch(name=name, product=product or parsed.get("product"))
    db.add(batch)
    db.flush()
    wafer_outs = []
    for w in parsed["wafers"]:
        wafer = Wafer(
            batch_id=batch.id,
            name=w["name"],
            diameter_mm=float(w.get("diameter_mm") or 300.0),
        )
        db.add(wafer)
        db.flush()
        db.bulk_save_objects([
            InspectionPoint(
                wafer_id=wafer.id,
                x_mm=float(p["x_mm"]),
                y_mm=float(p["y_mm"]),
                defect_type=str(p["defect_type"])[:64],
                is_defect=bool(p["is_defect"]),
            )
            for p in w["points"]
        ])
        db.flush()
        wafer_outs.append(_wafer_out(db, wafer))
    db.commit()
    total = sum(w.point_count for w in wafer_outs)
    defects = sum(w.defect_count for w in wafer_outs)
    return ImportResult(
        batch_id=batch.id,
        batch_name=batch.name,
        wafer_count=len(wafer_outs),
        point_count=total,
        defect_count=defects,
        wafers=wafer_outs,
    )


@app.post("/api/import/file", response_model=ImportResult, tags=["import"])
async def import_file(
    file: UploadFile = File(...),
    batch_name: Optional[str] = Query(None),
    product: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """上传 CSV/JSON 文件导入检测点位数据。"""
    content = await file.read()
    if not content:
        raise HTTPException(400, "上传文件为空")
    try:
        parsed = importer.parse_upload(file.filename, content)
    except importer.ImportError_ as exc:
        raise HTTPException(422, str(exc))
    return _persist_import(db, parsed, batch_name, product)


@app.post("/api/import/json", response_model=ImportResult, tags=["import"])
def import_json(payload: dict,
                batch_name: Optional[str] = Query(None),
                product: Optional[str] = Query(None),
                db: Session = Depends(get_db)):
    """直接以 JSON body 导入检测点位数据。"""
    import json
    try:
        parsed = importer.parse_json(json.dumps(payload).encode("utf-8"))
    except importer.ImportError_ as exc:
        raise HTTPException(422, str(exc))
    return _persist_import(db, parsed, batch_name, product)


# ---------------- 演示数据 ----------------

@app.post("/api/admin/seed", tags=["admin"])
def seed_demo(db: Session = Depends(get_db)):
    return seed_demo_data(db)
