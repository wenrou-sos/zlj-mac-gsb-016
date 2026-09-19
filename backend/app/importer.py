"""导入文件解析：支持 CSV / JSON。

CSV 表头别名（大小写不敏感，支持中英文）：
  批次: batch / lot / lot_id / batch_id / 批次
  晶圆: wafer / wafer_id / wafer_name / 晶圆
  X:   x / x_mm / die_x / col / x坐标 / die_x_index
  Y:   y / y_mm / die_y / row / y坐标 / die_y_index
  缺陷类型: defect / defect_type / defect_code / type / 缺陷类型 / 缺陷 / category
  晶圆直径(可选): diameter / diameter_mm / 直径
"""
import csv
import io
import json

from .analysis import is_defect_label

ALIASES = {
    "batch": {"batch", "lot", "lot_id", "batch_id", "批次", "批次号", "批号"},
    "wafer": {"wafer", "wafer_id", "wafer_name", "晶圆", "晶圆编号", "晶圆id", "wafer_no"},
    "x": {"x", "x_mm", "die_x", "col", "column", "x坐标", "die_x_index", "x_coord", "xpos"},
    "y": {"y", "y_mm", "die_y", "row", "y坐标", "die_y_index", "y_coord", "ypos"},
    "defect": {"defect", "defect_type", "defect_code", "type", "category", "result",
               "缺陷类型", "缺陷", "缺陷代码", "分类", "检测结果"},
    "diameter": {"diameter", "diameter_mm", "直径", "wafer_diameter"},
}

REQUIRED = ("batch", "wafer", "x", "y")


class ImportError_(ValueError):
    pass


def _normalize_header(h):
    return h.strip().lower().lstrip("﻿")


def _map_headers(fieldnames):
    mapping = {}
    for raw in fieldnames or []:
        key = _normalize_header(raw)
        for canonical, names in ALIASES.items():
            if key in names:
                mapping[canonical] = raw
    missing = [c for c in REQUIRED if c not in mapping]
    if missing:
        raise ImportError_(
            f"CSV 缺少必需列：{', '.join(missing)}；"
            f"识别到的列：{', '.join(fieldnames or [])}"
        )
    return mapping


def parse_csv(content: bytes):
    """返回 {"default_batch": ..., "wafers": [{"name","diameter_mm","points":[...]}]}"""
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = content.decode("gbk", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    mapping = _map_headers(reader.fieldnames)
    wafers: dict = {}
    order = []
    default_batch = None
    for lineno, row in enumerate(reader, start=2):
        try:
            x = float(row[mapping["x"]])
            y = float(row[mapping["y"]])
        except (TypeError, ValueError):
            continue  # 跳过坐标非法的空行
        wafer_name = (row.get(mapping["wafer"]) or "").strip() or "W01"
        batch_name = (row.get(mapping["batch"], "") or "").strip() if "batch" in mapping else ""
        if batch_name:
            default_batch = default_batch or batch_name
        dtype_raw = row.get(mapping["defect"], "") if "defect" in mapping else ""
        dtype = (dtype_raw or "").strip() or "GOOD"
        diameter = None
        if "diameter" in mapping:
            try:
                diameter = float(row[mapping["diameter"]])
            except (TypeError, ValueError):
                diameter = None
        w = wafers.setdefault(wafer_name, {"name": wafer_name, "diameter_mm": diameter, "points": []})
        if diameter and not w["diameter_mm"]:
            w["diameter_mm"] = diameter
        w["points"].append({"x_mm": x, "y_mm": y, "defect_type": dtype,
                            "is_defect": is_defect_label(dtype)})
        if wafer_name not in order:
            order.append(wafer_name)
    if not any(w["points"] for w in wafers.values()):
        raise ImportError_("CSV 中未解析到任何有效的检测点位数据")
    return {"default_batch": default_batch, "wafers": [wafers[n] for n in order]}


def parse_json(content: bytes):
    """JSON 格式：
    {"batch": "LOT_A", "product": "...", "wafers": [
       {"name": "W01", "diameter_mm": 300,
        "points": [{"x_mm":..,"y_mm":..,"defect_type":"GOOD"}]}
    ]}
    也兼容 points 直接平铺在顶层。
    """
    try:
        data = json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ImportError_(f"JSON 解析失败：{exc}")
    if not isinstance(data, dict):
        raise ImportError_("JSON 根节点必须是对象")
    wafers_in = data.get("wafers")
    if wafers_in is None and isinstance(data.get("points"), list):
        wafers_in = [{"name": data.get("wafer", "W01"), "points": data["points"]}]
    if not isinstance(wafers_in, list) or not wafers_in:
        raise ImportError_("JSON 必须包含非空的 wafers 数组")
    wafers = []
    for wi, w in enumerate(wafers_in):
        pts = []
        for p in w.get("points", []):
            try:
                x, y = float(p["x_mm"]), float(p["y_mm"])
            except (KeyError, TypeError, ValueError):
                continue
            dtype = str(p.get("defect_type", "GOOD")).strip() or "GOOD"
            pts.append({"x_mm": x, "y_mm": y, "defect_type": dtype,
                        "is_defect": is_defect_label(dtype)})
        if pts:
            wafers.append({
                "name": str(w.get("name") or f"W{wi + 1:02d}"),
                "diameter_mm": w.get("diameter_mm") or data.get("diameter_mm") or 300.0,
                "points": pts,
            })
    if not wafers:
        raise ImportError_("JSON 中未解析到任何有效的检测点位数据")
    return {"default_batch": data.get("batch") or data.get("lot"),
            "product": data.get("product"),
            "wafers": wafers}


def parse_upload(filename: str, content: bytes):
    name = (filename or "").lower()
    if name.endswith(".json"):
        return parse_json(content)
    if name.endswith(".csv"):
        return parse_csv(content)
    # 无明确后缀时尝试 JSON 再 CSV
    try:
        return parse_json(content)
    except ImportError_:
        return parse_csv(content)
