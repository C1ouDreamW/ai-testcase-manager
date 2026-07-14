# AI TestCase Manager

AI 驱动的测试用例管理系统，从需求文档自动生成测试用例，内置质量审核与离线评测。

## 技术栈

<p align="center">
  <img src="https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white" />
  <br/>
  <img src="https://img.shields.io/badge/SQLAlchemy-2.0-D71F00?logo=sqlalchemy&logoColor=white" />
  <img src="https://img.shields.io/badge/SQLite-003B57?logo=sqlite&logoColor=white" />
  <img src="https://img.shields.io/badge/ChromaDB-5B21B6?logo=chromadb&logoColor=white" />
  <img src="https://img.shields.io/badge/LLM-OpenAI%20Compatible-412991?logo=openai&logoColor=white" />
  <img src="https://img.shields.io/badge/Pydantic-v2-E92063?logo=pydantic&logoColor=white" />
  <br/>
  <img src="https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black" />
  <img src="https://img.shields.io/badge/Vite-646CFF?logo=vite&logoColor=white" />
</p>

## 项目结构

```
├── backend/
│   └── app/
│       ├── api/          # 8 个 Router，43 个端点
│       ├── models/       # 12 张数据表，自动迁移
│       ├── schemas/      # Pydantic 请求/响应模型
│       ├── services/     # 核心业务逻辑（生成管道 / 评测引擎 / RAG / 质量检查）
│       └── skills/       # 插件式 AI 技能系统
├── frontend/             # 8 个页面，5 步生成向导
└── .env.example
```

## 核心功能

### AI 用例生成

```
需求文档 → AI 解析 → 功能点确认 → 多技能生成 → 质量审核 → 人机审核确认
                ↑                             │
                └── 知识库 RAG 注入 ←──────────┘
```

- 上传 Word/Markdown 或粘贴文本，AI 自动解析为结构化功能点
- 支持完整覆盖与快速冒烟两种策略，RAG 知识库增强生成质量

### 插件式技能系统

每个技能是独立目录（`skill.yaml` + `handler.py` + `prompt.md`），自动发现与调度：

| 技能 | 类型 | 功能 |
|------|------|------|
| `case_writer` | 核心 | 按功能点生成测试用例 |
| `requirement_parser` | 核心 | PRD 解析为结构化功能列表 |
| `case_judge` | 质量 | AI 评分 + 幻觉检测 |
| `test_proposal` | 工具 | 测试范围与风险建议 |
| `api_test` | 专项 | 接口测试用例 |
| `security` | 专项 | 安全/权限测试用例 |

### 质量审核管道

规则检查 → 重复检测 → AI 打分（相关性/可执行性/可验证性） → 幻觉检测 → 聚合报告

生成的用例以草稿形式展示，支持逐条采纳/拒绝/编辑，统计通过率。

### 离线评测系统

创建评测样本（需求 + 人工黄金检查点），运行生成管道后计算 5 项指标：成功率、可用率、召回率、重复率、幻觉数。支持多轮评测并行对比。

### RAG 知识库

上传业务文档，ChromaDB 向量化，生成时语义检索相关知识注入 Prompt。支持 Mock 模式离线开发。

### 多模型配置

生成模型 / 评测模型 / 嵌入模型独立配置，支持 13 种厂商预设，避免自评偏差。

## 快速开始

### 后端

```bash
cd backend
uv sync
cp ../.env.example ../.env    # 填写 API Key，或设 LLM_MOCK_MODE=true 体验 Mock 模式
uv run uvicorn app.main:app --reload --port 8000
```

### 前端

```bash
cd frontend
npm install
npm run dev
```

打开 `http://localhost:5173`，代理自动转发 `/api` 到后端。启动后访问 `/docs` 查看 Swagger API 文档。

## 项目亮点

- **插件式技能架构** — 新增 AI 技能只需 3 个文件，自动注册调度
- **RAG 增强生成** — ChromaDB 语义检索 + 分块，业务知识注入减少幻觉
- **自建评测基准** — 离线评测 + 多指标对比，量化生成质量
- **人机协同** — 草案审核流程保留人类决策，避免全自动失控
- **多模型解耦** — 生成/评测/嵌入独立配置，支持任意 OpenAI 兼容 API
