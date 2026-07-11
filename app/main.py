from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI 应用生命周期管理，在启动时初始化数据库。

    Args:
        app (FastAPI): FastAPI 应用实例。
    """
    init_db()
    yield


app = FastAPI(
    title="AiTestCase",
    description="AI测试用例生成与管理平台",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    """健康检查接口，返回服务状态和模拟模式标志。

    Returns:
        dict: 包含 status 和 mock_mode 的字典。
    """
    return {"status": "ok", "mock_mode": settings.use_mock_llm}
