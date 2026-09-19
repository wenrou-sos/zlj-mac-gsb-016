"""CSV / JSON 导入解析测试。"""
import pytest

from app.importer import ImportError_, parse_csv, parse_json, parse_upload


def test_parse_csv_basic():
    csv_data = (
        "batch,wafer,x,y,defect_type\n"
        "LOT1,W01,0,0,GOOD\n"
        "LOT1,W01,10,0,PARTICLE\n"
        "LOT1,W01,0,10,good\n"
        "LOT1,W02,10,10,SCRATCH\n"
    ).encode()
    parsed = parse_csv(csv_data)
    assert parsed["default_batch"] == "LOT1"
    assert [w["name"] for w in parsed["wafers"]] == ["W01", "W02"]
    w01 = parsed["wafers"][0]
    assert len(w01["points"]) == 3
    assert w01["points"][1]["is_defect"] is True
    assert w01["points"][0]["is_defect"] is False
    assert w01["points"][2]["is_defect"] is False  # "good" 小写


def test_parse_csv_chinese_headers():
    csv_data = (
        "批次,晶圆,X坐标,Y坐标,缺陷类型\n"
        "批次甲,W-A,0,0,正常\n"
        "批次甲,W-A,10,10,颗粒\n"
    ).encode("utf-8")
    parsed = parse_csv(csv_data)
    assert parsed["default_batch"] == "批次甲"
    assert parsed["wafers"][0]["points"][1]["defect_type"] == "颗粒"
    assert parsed["wafers"][0]["points"][1]["is_defect"] is True


def test_parse_csv_aliases_lot_die():
    csv_data = (
        "lot_id,wafer_id,die_x,die_y,category\n"
        "L9,W1,0,0,OK\n"
        "L9,W1,1,1,CRACK\n"
    ).encode()
    parsed = parse_csv(csv_data)
    assert len(parsed["wafers"][0]["points"]) == 2
    assert parsed["wafers"][0]["points"][0]["defect_type"] == "OK"
    assert parsed["wafers"][0]["points"][0]["is_defect"] is False


def test_parse_csv_missing_columns():
    with pytest.raises(ImportError_):
        parse_csv(b"foo,bar\n1,2\n")


def test_parse_csv_skips_bad_rows():
    csv_data = (
        "batch,wafer,x,y,defect_type\n"
        "L,W,,,\n"
        "L,W,10,20,GOOD\n"
    ).encode()
    parsed = parse_csv(csv_data)
    assert len(parsed["wafers"][0]["points"]) == 1


def test_parse_json_wafers():
    payload = (
        b'{"batch":"LOT-J","product":"CPU","wafers":['
        b'{"name":"W1","points":['
        b'{"x_mm":0,"y_mm":0,"defect_type":"GOOD"},'
        b'{"x_mm":10,"y_mm":10,"defect_type":"PARTICLE"}]}]}'
    )
    parsed = parse_json(payload)
    assert parsed["default_batch"] == "LOT-J"
    assert parsed["product"] == "CPU"
    assert len(parsed["wafers"]) == 1
    assert parsed["wafers"][0]["points"][1]["is_defect"] is True


def test_parse_json_flat_points():
    payload = b'{"batch":"LOT-F","wafer":"WF","points":[{"x_mm":1,"y_mm":2}]}'
    parsed = parse_json(payload)
    assert parsed["wafers"][0]["name"] == "WF"
    assert parsed["wafers"][0]["points"][0]["defect_type"] == "GOOD"


def test_parse_json_invalid():
    with pytest.raises(ImportError_):
        parse_json(b"{not valid json")
    with pytest.raises(ImportError_):
        parse_json(b'{"foo": 1}')


def test_parse_upload_dispatch():
    parsed = parse_upload("data.json", b'{"batch":"B","wafers":[{"points":[{"x_mm":0,"y_mm":0}]}]}')
    assert parsed["default_batch"] == "B"
    parsed = parse_upload("data.csv", b"batch,wafer,x,y\nB,W,0,0\n")
    assert parsed["default_batch"] == "B"
    with pytest.raises(ImportError_):
        parse_upload("bad.dat", b"garbage garbage")
