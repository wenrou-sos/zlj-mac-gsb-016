"""测试夹具：使用 SQLite 内存库创建隔离的应用实例。"""
import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture(scope="session")
def client():
    """应用级 TestClient：验证服务能正常启动并建表。"""
    app = create_app("sqlite://")  # 内存库，StaticPool 共享连接
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def csv_payload():
    """构造含聚集图案的 CSV 数据：中心团状 + 散布噪声。"""
    lines = ["lot,wafer,die_x,die_y,defect_code"]
    # 紧密聚集：8 个点集中在 (10,10) 附近
    for dx, dy in [(0, 0), (1, 0), (0, 1), (1, 1), (2, 0), (0, 2), (2, 1), (1, 2)]:
        lines.append(f"LOT-T,1,{10 + dx},{10 + dy},PRT")
    # 散布噪声
    for x, y in [(1, 1), (18, 2), (3, 17), (15, 18), (7, 5)]:
        lines.append(f"LOT-T,1,{x},{y},SCR")
    # 第二片晶圆：仅少量缺陷（高良率对照）
    lines.append("LOT-T,2,5,5,CNT")
    return "\n".join(lines)
