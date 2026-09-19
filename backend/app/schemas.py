from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------- 基础 ----------
class PointOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    x_mm: float
    y_mm: float
    defect_type: str
    is_defect: bool


class WaferOut(BaseModel):
    id: int
    name: str
    diameter_mm: float
    point_count: int
    defect_count: int
    yield_rate: float
    created_at: datetime

    class Config:
        from_attributes = True


class BatchOut(BaseModel):
    id: int
    name: str
    product: Optional[str] = None
    wafer_count: int
    point_count: int
    defect_count: int
    yield_rate: float
    created_at: datetime


# ---------- 分析 ----------
class DefectTypeCount(BaseModel):
    defect_type: str
    count: int


class ClusterOut(BaseModel):
    cluster_id: int
    size: int
    center_x: float
    center_y: float
    spread_mm: float
    defect_density: float
    relative_density: float
    edge_fraction: float
    center_fraction: float
    linear_ratio: Optional[float]
    orientation_deg: float
    pattern: str
    is_anomaly: bool
    severity: str
    defect_types: List[DefectTypeCount]
    point_ids: List[int]


class PatternOut(BaseModel):
    code: str
    name: str
    severity: str
    description: str
    cluster_id: Optional[int] = None


class AnalysisOut(BaseModel):
    total_points: int
    defect_count: int
    yield_rate: float
    defect_rate: float
    defect_type_counts: List[DefectTypeCount]
    cluster_count: int
    anomaly_cluster_count: int
    clusters: List[ClusterOut]
    patterns: List[PatternOut]
    overall_severity: str
    has_anomaly: bool
    params: dict


class WaferMapOut(BaseModel):
    wafer: WaferOut
    analysis: AnalysisOut
    points: List[PointOut]


# ---------- 批次对比 ----------
class BatchCompareWafer(BaseModel):
    id: int
    name: str
    point_count: int
    defect_count: int
    yield_rate: float
    defect_rate: float
    has_anomaly: bool
    overall_severity: str
    patterns: List[str]


class BatchCompareItem(BaseModel):
    batch_id: int
    batch_name: str
    product: Optional[str]
    wafer_count: int
    point_count: int
    defect_count: int
    yield_rate: float
    avg_wafer_yield: float
    yield_stddev: float
    anomaly_wafer_count: int
    severity: str
    defect_type_counts: List[DefectTypeCount]
    wafers: List[BatchCompareWafer]


# ---------- 导入 ----------
class ImportResult(BaseModel):
    batch_id: int
    batch_name: str
    wafer_count: int
    point_count: int
    defect_count: int
    wafers: List[WaferOut]
