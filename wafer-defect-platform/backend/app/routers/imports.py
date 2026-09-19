"""数据导入接口：CSV 文件上传 / JSON 记录 / 演示数据。"""
import csv
import io

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Defect, DefectType, Lot, Wafer
from ..schemas import DefectRecord, ImportResult
from ..seed import seed_demo

router = APIRouter(prefix="/api", tags=["import"])

REQUIRED_COLUMNS = {"lot", "wafer", "die_x", "die_y"}


def import_records(records: list[DefectRecord], die_rows: int, die_cols: int,
                   db: Session) -> ImportResult:
    """统一导入逻辑：自动建批次/晶圆，未知缺陷类型归入 UNK。"""
    type_ids = {t.code: t.id for t in db.query(DefectType).all()}
    unk_id = type_ids.get("UNK")
    lot_cache = {l.name: l for l in db.query(Lot).all()}
    wafer_cache = {(w.lot_id, w.wafer_number): w for w in db.query(Wafer).all()}

    imported = skipped = lots_created = wafers_created = 0
    errors: list[str] = []

    for i, rec in enumerate(records, start=1):
        if rec.die_x >= die_cols or rec.die_y >= die_rows:
            skipped += 1
            errors.append(f"第{i}行：坐标({rec.die_x},{rec.die_y})超出"
                          f"{die_cols}x{die_rows}网格")
            continue

        lot = lot_cache.get(rec.lot)
        if not lot:
            lot = Lot(name=rec.lot)
            db.add(lot)
            db.flush()
            lot_cache[rec.lot] = lot
            lots_created += 1

        key = (lot.id, rec.wafer)
        wafer = wafer_cache.get(key)
        if not wafer:
            wafer = Wafer(lot_id=lot.id, wafer_number=rec.wafer,
                          die_rows=die_rows, die_cols=die_cols)
            db.add(wafer)
            db.flush()
            wafer_cache[key] = wafer
            wafers_created += 1

        code = (rec.defect_code or "UNK").upper()
        type_id = type_ids.get(code, unk_id)
        if type_id is None:
            skipped += 1
            errors.append(f"第{i}行：缺陷类型字典为空")
            continue
        db.add(Defect(wafer_id=wafer.id, x=rec.die_x, y=rec.die_y,
                      defect_type_id=type_id))
        imported += 1

    db.commit()
    return ImportResult(rows_total=len(records), defects_imported=imported,
                        lots_created=lots_created, wafers_created=wafers_created,
                        rows_skipped=skipped, errors=errors[:50])


@router.post("/import/csv", response_model=ImportResult)
async def import_csv(file: UploadFile,
                     die_rows: int = Query(20, ge=1, le=200),
                     die_cols: int = Query(20, ge=1, le=200),
                     db: Session = Depends(get_db)):
    """导入 CSV。必需列：lot, wafer, die_x, die_y；可选列：defect_code。"""
    raw = await file.read()
    text = raw.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    header = {h.strip() for h in (reader.fieldnames or [])}
    missing = REQUIRED_COLUMNS - header
    if missing:
        raise HTTPException(422, f"CSV 缺少必需列: {sorted(missing)}")

    records, parse_errors = [], []
    for lineno, row in enumerate(reader, start=2):  # 第1行为表头
        try:
            records.append(DefectRecord(
                lot=row["lot"].strip(),
                wafer=int(row["wafer"]),
                die_x=int(row["die_x"]),
                die_y=int(row["die_y"]),
                defect_code=(row.get("defect_code") or "UNK").strip().upper(),
            ))
        except (ValueError, AttributeError) as e:
            parse_errors.append(f"第{lineno}行解析失败: {e}")
    result = import_records(records, die_rows, die_cols, db)
    result.errors = parse_errors + result.errors
    result.rows_total += len(parse_errors)
    result.rows_skipped += len(parse_errors)
    return result


@router.post("/import/json", response_model=ImportResult)
def import_json(records: list[DefectRecord],
                die_rows: int = Query(20, ge=1, le=200),
                die_cols: int = Query(20, ge=1, le=200),
                db: Session = Depends(get_db)):
    """导入 JSON 记录数组，字段同 DefectRecord。"""
    return import_records(records, die_rows, die_cols, db)


@router.post("/demo/seed")
def create_demo_data(db: Session = Depends(get_db)):
    """生成演示数据（幂等）。"""
    return seed_demo(db)
