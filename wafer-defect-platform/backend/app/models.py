"""SQLAlchemy ORM 模型。

领域模型：
- Lot（批次）→ Wafer（晶圆）→ Defect（缺陷点）
- DefectType（缺陷类型字典）
- 晶圆被抽象为 die_rows × die_cols 的管芯网格，缺陷落在管芯坐标 (x, y) 上。
"""
from sqlalchemy import (Column, DateTime, ForeignKey, Integer, String,
                        UniqueConstraint, func)
from sqlalchemy.orm import relationship

from .database import Base


class Lot(Base):
    __tablename__ = "lots"

    id = Column(Integer, primary_key=True)
    name = Column(String(64), unique=True, nullable=False, index=True)
    product = Column(String(64), default="")
    created_at = Column(DateTime, server_default=func.now())

    wafers = relationship("Wafer", back_populates="lot",
                          cascade="all, delete-orphan", order_by="Wafer.wafer_number")


class Wafer(Base):
    __tablename__ = "wafers"

    id = Column(Integer, primary_key=True)
    lot_id = Column(ForeignKey("lots.id", ondelete="CASCADE"), nullable=False, index=True)
    wafer_number = Column(Integer, nullable=False)
    die_rows = Column(Integer, nullable=False, default=20)
    die_cols = Column(Integer, nullable=False, default=20)

    lot = relationship("Lot", back_populates="wafers")
    defects = relationship("Defect", back_populates="wafer", cascade="all, delete-orphan")

    __table_args__ = (UniqueConstraint("lot_id", "wafer_number", name="uq_lot_wafer"),)


class DefectType(Base):
    __tablename__ = "defect_types"

    id = Column(Integer, primary_key=True)
    code = Column(String(16), unique=True, nullable=False)
    name = Column(String(64), nullable=False)
    color = Column(String(16), default="#999999")
    severity = Column(Integer, default=1)  # 1 轻微 ~ 5 严重


class Defect(Base):
    __tablename__ = "defects"

    id = Column(Integer, primary_key=True)
    wafer_id = Column(ForeignKey("wafers.id", ondelete="CASCADE"), nullable=False, index=True)
    x = Column(Integer, nullable=False)  # 管芯列坐标 0..die_cols-1
    y = Column(Integer, nullable=False)  # 管芯行坐标 0..die_rows-1
    defect_type_id = Column(ForeignKey("defect_types.id"), nullable=False)

    wafer = relationship("Wafer", back_populates="defects")
    defect_type = relationship("DefectType")
