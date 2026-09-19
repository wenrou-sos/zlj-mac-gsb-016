"""FastAPI 应用工厂。

create_app() 支持注入数据库 URL，测试可传入 SQLite 内存库实现完全隔离。
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import sessionmaker

from .config import settings
from .database import Base, get_db, make_engine
from .routers import analytics, defects, imports, lots, wafers
from .seed import seed_defect_types, seed_demo


def create_app(database_url: str | None = None,
               seed_demo_data: bool | None = None) -> FastAPI:
    url = database_url or settings.DATABASE_URL
    engine = make_engine(url)
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    app = FastAPI(title="晶圆缺陷图谱分析平台",
                  description="Wafer Defect Map Analysis Platform",
                  version="1.0.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS.split(","),
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 用本实例的会话工厂覆盖全局依赖，保证测试隔离
    def _get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _get_db

    # 初始化字典数据与演示数据
    db = session_factory()
    try:
        seed_defect_types(db)
        if seed_demo_data if seed_demo_data is not None else settings.SEED_DEMO:
            seed_demo(db)
    finally:
        db.close()

    @app.get("/api/health", tags=["meta"])
    def health():
        return {"status": "ok", "service": "wafer-defect-platform"}

    for r in (lots.router, wafers.router, defects.router,
              imports.router, analytics.router):
        app.include_router(r)
    return app


app = create_app()
