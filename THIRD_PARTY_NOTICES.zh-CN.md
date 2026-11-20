# 第三方代码说明

[English](THIRD_PARTY_NOTICES.md) | 中文

> 英文版 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) 的中文版。涉及许可证的内容以英文版和许可证原文为准。

## RAGFlow

`backend/termpilot/knowledge/engine/` 中的代码改编自 [RAGFlow](https://github.com/infiniflow/ragflow) v0.16.0，
版权归 The InfiniFlow Authors 所有（Copyright 2024-2025），以 Apache License 2.0 授权。
许可证全文见 [`LICENSES/Apache-2.0.txt`](LICENSES/Apache-2.0.txt)。

每个改编过的文件都保留了原来的版权声明，并注明了该文件经过修改。

| 上游路径 | 在本项目中的位置 |
| --- | --- |
| `deepdoc/parser/*`（docx、excel、html、json、markdown、pdf、ppt、txt、utils） | `engine/parser/` |
| `deepdoc/vision/*`（OCR、版面分析、表格结构、算子、后处理） | `engine/vision/` |
| `rag/nlp/{__init__,query,rag_tokenizer,search,synonym,term_weight}.py` | `engine/nlp/` |
| `rag/utils/__init__.py` | `engine/utils.py` |
| `rag/utils/{doc_store_conn,es_conn}.py` | `engine/store/` |
| `rag/app/naive.py` | `engine/chunker.py` |
| `conf/mapping.json` | `engine/store/es_mapping.json` |

我做的修改：

- import 路径都移到了 `termpilot.knowledge.engine` 下。模型、词典和索引 mapping 的位置由 `engine/runtime.py` 提供，
  不再依赖 RAGFlow 的项目目录。
- Elasticsearch 连接从运行时配置里读取地址和账号密码，连不上时直接报错，不再重试两分钟。索引名前缀可以配置。
- 切块逻辑不再依赖 Apache Tika（所以不支持旧版 `.doc` 文件）。PowerPoint（`.pptx`）通过已有的幻灯片解析器支持，Markdown 文件按 UTF-8 读取。
- 没装 `datrie` 扩展时，分词器会退回到纯 Python 实现的 trie（`engine/simple_trie.py`）。
- 删掉了 Python 2 兼容代码（`six`）、命令行测试脚本和视觉模块的命令行工具。
- 把唯一一条中文代码注释（在 `nlp/term_weight.py` 里）改成了英文。
- `engine/runtime.py`、`engine/fields.py` 和 `engine/simple_trie.py` 是新增的文件。

模型权重不在这个仓库里。`backend/scripts/fetch_models.py` 会从 Hugging Face 的 `InfiniFlow/deepdoc` 和
`InfiniFlow/text_concat_xgb_v1.0` 仓库下载模型，分词词典从 RAGFlow 仓库下载，它们各自的许可证同样适用。

## 校园代码表

`backend/termpilot/campus/codebook.json` 把教务系统里出现的院系、书院和班级代码对应到公开的名称。
