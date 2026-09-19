from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from .database import Base


class Batch(Base):
    __tablename__ = "batches"

    id = Column(Integer, primary_key=True)
    name = Column(String(128), unique=True, nullable=False, index=True)
    product = Column(String(128), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    wafers = relationship(
        "Wafer", back_populates="batch", cascade="all, delete-orphan"
    )


class Wafer(Base):
    __tablename__ = "wafers"

    id = Column(Integer, primary_key=True)
    batch_id = Column(Integer, ForeignKey("batches.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(128), nullable=False, index=True)
    diameter_mm = Column(Float, nullable=False, default=300.0)
    created_at = Column(DateTime, default=datetime.utcnow)

    batch = relationship("Batch", back_populates="wafers")
    points = relationship(
        "InspectionPoint", back_populates="wafer", cascade="all, delete-orphan"
    )


class InspectionPoint(Base):
    __tablename__ = "inspection_points"

    id = Column(Integer, primary_key=True)
    wafer_id = Column(Integer, ForeignKey("wafers.id", ondelete="CASCADE"), nullable=False, index=True)
    x_mm = Column(Float, nullable=False)
    y_mm = Column(Float, nullable=False)
    defect_type = Column(String(64), nullable=False, default="GOOD")
    is_defect = Column(Boolean, nullable=False, default=False)

    wafer = relationship("Wafer", back_populates="points")
