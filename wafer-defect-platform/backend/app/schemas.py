"""Pydantic 请求/响应模型。"""
from pydantic import BaseModel, Field


class LotCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    product: str = ""


class WaferCreate(BaseModel):
    lot_id: int
    wafer_number: int = Field(..., ge=1)
    die_rows: int = Field(20, ge=1, le=200)
    die_cols: int = Field(20, ge=1, le=200)


class DefectRecord(BaseModel):
    """单条缺陷导入记录（JSON 导入 / CSV 行解析后的统一结构）。"""
    lot: str = Field(..., min_length=1)
    wafer: int = Field(..., ge=1)
    die_x: int = Field(..., ge=0)
    die_y: int = Field(..., ge=0)
    defect_code: str = "UNK"


class ImportResult(BaseModel):
    rows_total: int
    defects_imported: int
    lots_created: int
    wafers_created: int
    rows_skipped: int
    errors: list[str] = []
