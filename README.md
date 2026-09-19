# 🔬 晶圆缺陷图谱分析平台（Wafer Defect Map Analysis）

导入检测点位与缺陷类型数据，生成晶圆缺陷分布图（Wafer Map），自动识别空间聚集异常
（局部聚集 / 边缘环 / 中心聚集 / 划伤），并对比不同批次的良率与缺陷结构。

## 功能特性

- **数据导入**：上传 CSV / JSON 文件，支持中英文表头别名与多种良率/缺陷代码（`GOOD`/`OK`/`正常`…）
- **晶圆分布图**：Canvas 绘制 die 网格，按缺陷类型着色，异常簇虚线圈高亮，悬停查看点位信息
- **聚集异常识别**：纯 Python 实现的 **DBSCAN**（网格空间索引）+ **2D PCA** 线性分析
  - 局部高密度簇（cluster）、边缘环缺陷（ring）、中心聚集（center）、划伤/线性缺陷（scratch）
  - 输出簇中心、规模、相对缺陷密度、线性比、方向角、严重程度（高/中/低）
- **批次良率对比**：整体良率、片均良率、片间波动 σ、异常晶圆数、缺陷类型结构、柱状图对比
- **内置演示数据**：3 个批次（LOT-A 正常散点 / LOT-B 边缘环 / LOT-C 中心聚集+划伤），一键生成

## 技术栈

| 层 | 技术 |
|---|---|
| 前端 | Vue 3 + Vite（原生 Canvas 绘图，无重型图表库）+ Nginx |
| 后端 | FastAPI + SQLAlchemy 2 |
| 数据库 | PostgreSQL 16（本地开发/测试自动回退 SQLite） |
| 部署 | Docker Compose（db + backend + frontend 三容器） |
| 测试 | pytest + FastAPI TestClient（32 个测试用例）|

## 快速开始

### 方式一：Docker Compose（推荐，含 PostgreSQL）

```bash
./start.sh            # 构建并启动全部服务，自动写入演示数据
```

启动后访问：

- 前端平台：<http://localhost:8080>
- API 文档（Swagger）：<http://localhost:8000/docs>
- 健康检查：<http://localhost:8000/health>

停止：`./stop.sh`

### 方式二：本地开发模式（SQLite，无需 Docker）

```bash
./start.sh --local    # 后端 :8000，前端 Vite :5173（自动代理 /api）
```

### 运行测试

```bash
./test.sh             # 后端 pytest + 服务启动冒烟 + 前端构建
```

## 数据格式

CSV（表头大小写不敏感，支持别名）：

```csv
batch,wafer,x,y,defect_type
LOT-001,W01,-150,-150,GOOD
LOT-001,W01,-140,-150,GOOD
LOT-001,W01,-130,-140,PARTICLE
LOT-001,W01,-120,-130,SCRATCH
```

支持的列名别名：

| 含义 | 可识别列名 |
|---|---|
| 批次 | `batch` `lot` `lot_id` `批次` |
| 晶圆 | `wafer` `wafer_id` `晶圆` |
| X 坐标(mm) | `x` `x_mm` `die_x` `col` `X坐标` |
| Y 坐标(mm) | `y` `y_mm` `die_y` `row` `Y坐标` |
| 缺陷类型 | `defect_type` `defect` `category` `缺陷类型` |

JSON 格式见 API 文档 `POST /api/import/json`。缺陷类型除 `GOOD/OK/正常/空值` 外均计为缺陷。

## 主要 API

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/health` | 健康检查 |
| GET | `/api/batches` | 批次列表（含良率统计）|
| DELETE | `/api/batches/{id}` | 删除批次 |
| GET | `/api/wafers?batch_id=` | 晶圆列表 |
| GET | `/api/wafers/{id}/map` | 晶圆点位 + 完整聚集分析结果 |
| GET | `/api/batches/compare` | 跨批次良率/异常对比（支持 `?batch_ids=1,2`）|
| POST | `/api/import/file` | 上传 CSV/JSON 文件（multipart）|
| POST | `/api/import/json` | JSON body 直接导入 |
| POST | `/api/admin/seed` | 生成内置演示数据 |

聚类参数可通过环境变量调整：`CLUSTER_EPS`（默认 30mm）、`CLUSTER_MIN_SAMPLES`（默认 5）。

## 目录结构

```
.
├── backend/
│   ├── app/
│   │   ├── main.py        # FastAPI 路由
│   │   ├── analysis.py    # DBSCAN + PCA + 空间模式识别
│   │   ├── importer.py    # CSV/JSON 解析（表头别名）
│   │   ├── seed.py        # 演示数据生成
│   │   ├── models.py      # SQLAlchemy 模型
│   │   └── schemas.py     # Pydantic 模型
│   ├── tests/             # pytest：引擎/解析/API 共 32 例
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.vue
│   │   ├── api.js
│   │   └── components/
│   │       ├── WaferMapCanvas.vue  # 晶圆分布图
│   │       ├── MapView.vue         # 图谱+异常分析页
│   │       ├── CompareView.vue     # 批次对比页
│   │       └── ImportView.vue      # 数据导入页
│   ├── Dockerfile / nginx.conf
│   └── package.json
├── docker-compose.yml
├── start.sh / stop.sh / test.sh
└── README.md
```

## 异常识别算法说明

1. **DBSCAN 聚类**：对缺陷点按空间密度聚类，网格分桶加速邻居查询；
   `eps` 为邻域半径，`min_samples` 为成簇最小点数。
2. **簇密度**：以簇成员空间标准差估算覆盖范围（折算 die 数），
   `相对缺陷密度 = 簇内局部缺陷率 / 晶圆整体缺陷率`，≥1.5x 且簇规模 ≥10 判为异常簇。
3. **划伤识别**：对每个簇做 2D PCA，主/次特征值比 ≥6 且点数 ≥8 判为线性缺陷带。
4. **边缘环**：边缘区域（r ≥ 82%R）缺陷占比 ≥35% 且相对环形面积基线富集 ≥1.3 倍。
5. **中心聚集**：异常簇中心位于 r ≤ 33%R 且成员 60% 以上落在中心区域。
