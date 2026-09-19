"""缺陷类型字典接口。"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import DefectType

router = APIRouter(prefix="/api/defect-types", tags=["defect-types"])


@router.get("")
def list_defect_types(db: Session = Depends(get_db)):
    return [{"code": t.code, "name": t.name, "color": t.color,
             "severity": t.severity}
            for t in db.query(DefectType).order_by(DefectType.severity.desc())]
