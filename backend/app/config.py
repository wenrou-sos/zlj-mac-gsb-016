import os


class Settings:
    # 本地开发默认使用 SQLite；Docker 中通过环境变量切换为 PostgreSQL
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./wafermap.db")
    SEED_DEMO: bool = os.getenv("SEED_DEMO", "").lower() in ("1", "true", "yes", "on")
    # DBSCAN 聚集分析参数（单位 mm，300mm 晶圆 die 间距约 10mm；
    # eps=30 可将对角相邻 die 的划伤链连通，同时不会把随机散点连成簇）
    CLUSTER_EPS: float = float(os.getenv("CLUSTER_EPS", "30"))
    CLUSTER_MIN_SAMPLES: int = int(os.getenv("CLUSTER_MIN_SAMPLES", "5"))


settings = Settings()
