# 接口文档

[English](api.md) | 中文

> 英文版 [api.md](api.md) 的中文版，内容有出入时以英文版为准。

后端跑起来之后，FastAPI 会在 `/docs`（Swagger UI）和 `/redoc` 提供交互式文档，那边永远和代码保持一致。
这一页是简化版，另外补充一些在 Swagger 里看不太出来的约定。

## 通用约定

- 所有接口都在 `/api` 下，除非特别说明，请求和响应都是 JSON。
- 认证：请求头带 `Authorization: Bearer <token>`，token 从 `POST /api/auth/session` 拿。有效期是
  `TP_TOKEN_TTL_MINUTES`（默认 12 小时）。调用 `DELETE /api/auth/session` 会让这个账号的所有 token 一起失效。
- 错误响应的格式固定是：

  ```json
  {"error": {"code": "not_found", "message": "...", "details": null}}
  ```

  常见的 code：`invalid_input`（422），`not_authenticated`、`invalid_credentials`、`campus_session_expired`（401），
  `not_found`（404），`conflict`（409），`upstream_failure`（502），`feature_unavailable`（503）。
- 时间戳用带时区偏移的 ISO 8601。一天中的时间用 `HH:MM`。星期用 1（周一）到 7（周日）。

## 账号

| 方法 | 路径 | 作用 |
| --- | --- | --- |
| GET | `/config` | 公开的功能开关：`demo_mode`、`assistant`、`library`、`web_search` |
| POST | `/auth/session` | 用 `{username, password}` 登录，返回 `{token, expires_in, first_visit, student}` |
| DELETE | `/auth/session` | 在所有设备上退出登录 |
| GET、PATCH | `/me` | 个人信息。PATCH 可以改 `interests`、`term_start`，或者传 `clear_term_start` 清空开学日期 |
| GET | `/me/term` | 当前学期：`today`、`label`、`start`、`end`、`weeks`、`current_week`、`in_session` |
| GET | `/me/photo` | 头像，格式是 `{data_url}` |

## 日程

| 方法 | 路径 | 作用 |
| --- | --- | --- |
| GET | `/briefing` | 今日页的数据：今天的课、下一节课、快到期的、已逾期的、冲突、各种计数和提示 |
| GET | `/timetable` | `{term, entries, clashes}` |
| POST、PATCH、DELETE | `/timetable`、`/timetable/{id}` | 管理课表记录（`title`、`kind`、`weekday`、`starts_at`、`ends_at`、`weeks`、`location` 等） |
| GET | `/tasks?status=open\|done\|all` | 按截止时间排序的任务 |
| POST、PATCH、DELETE | `/tasks`、`/tasks/{id}` | 管理任务。`due_at` 必须带时区偏移 |
| POST | `/planner/suggestions` | 传 `{days, block_minutes, day_start, day_end}`，返回建议的复习时段 |
| POST | `/planner/accept` | 传 `{blocks: [{task_id, day, starts_at, ends_at}]}`，返回创建好的课表记录 |
| GET | `/calendar/link` | 私有订阅链接，有效期 180 天，或者到退出登录为止 |
| GET | `/calendar/feed.ics?token=...` | iCalendar 订阅内容。不需要 Bearer 请求头，token 就在链接里 |

## 校园数据

| 方法 | 路径 | 作用 |
| --- | --- | --- |
| POST | `/sync` | 执行一次导入。可以传 `{sources: [...]}` 只同步其中几项：`profile`、`grades`、`timetable`、`deadlines`、`coursework`、`materials` |
| GET | `/sync/runs` | 最近几次同步，每个数据源一条结果 |
| GET | `/academics` | GPA、排名、各类学分、按课程分组的作业成绩 |
| GET | `/academics/materials` | 课程文件链接 |

## 邮件

| 方法 | 路径 | 作用 |
| --- | --- | --- |
| GET、PUT、DELETE | `/mail/account` | 查看连接状态 / 用 `{provider, address, secret}` 连接 / 断开 |
| POST | `/mail/sync` | 传 `{folder, limit, unread_only}`，返回 `{fetched, added, updated}` |
| GET | `/mail/messages?folder&unread_only&q&limit` | 邮件列表 |
| GET | `/mail/messages/{id}` | 单封邮件，包含纯文本和 HTML 正文 |
| POST | `/mail/messages/{id}/tasks` | 从这封邮件里找到的截止事项，只返回结果，不会保存 |
| POST | `/mail/send` | `{to, cc, bcc, subject, body}` |

## 助手

| 方法 | 路径 | 作用 |
| --- | --- | --- |
| GET、POST | `/conversations` | 列出对话（可以用 `q` 搜索）或新建对话 |
| GET、PATCH、DELETE | `/conversations/{id}` | 查看问答记录、附件和提案 / 重命名 / 删除 |
| POST | `/conversations/{id}/ask` | 传 `{question, mode: agent\|ask\|research, deep_think}`，返回事件流 |
| POST、DELETE | `/conversations/{id}/attachments`、`.../attachments/{attachment_id}` | 上传附件（multipart，字段名 `file`）或删除附件 |
| GET | `/approvals?state=pending\|all` | 助手提出的操作提案 |
| POST | `/approvals/{id}/decision` | 传 `{approve: true\|false}`，返回提案和执行结果 |

### 回答的事件流

`POST /conversations/{id}/ask` 返回 `text/event-stream`，每个事件的 `data` 都是一个 JSON 对象。

| 事件 | 数据 | 含义 |
| --- | --- | --- |
| `turn` | `{turn_id, conversation_id, mode}` | 一定是第一个事件 |
| `step` | `{id, tool, label, status, detail}` | 工具执行进度：先是 `running`，然后是 `done` 或 `failed` |
| `sources` | `{items: [{index, kind, title, excerpt, url}]}` | 引用资料，回答里用 `[index]` 标注 |
| `reasoning` | `{text}` | 推理模型的思考过程，流式输出 |
| `answer` | `{text}` | 回答正文，流式输出 |
| `approval` | `{id, kind, title, summary, preview, status, expires_at}` | 一个等待你批准的提案 |
| `suggestions` | `{items}` | 推荐的追问 |
| `title` | `{title}` | 对话自动生成了标题 |
| `error` | `{message}` | 出错了。即使出错，事件流最后也一定会有 `done` |
| `done` | `{turn_id}` | 一定是最后一个事件 |

## 资料库和工作区

| 方法 | 路径 | 作用 |
| --- | --- | --- |
| GET | `/library/documents` | `{available, reason, documents}` |
| POST | `/library/documents` | 上传（multipart，字段名 `files`，可以传多个），返回 `{uploaded, failed}` |
| DELETE | `/library/documents/{id}` | 从索引和磁盘上删除 |
| POST | `/library/documents/{id}/study-aid` | 传 `{kind: summary\|quiz\|flashcards}`，返回事件流（`answer`、`error`、`done`） |
| GET | `/workspace/files?folder=.` | `{files, usage_bytes, quota_bytes}` |
| POST | `/workspace/files?folder=.&replace=false` | 上传（multipart，字段名 `file`） |
| GET | `/workspace/download?path=...` | 下载文件 |
| DELETE | `/workspace/files?path=...` | 把文件移到工作区回收站 |

## 健康检查

`GET /health` 返回 `{status, version, database, search, assistant}`。没有配置资料库时 `search` 为 `null`。
