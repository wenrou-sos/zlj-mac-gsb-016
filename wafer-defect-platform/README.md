# 晶圆缺陷图谱分析平台

面向半导体制造场景的缺陷数据分析系统：导入检测点位与缺陷类型数据，生成晶圆缺陷分布图，
基于密度聚类自动识别聚集异常（划伤、团状聚集、边缘环状等典型模式），并支持多批次良率对比。

## 功能特性

| 模块 | 说明 |
| --- | --- |
| 数据导入 | CSV 文件上传 / JSON 粘贴导入，自动创建批次与晶圆，越界坐标校验；内置一键演示数据 |
| 晶圆图谱 | 管芯级热力图（良/失效分色）+ 缺陷散点（按类型着色）+ 晶圆边界圆，聚集区域虚线圈选 |
| 聚集识别 | DBSCAN 密度聚类（纯 numpy 实现），参数 ε / min_samples 可调；自动分类模式：团状聚集、线状/划伤、边缘聚集、边缘环状 |
| 良率对比 | 批次平均良率柱状图（含 95% 目标线）、各晶圆良率趋势线、明细数据表 |
| 仪表盘 | 平台 KPI 总览、批次良率排行、缺陷类型帕累托分析 |

## 技术栈

- **前端**：Vue 3 + Vite + Vue Router + ECharts（Nginx 托管生产构建）
- **后端**：FastAPI + SQLAlchemy 2.0 + Pydantic v2 + numpy
- **数据库**：PostgreSQL 16（docker-compose 编排）；本地开发可零依赖回退 SQLite
- **测试**：pytest + FastAPI TestClient（23 个用例：API 端到端 + 聚类算法单元测试）

## 快速开始

### 方式一：Docker（推荐，一键启动）

```bash
./start.sh
```

启动后访问：

- 前端界面：http://localhost:8080
- API 文档（Swagger）：http://localhost:8000/docs

停止服务：`./start.sh --stop`

### 方式二：本地开发（无需 Docker，使用 SQLite）

```bash
./start.sh --local
```

前端开发服务器 http://localhost:5173（热重载），后端 http://localhost:8000。

### 运行测试

```bash
./start.sh --test
# 或手动：
cd backend && pip install -r requirements-dev.txt && python -m pytest
```

## 数据导入格式

CSV 需包含表头，必需列 `lot, wafer, die_x, die_y`，可选列 `defect_code`：

```csv
lot,wafer,die_x,die_y,defect_code
LOT-001,1,5,7,SCR
LOT-001,1,5,8,SCR
LOT-001,1,12,3,CNT
LOT-001,2,9,9,PAT
```

- `die_x` / `die_y`：管芯坐标，范围 `0 ~ 列数-1` / `0 ~ 行数-1`（网格尺寸导入时可指定，默认 20×20）
- `defect_code` 缺省为 `UNK`；内置类型：`SCR` 划痕、`PRT` 颗粒、`CRK` 裂纹、`CNT` 污染、`PAT` 图形缺陷
- 批次/晶圆不存在时自动创建；同一管芯多个缺陷只计一次失效

JSON 导入为同名字段的记录数组，POST 至 `/api/import/json`。

## API 一览

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/health` | 健康检查 |
| GET/POST | `/api/lots` | 批次列表（含良率汇总）/ 创建批次 |
| GET/POST | `/api/wafers` | 晶圆列表 / 创建晶圆 |
| GET | `/api/wafers/{id}/map` | 晶圆分布图数据 |
| GET | `/api/wafers/{id}/clusters?eps=3&min_samples=4` | DBSCAN 聚集分析 |
| POST | `/api/import/csv` · `/api/import/json` | 数据导入 |
| POST | `/api/demo/seed` | 生成演示数据（幂等） |
| GET | `/api/analytics/summary` · `/yield` · `/pareto` | 总览 / 良率对比 / 帕累托 |
| GET | `/api/defect-types` | 缺陷类型字典 |

## 项目结构

```
wafer-defect-platform/
├── docker-compose.yml        # PostgreSQL + 后端 + 前端编排
├── start.sh                  # 一键启动（docker / --local / --test / --stop）
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt / requirements-dev.txt
│   ├── app/
│   │   ├── main.py           # 应用工厂（支持注入测试数据库）
│   │   ├── models.py         # Lot / Wafer / Defect / DefectType
│   │   ├── clustering.py     # DBSCAN + 缺陷模式分类
│   │   ├── crud.py           # 良率统计
│   │   ├── seed.py           # 字典数据 + 演示数据
│   │   └── routers/          # lots / wafers / defects / imports / analytics
│   └── tests/                # pytest：API 端到端 + 聚类算法单元测试
└── frontend/
    ├── Dockerfile            # Vite 构建 + Nginx 托管
    ├── nginx.conf            # SPA 回退 + /api 反向代理
    └── src/views/            # 仪表盘 / 晶圆图谱 / 良率对比 / 数据导入
```

## 环境变量

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `DATABASE_URL` | `sqlite:///./wafer_defect.db` | SQLAlchemy 连接串，compose 中指向 PostgreSQL |
| `SEED_DEMO` | `false`（compose 中为 `true`） | 启动时注入演示数据 |
| `CORS_ORIGINS` | `*` | 允许的跨域来源，逗号分隔 |
