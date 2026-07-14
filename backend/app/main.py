from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import evaluations, generations, knowledge, projects, requirements, settings as settings_api, skills, testcases
from app.config import settings
from app.database import init_db
from app.services.llm import LLMCallError


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="AITC",
    description="AI 测试用例生成与管理平台",
    version="0.1.0",
    lifespan=lifespan,
)

@app.exception_handler(LLMCallError)
async def llm_error_handler(request: Request, exc: LLMCallError):
    """LLM/Embedding 调用失败（Key 过期、限流、网络等）统一返回中文提示，前端直接展示 detail。"""
    return JSONResponse(status_code=502, content={"detail": str(exc)})


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(skills.router, prefix="/api")
app.include_router(projects.router, prefix="/api")
app.include_router(requirements.router, prefix="/api")
app.include_router(generations.router, prefix="/api")
app.include_router(testcases.router, prefix="/api")
app.include_router(testcases.project_router, prefix="/api")
app.include_router(evaluations.router, prefix="/api")
app.include_router(knowledge.router, prefix="/api")
app.include_router(settings_api.router, prefix="/api")


@app.get("/api/health")
def health():
    return {"status": "ok", "mock_mode": settings.use_mock_llm}
