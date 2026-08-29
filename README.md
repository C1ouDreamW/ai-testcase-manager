# AITC

**AITC**（AI Test Case）是基于 AI 的测试用例生成与管理平台，聚焦「需求结构化 → 功能清单 → RAG 知识增强 → 用例生成 → 质量评测 → 评审入库 → 导出交付」闭环。

## 功能概览

### 已实现

| 模块 | 能力 |
|------|------|
| **账号体系** | 登录 / 注册（可配置开关）、Token 会话、登录失败锁定与注册频控；管理员与普通用户，模型配置按用户隔离 |
| **项目管理** | 创建/编辑项目，首页「继续上次工作」快捷入口 |
| **需求导入** | 粘贴文本、上传 Word（`.docx`）/ Markdown（`.md`），或导入 FeatureList（`.xlsx` / `.md`） |
| **设计稿导入** | 可选上传 PNG / JPG / WebP 并通过独立视觉模型提取页面功能与交互；支持关联 Figma 链接，确认后合并到 FeatureList |
| **FeatureList** | AI 解析 PRD 为功能点；确认页可编辑、展开验收标准/约束；支持导出/导入 Excel 与 Markdown |
| **测试范围** | 功能点表上方「不测范围 / 风险」卡片，支持 AI 生成与手动保存 |
| **用例生成** | 一套 `case_writer` Skill，策略「完整用例 / 快速冒烟」；可选专项 Skill（安全、接口） |
| **知识库 / RAG** | 项目级知识库；Markdown 分块、Embedding 向量化；混合检索（向量 + BM25 关键词 + RRF 融合），可选外部 Rerank 精排；按功能点召回业务规则并注入生成 Prompt |
| **冒烟标签** | 完整用例中核心主路径自动标 `is_smoke`，结果页与测试用例可按「全部 / 冒烟」筛选 |
| **质检与评审** | 规则质检、重复检测、AI Judge、覆盖率统计；人工采纳 / 编辑 / 驳回 / 一键全选 |
| **覆盖矩阵** | 功能点 × 功能/边界/异常 矩阵视图（评审页切换，辅助查漏） |
| **全局测试用例** | 按项目 / 模块 / 功能点浏览；列表与脑图双视图；用例与目录可编辑；脑图全屏 + 缩放 |
| **用例导出** | 生成任务支持导出 Excel / Markdown，可仅导出冒烟用例 |
| **测试任务** | 任务 / 批次（线下、预发、线上等）管理，执行结果标记（通过 / 失败 / 阻塞），通过率进度与缺陷列表 |
| **AI小助手（测试助手 Agent）** | 全局「AI小助手」页 + 项目页悬浮球；只读查询 + 设计稿受控写入（选需求、上传截图/关联 Figma、解析后确认合并）；SSE 流式回答 |
| **AI 评测** | 评测样本与回归运行；统计生成成功率、可用率、场景召回率、重复率、幻觉数、Token 与耗时；支持运行对比 |
| **设置** | 生成、视觉、评测、Embedding、Rerank 模型独立配置；API Key 掩码；Mock 模式 |
| **自动化测试** | pytest + requests 接口自动化，pytest + Playwright + POM UI 自动化，支持隔离环境和离线 Mock |

### 后续演进方向

- 将人工驳回、编辑和线上缺陷自动沉淀为 badcase / 回归知识
- 检索质量离线评测（召回率 / 排序指标基准集）
- 增加 LangGraph 工作流可观测性（节点耗时、失败率、模型调用链路）
- 对接 Jira、禅道、TestRail 等外部项目与用例管理系统

## 六步工作流

产品目标流程（默认短路径，专业能力按需展开）：

```
① 需求/设计稿导入 → ② FeatureList → ③ 用例生成 → ④ 评审入库 → ⑤ 导出 → ⑥ 复盘沉淀
```

| 步骤 | 产物 | 状态 |
|------|------|------|
| ① 需求/设计稿导入 | RequirementDocument + DesignAsset / DesignInsight | ✅ |
| ② FeatureList | 功能点表 + 测试范围卡片 + 清单导入导出 | ✅ |
| ③ 用例生成 | RAG 引用 + 用例草稿 + 规则质检 + AI Judge + 覆盖矩阵 | ✅ |
| ④ 评审入库 | 采纳后的 TestCase | ✅ |
| ⑤ 导出 | 可交付的 Excel / Markdown（支持冒烟筛选） | ✅ |
| ⑥ 复盘沉淀 | 项目知识库 + RAG 检索增强 | ✅ 基础链路 |

向导页当前包含 **五个操作步骤 + 完成页**（导入需求 → 导入设计稿（可跳过）→ 确认功能点 → 选择策略 → 评审采纳 → 完成）。图片设计稿由视觉模型提取可测试功能点，Figma 首版仅保存链接，需同时上传页面截图才能自动解析。

## 技术栈

- **后端**：FastAPI + SQLAlchemy + SQLite（开发）
- **前端**：React + Vite + Ant Design
- **AI**：LangChain（模型适配、Prompt、结构化输出）+ LangGraph（生成工作流、失败恢复）
- **模型协议**：OpenAI 兼容 Chat / 多模态 / Embeddings API（DeepSeek、通义、OpenAI 等）；Rerank 保留轻量 HTTP 适配
- **向量检索**：LangChain OpenAIEmbeddings + LangChain Chroma（项目、端点与 Embedding 模型隔离）
- **文档与导出**：`python-docx` + `openpyxl`
- **自动化测试**：pytest + requests + Playwright + pytest-html

## 前端开发约定

- 本项目定位为桌面端后台管理系统，默认以宽度不低于 `1280px` 的桌面浏览器作为设计和验收基准。
- 后续新增或调整页面无需兼顾手机模式，不要求补充移动端布局、抽屉导航或小屏响应式断点。
- 现有移动端样式暂时保留，但不属于后续功能开发和回归验收范围。

## 快速开始

### 1. 环境

```bash
cp .env.example .env
# 编辑 .env：至少配置生成模型；视觉、评测与 Embedding 模型按需独立配置
# 未配置 LLM_API_KEY 或 LLM_MOCK_MODE=true 时，生成/评分/向量化均可使用 Mock 链路
```

> 环境要求：Python 3.12+ 与 [uv](https://docs.astral.sh/uv/)、Node.js 22+。

### 2. 后端

```bash
cd backend
uv sync --all-groups
uv run uvicorn app.main:app --reload --port 8000
```

### 3. 前端

```bash
cd frontend
npm install
npm run dev
```

### 4. 一键脚本

**macOS / Linux**

```bash
./restart.sh          # 清理端口并后台启动前后端
```

**Windows**（资源管理器中双击，或在 `cmd` 中执行）

```bat
setup.bat             # 首次：uv 同步后端依赖、npm install、生成 .env
start.bat             # 日常：两个窗口分别启动前后端
restart.bat           # 清理 8000/5173 占用后再启动
```

### 5. 从旧版本升级

启动后端时会对本地数据库自动执行增量迁移：

- 首次启动自动创建管理员账号（`.env` 的 `AUTH_USERNAME` / `AUTH_PASSWORD`，默认 `admin / nini123456`），存量项目与配置自动归属该账号
- 模型配置升级为按用户隔离；历史不完整的评测模型配置会被清空并回退到生成模型
- 知识库向量索引格式已升级，旧知识文档会被标记为"需重新上传"，文本内容保留，删除后重新上传即可

### 6. 访问

| 地址 | 说明 |
|------|------|
| http://localhost:5173 | 前端 |
| http://localhost:8000 | 后端 API |
| http://localhost:8000/docs | Swagger 文档 |

前端 `/api` 代理至 `http://localhost:8000`（见 `frontend/vite.config.js`）。

首次访问需登录，默认管理员账号 `admin / nini123456`（由 `.env` 的 `AUTH_USERNAME` / `AUTH_PASSWORD` 初始化，建议修改）；开放注册时也可在登录页自行注册普通账号。

## 生成流程

```
上传需求 / 导入清单
    → AI 拆功能点（或跳过 AI 直接导入 FeatureList）
    → 确认功能点 + 测试范围
    → 选择策略（完整 / 快速冒烟 + 可选专项 Skill + RAG）
    → 按功能点检索知识 → 生成候选用例
    → 规则质检 → 重复检测 → AI Judge → 质量报告
    → 评审页：列表 / 覆盖矩阵 → 采纳 / 编辑 / 驳回
    → 入库至全局测试用例 / 导出 Excel 或 Markdown
```

**策略说明**

- **完整用例**（`full`）：每功能点 5～12 条，覆盖功能、边界、异常；核心主路径标为冒烟
- **快速冒烟**（`quick`）：每功能点 2～4 条，仅核心主路径，省时省成本
- **专项 Skill**（可选）：`security`（安全/权限）、`api_test`（接口测试），按功能点追加生成
- **RAG**（可选）：使用「模块 + 功能点 + 描述」构造查询，从当前项目知识库召回相关内容并注入生成上下文

上述生成主链路由 LangGraph 编排。节点状态只保存任务 ID、功能点 ID 和普通字典，不持有数据库 Session、API Key 或模型客户端；运行检查点默认写入独立的 `backend/data/langgraph_checkpoints.sqlite`。生成中可安全暂停（当前节点完成后生效），失败或已暂停任务可在评审页从最近检查点继续；已落库草稿使用稳定生成键防止重复写入。运行租约防止同一任务并发双跑，Token 按多次运行累加。

## 知识库与 RAG

每个项目拥有独立知识库，支持业务文档、历史用例和缺陷记录等来源。核心链路：

```
文档录入 / 上传
    → 按 Markdown 标题分块（超长内容按句切分）
    → LangChain OpenAIEmbeddings 向量化
    → 写入 LangChain Chroma，同时在 SQLite 保存文本与溯源信息
    → 混合检索：向量 top20 + BM25 关键词 top20 → RRF 融合
    → （可选）外部 Rerank API 精排
    → Top-K 知识片段注入 case_writer / specialist Skill
```

- **混合检索**：向量检索负责语义相近召回，BM25（jieba 分词）负责错误码、专有名词等精确词命中，两路结果用 RRF（倒数排名融合，k=60）合并，双路命中的分块自然靠前
- **Rerank 精排（可选）**：在设置页配置 Rerank 模型（如硅基流动 `BAAI/bge-reranker-v2-m3`）后，融合候选会送外部 `/rerank` 接口做精细相关性排序；未配置或调用失败时自动退化为 RRF 融合结果
- 默认返回 Top 5；向量路过滤低于相似度阈值的结果，BM25 路只保留有关键词命中的分块
- Collection 按「项目 + Embedding 端点 + 模型」隔离，避免跨项目污染和向量维度冲突
- 检索失败不会阻断生成任务，而是自动降级为无知识生成
- 生成任务保存 `knowledge_refs`，可追踪命中的文档、标题路径和相似度；检索测试面板展示每条结果的命中来源（语义 / 关键词 / 双路）

## AI小助手（测试助手 Agent）

提供两个入口：侧边栏第一项「AI小助手」全局页（先选项目再对话），以及项目相关页面右下角的可拖动悬浮球（位置记忆在本地）。可用自然语言询问项目的用例、需求覆盖、测试进度、缺陷与业务规则；也可选择目标需求后上传截图 / 关联 Figma，解析设计功能点并在确认后合并。

```
用户提问（可附设计稿）
    → LangGraph ReAct 循环：模型决策 → 调用工具 → 汇总数据
    → SSE 流式返回（tool_start / tool_end / token / done）
    → 前端实时展示工具过程；解析结果可点「确认合并」
```

- **只读工具**：`search_knowledge`、`list_testcases`、`get_testcase_detail`、`get_coverage_summary`、`get_test_task_stats`、`list_defects`
- **设计稿工具**：`list_requirement_documents`、`list_design_assets`、`parse_design_asset`、`get_design_insights`、`merge_design_insights`（须 `confirmed=true`）；协议固定为「解析 → 展示 → 确认 → 合并」
- **过程透明**：每轮回答展示调用了哪些工具；列表类工具输出做条数与文本截断
- **对话按项目持久化**：含附件快照、目标需求与待确认 insight IDs；Mock 下有设计附件时走解析演示
- 复用设置页的生成模型配置，无需单独配置 Agent 模型

## 质量保障与 AI 评测

生成结果通过四层质量保障：

1. **Prompt 约束**：限定输出结构、字段与测试范围。
2. **规则质检**：标准化步骤，过滤空用例和无意义用例，检查标题、步骤与预期结果。
3. **AI Judge**：从相关性、可执行性、可验证性等维度评分，并标记疑似幻觉。
4. **人工评审**：测试人员采纳、编辑或驳回候选用例，采纳后才进入正式测试用例。

离线评测使用「PRD 原文 + 人工标准测试点」批量执行完整生成链路，主要指标包括：

| 指标 | 口径 |
|------|------|
| 生成成功率 | 评测任务成功且产出用例的样本占比 |
| 可用率 | AI Judge 综合分 ≥ 4 的用例占比 |
| 场景召回率 | 人工标准测试点中被生成用例覆盖的比例 |
| 重复率 | 重复用例数占生成用例总数的比例 |
| 幻觉数 | AI Judge 标记为疑似虚构业务规则的用例数 |
| Token / 耗时 | 评估生成成本和执行性能 |

## AI Skill 架构

Skill 采用 **manifest + handler + prompt** 插件结构，由 `SkillRegistry` 统一发现与调度。

```
backend/app/skills/
├── registry.py / loader.py / base.py   # 注册表
├── shared/                             # LLM、解析、Mock
├── requirement_parser/                 # 需求 → 功能点
├── test_proposal/                      # 测试范围 / 风险建议
├── case_writer/                        # 综合用例（full / quick）
├── security/                           # 专项：安全 / 权限
├── api_test/                           # 专项：接口测试
└── case_judge/                         # AI Judge 评分 / 幻觉判断
```

每个 Skill 目录：

| 文件 | 作用 |
|------|------|
| `skill.yaml` | 元数据：name、category、inputs/outputs、策略等 |
| `prompt.md` 或 `prompts/*.md` | Prompt 正文 |
| `handler.py` | `async def run(inputs, context) -> dict` |

**API**: `GET /api/skills` — 返回 core / specialist / strategies，前端策略页动态渲染。

**新增 Skill**: 复制 specialist 目录 → 编辑 `skill.yaml`（`category: specialist`, `ui.selectable: true`）→ 编写 prompt + handler → 重启后端即可，无需改前端硬编码。

## 目录结构

```
AITC/
├── backend/
│   └── app/
│       ├── api/              # REST 接口
│       ├── models/           # SQLAlchemy 模型
│       ├── schemas/          # Pydantic 模型
│       ├── services/         # 业务逻辑（生成、质检、知识库、评测等）
│       ├── ai/               # LangChain 模型、Embedding、Chroma、结构化输出与 Retriever 适配
│       ├── agent/            # 测试助手 Agent（只读 + 设计稿受控写入 + LangGraph ReAct）
│       ├── skills/           # AI Skill 模块
│       └── workflows/        # LangGraph 工作流与 checkpoint
├── frontend/
│   └── src/
│       ├── components/       # 通用组件（脑图、编辑弹窗、覆盖矩阵等）
│       ├── layouts/          # 布局
│       ├── pages/            # 页面
│       ├── services/         # API 客户端
│       └── utils/            # 工具函数
├── docs/                     # 开发问题与维护文档
├── democase/                 # 示例需求与清单
├── autotest/                 # 接口自动化、UI 自动化、报告与运行脚本
├── restart.sh                # macOS/Linux 一键重启前后端
├── setup.bat / start.bat / restart.bat   # Windows 安装与启动脚本
└── .env.example
```

## 自动化测试

测试工程位于 `autotest/`，使用临时 SQLite / Chroma 目录与 Mock 模式运行，不污染开发数据。

当前包含 **86 条接口自动化 + 21 条 UI 自动化**，覆盖鉴权、项目、需求、设计稿、生成、评审、
知识库、评测、设置等模块，并含 37 条后端单元测试（`backend/tests`）。

```bash
cd autotest
./run_tests.sh api     # 接口自动化
./run_tests.sh ui      # UI 自动化
./run_tests.sh smoke   # 冒烟用例
./run_tests.sh all     # 全量测试，报告输出到 reports/
```

Windows 使用 `run_tests.bat`，参数与上面一致。详细说明见 [`autotest/README.md`](autotest/README.md)。

## 相关文档

- [`docs/PRD.md`](docs/PRD.md)：产品需求与功能边界
- [`docs/环境准备.md`](docs/环境准备.md)：本地环境配置
- [`docs/接口文档.md`](docs/接口文档.md)：主要 API 说明
- [`docs/评测数据/`](docs/评测数据/)：示例评测样本
- [`docs/Bug记录.md`](docs/Bug记录.md)：开发与测试发现的问题
