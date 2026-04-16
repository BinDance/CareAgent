# Elder Care Agent

一个可运行的老年陪护 Agent MVP monorepo，包含：

- `apps/elder-web`：老人语音对话端，浏览器原生 `SpeechRecognition` 和 `speechSynthesis`
- `apps/family-web`：家属控制台，查看摘要、发送通知、上传药方、收发消息
- `apps/api-server`：FastAPI 后端，数据库、调度器、上传、Graph 入口、REST API
- `apps/mcp-server`：真实可运行的 Python MCP server，向 Agent 暴露数据库和业务 tools
- `packages/agent-core`：LangGraph orchestration、LLM provider、prompts、schema、MCP tool executor
- `packages/shared-types` / `packages/ui`：前端共享包

## 技术栈

- 前端：Next.js App Router、React、TypeScript、Tailwind CSS
- 后端：FastAPI、SQLAlchemy 2.x、Pydantic v2、PostgreSQL、Redis、APScheduler
- Agent：LangGraph、LangChain OpenAI-compatible client、LangSmith tracing env 开关
- 模型：默认 Xiaomi MiMo OpenAI-compatible 接口
- 多模态药方解析：图片直接送多模态模型；PDF 先转图片再解析；不确定字段进入待确认/复核

## 目录结构

```text
elder-care-agent/
  apps/
    elder-web/
    family-web/
    api-server/
    mcp-server/
  packages/
    agent-core/
    shared-types/
    ui/
  infra/
    docker/
  docs/
  scripts/
  docker-compose.yml
  .env.example
  README.md
```

## 环境变量

先复制：

```bash
cp .env.example .env
```

核心变量：

- `DATABASE_URL=postgresql+psycopg://postgres:postgres@db:5432/eldercare`
- `REDIS_URL=redis://redis:6379/0`
- `LLM_API_KEY=`
- `LLM_BASE_URL=https://api.xiaomimimo.com/v1`
- `LLM_MODEL=mimo-v2-omni`
- `LANGSMITH_API_KEY=`
- `LANGSMITH_TRACING=false`
- `APP_ENV=development`
- `SECRET_KEY=change-me`
- `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000`

模型说明：

- 默认配置使用 Xiaomi MiMo 官方 OpenAI-compatible endpoint：`https://api.xiaomimimo.com/v1`
- 当前默认模型 `mimo-v2-omni` 支持图片多模态输入，适合本项目的药方图片/PDF 转图解析链路
- `LLM_API_KEY` 需要在 Xiaomi MiMo Open Platform 控制台创建后填入

## 本地开发

### 1. 安装依赖

```bash
sh ./scripts/bootstrap.sh
```

这个脚本会：

- 创建 `.venv`
- 安装 `agent-core`、`api-server`、`mcp-server` 和 `pytest`
- 安装前端 workspace 依赖
- 自动从 `.env.example` 生成 `.env`

### 2. 启动数据库和 Redis

```bash
docker compose up -d db redis
```

### 3. 初始化数据库

```bash
cd apps/api-server
../../.venv/bin/python -m alembic upgrade head
../../.venv/bin/python -m eldercare_api.scripts.seed
cd ../..
```

### 4. 启动全部开发服务

```bash
sh ./scripts/dev.sh
```

启动后：

- 老人端：`http://localhost:3000`
- 家属端：`http://localhost:3001`
- API：`http://localhost:8000`
- MCP Server：`http://localhost:9000/mcp`

### Demo Token

开发默认种子会插入两类演示 token：

- 老人端：`demo-elder-token`
- 家属端：`demo-family-token`

前端默认会带上这两个演示 token。正式环境请替换为真实鉴权流程。

## Docker 使用建议

第一次构建：

```bash
docker compose up --build
```

后续普通启动不要再用 `--build`，直接：

```bash
docker compose up
```

如果容器只是停止过，最快的是：

```bash
docker compose start
```

只在以下情况才需要重新 build：

- Dockerfile 改了
- Python 依赖改了
- 前端依赖改了
- 基础镜像需要刷新

如果只改了 API 代码或前端页面，优先单独重建对应服务：

```bash
docker compose build api-server

docker compose build elder-web family-web
```

Docker 流程会自动：

- 启动 PostgreSQL 和 Redis
- 启动 MCP server
- API 容器执行 `alembic upgrade head`
- 数据库为空时自动写入 demo seed
- 启动两个 Next.js Web 服务

访问地址：

- `http://localhost:3000` 老人端
- `http://localhost:3001` 家属端
- `http://localhost:8000/docs` FastAPI 文档

## Agent Graphs

`packages/agent-core` 已实现以下 LangGraph：

- `ElderConversationGraph`
- `FamilyInstructionGraph`
- `PrescriptionGraph`
- `FamilyRelayGraph`
- `CognitionCareGraph`

关键特性：

- 所有关键 LLM 输出都通过 Pydantic schema 校验
- LLM provider 支持文本和图像输入
- 未配置 `LLM_API_KEY` 时，会自动走 fallback 逻辑，方便本地开发闭环
- Agent 默认通过 MCP tools 访问数据库和业务能力，而不是把业务逻辑写死在前端

## MCP Tools

`apps/mcp-server` 暴露了真实可运行的 tools，包括：

- 画像与状态：`get_elder_profile`、`propose_profile_update`、`get_today_status`、`update_today_status`
- 通知：`create_family_notice`、`list_pending_notices`、`mark_notice_delivered`、`reschedule_notice`
- 药物：`create_medication_plan`、`get_due_medications`、`log_medication_reminder`、`confirm_medication_taken`
- 消息：`send_message_to_family`、`list_family_messages`、`send_message_to_elder`
- 认知与摘要：`get_cognition_history`、`save_cognition_session`、`generate_daily_report`、`publish_report_to_family`
- 安全：`raise_alert`、`request_human_review`

## API 端点

### 老人端

- `POST /api/elder/voice-input`
- `GET /api/elder/session/{elder_id}`
- `GET /api/elder/today-reminders`

### 家属端

- `POST /api/family/notice`
- `POST /api/family/upload-prescription`
- `GET /api/family/dashboard/{elder_id}`
- `GET /api/family/messages/{elder_id}`
- `POST /api/family/message-to-elder`
- `GET /api/family/reports/daily/{elder_id}`

### 内部调度

- `POST /api/internal/run-notice-scheduler`
- `POST /api/internal/run-medication-check`
- `POST /api/internal/run-cognition-check`

## 调度器

系统使用 APScheduler 周期触发：

- 待传达 notice 检查
- 到点 medication 检查
- cognition interaction 检查

调度器只做触发，不写死话术。最终是否提醒、何时转达、怎么说，仍由 Agent 结合画像和上下文决定。

## 数据库与迁移

- ORM：SQLAlchemy 2.x
- 迁移：Alembic
- 初始化迁移：`apps/api-server/alembic/versions/202603310001_init.py`
- 种子：`apps/api-server/eldercare_api/scripts/seed.py`

已包含这些表：

- `users`
- `elders`
- `family_members`
- `elder_profiles`
- `daily_status`
- `family_notices`
- `prescriptions`
- `medication_plans`
- `medication_logs`
- `conversations`
- `family_messages`
- `cognition_sessions`
- `alerts`
- `review_queue`

## 测试

最小测试位于 `apps/api-server/tests`：

- `test_family_notice_flow.py`
- `test_prescription_flow.py`
- `test_elder_relay_message_flow.py`

运行：

```bash
sh ./scripts/test.sh
```

或：

```bash
. .venv/bin/activate
pytest apps/api-server/tests
```

## 当前已验证项

我在当前环境里完成了：

- Python 源码整树 `compileall`
- 启动脚本 `sh -n`
- 关键 `package.json` JSON 校验
- 前端构建错误修复
- Docker 构建缓存优化

当前环境没有宿主机 Docker socket 权限，所以没有直接替你跑完整 `docker compose build`。

## 安全边界

- 本系统不是医疗诊断工具
- 药方解析允许低置信和不确定字段，不会静默自动高风险执行
- 出现 `胸痛`、`呼吸困难`、`跌倒`、`严重意识混乱`、`自杀倾向` 等表达时，Agent 会走 `raise_alert`
- secrets 只从环境变量读取，代码中不硬编码真实 API key
- 当前 auth 是最小可扩展结构，适合 MVP，生产环境需要替换为真正的用户体系和 session/token 管理
