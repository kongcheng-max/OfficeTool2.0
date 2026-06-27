"""OfficeTool FastAPI 应用入口"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from core.config import settings
from core.database import close_db, init_db
from core.exceptions import register_exception_handlers

# 预加载解析器注册表
import engine.parser  # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info(f"🚀 {settings.APP_NAME} v{settings.APP_VERSION} 启动中...")
    await init_db()
    logger.info("✅ 数据库表初始化完成")
    yield
    await close_db()
    logger.info("👋 应用已关闭")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册异常处理
register_exception_handlers(app)

# 注册路由
from api.auth import router as auth_router
from api.knowledge_base import router as kb_router
from api.document import router as doc_router
from api.qa import router as qa_router
from api.users import router as users_router

app.include_router(auth_router)
app.include_router(kb_router)
app.include_router(doc_router)
app.include_router(qa_router)
app.include_router(users_router)


@app.get("/api/health")
async def health_check():
    """健康检查"""
    return {"status": "ok", "version": settings.APP_VERSION}
