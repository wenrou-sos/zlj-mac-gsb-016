"""应用配置：通过环境变量覆盖默认值。"""
import os


class Settings:
    # 生产环境（docker-compose）使用 PostgreSQL；本地开发缺省回退到 SQLite，便于零依赖启动
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./wafer_defect.db")
    # 启动时是否注入演示数据（3 个批次，含聚集缺陷）
    SEED_DEMO: bool = os.getenv("SEED_DEMO", "false").lower() in ("1", "true", "yes")
    CORS_ORIGINS: str = os.getenv("CORS_ORIGINS", "*")


settings = Settings()
