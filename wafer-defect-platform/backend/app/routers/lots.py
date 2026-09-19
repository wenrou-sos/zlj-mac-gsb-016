"""批次管理接口。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..crud import lot_summary
from ..database import get_db
from ..models import Lot
from ..schemas import LotCreate

router = APIRouter(prefix="/api/lots", tags=["lots"])


@router.get("")
def list_lots(db: Session = Depends(get_db)):
    """批次列表（含良率汇总）。"""
    lots = db.query(Lot).order_by(Lot.id).all()
    return [lot_summary(db, lot) for lot in lots]


@router.post("", status_code=201)
def create_lot(payload: LotCreate, db: Session = Depends(get_db)):
    if db.query(Lot).filter(Lot.name == payload.name).first():
        raise HTTPException(409, f"批次 {payload.name} 已存在")
    lot = Lot(name=payload.name, product=payload.product)
    db.add(lot)
    db.commit()
    db.refresh(lot)
    return lot_summary(db, lot)


@router.get("/{lot_id}")
def get_lot(lot_id: int, db: Session = Depends(get_db)):
    lot = db.get(Lot, lot_id)
    if not lot:
        raise HTTPException(404, "批次不存在")
    return lot_summary(db, lot)


@router.delete("/{lot_id}", status_code=204)
def delete_lot(lot_id: int, db: Session = Depends(get_db)):
    lot = db.get(Lot, lot_id)
    if not lot:
        raise HTTPException(404, "批次不存在")
    db.delete(lot)
    db.commit()
