# 开发笔记

[English](development.md) | 中文

> 英文版 [development.md](development.md) 的中文版，内容有出入时以英文版为准。

写代码时经常要查的一些东西。

## 后端

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt        # 或者 pip install -e ".[dev]"
python scripts/fetch_models.py --skip-ocr  # 分词用的数据；要处理扫描版 PDF 就去掉 --skip-ocr
TP_DEMO_MODE=true python -m termpilot --reload
```

- 所有配置都在 `termpilot/settings.py` 里，每个字段对应一个 `TP_*` 环境变量。嵌套的配置用双下划线，比如
  `TP_MAIL_PROVIDERS__QQ__IMAP_HOST`。
- 没设置 `TP_SECRET_KEY` 的话，第一次启动会生成一个开发用的密钥，存在 `var/secret.key`。
- 默认数据库是 SQLite（`var/termpilot.db`），启动时自动建表。
- 想在没有真实模型服务的情况下改助手相关的代码，可以运行 `python scripts/fake_model_server.py`，再把
  `TP_LLM_BASE_URL` 设成 `http://127.0.0.1:8100/v1`。它也会响应 `/v1/embeddings`，返回固定的向量。

### 测试和代码检查

```bash
pytest                          # 73 个测试，大概 15 秒
ruff check termpilot tests scripts
ruff format termpilot tests scripts
```

测试用的是内存里的 SQLite、演示用的校园网关和一个按脚本回复的对话模型（见 `tests/conftest.py`）。
测试里的时钟固定在秋季学期第 6 周的一个周三，所以和日期有关的逻辑每次跑结果都一样。

`termpilot/knowledge/engine` 是从 RAGFlow 改过来的，保留了原来的代码风格，所以 ruff 不检查这个目录。

### 给助手加一个工具

1. 在 `termpilot/assistant/toolkit.py` 里写一个函数，加上 `@tool(name, label, description, properties, required)` 装饰器。
2. 返回 `ToolOutcome(content, summary)`。如果出了问题、需要让模型知道，就抛一个 `AppError` 的子类。
3. 如果这个工具会改数据，不要在工具里直接改。调用 `ctx.propose(kind=..., payload=...)`，再到
   `termpilot/assistant/approvals.py` 里给这个 `kind` 加一个执行函数。
4. 在 `tests/test_assistant.py` 里用脚本模型写个测试。

### 对接别的学校

实现 `termpilot/campus/gateway.py` 里的 `CampusGateway` protocol，然后在 `build_gateway` 里返回你的实现。
`academic_records.py` 和 `learning_platform.py` 里的解析函数都是纯函数，可以像 `tests/test_campus_parsers.py`
那样，拿保存下来的页面内容直接测。

## 前端

```bash
cd frontend
npm install
npm run dev          # http://localhost:3000，请求发到 NUXT_PUBLIC_API_BASE（默认 http://localhost:8000）
npm test             # vitest
npm run typecheck    # vue-tsc，严格模式
npm run generate     # 静态构建，输出到 .output/public
```

- 在 Windows 上，项目不要放在路径里带 `#` 的文件夹。Vite 会把 `#` 当成 URL 片段，构建会报一些很难看懂的错。
- store 都是显式 import 的（`~/stores/...`）。`app/utils` 里的代码不要用 Nuxt 的 API，不然没法写单元测试。
- 颜色统一用 `app/assets/css/main.css` 里定义的 token（`bg-surface`、`text-muted`、`border-line`、`bg-brand` 等）。
  深色模式基本只是重新定义这些 token，剩下的几个 `dark:` 类只用在品牌色背景上的文字。
