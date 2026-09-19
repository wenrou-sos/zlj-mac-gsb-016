"""数据库引擎与会话管理。

默认引擎基于 settings.DATABASE_URL；测试可通过 app 工厂注入独立引擎。
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool

from .config import settings

Base = declarative_base()


def make_engine(database_url: str):
    """根据 URL 创建引擎，SQLite 内存库使用 StaticPool 保证多连接共享同一库。"""
    kwargs = {"pool_pre_ping": True}
    if database_url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
        if database_url in ("sqlite://", "sqlite:///:memory:"):
            kwargs["poolclass"] = StaticPool
    return create_engine(database_url, **kwargs)


engine = make_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db():
    """FastAPI 依赖：请求级数据库会话。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
