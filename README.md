# ai-agent-py

使用 Python 学习 Agent 开发的示例集，框架用的是 [Pydantic AI](https://pydantic.dev/docs/ai/overview/)。所有示例共用一个虚拟环境，每个脚本都能单独运行。

## 准备

```bash
uv sync                  # 安装依赖（只需一次）
cp .env.example .env     # 填写 API 密钥和地址
```

然后编辑 `providers.toml`，把两个 profile 的 `model` 改成你的接口支持的模型名。

```bash
uv run examples/00_setup_check/main.py                           # 检查默认 profile
LLM_PROFILE=claude-relay uv run examples/00_setup_check/main.py  # 检查 Claude 规范接口
```

`00_setup_check` 会列出当前接口支持的模型名，并发一次真实请求。

## 运行示例

```bash
uv run examples/01_basic_call/01_hello.py
LLM_PROFILE=claude-relay uv run examples/01_basic_call/01_hello.py   # 换来源
LLM_MODEL=deepseek-chat uv run examples/01_basic_call/01_hello.py    # 临时换模型
```

## 目录

| 目录 | 内容 | 详解 |
|---|---|---|
| `src/agentkit/` | 共享包：读取配置、按 profile 创建模型、终端输出。只做这三件事 | |
| `examples/00_setup_check/` | 连通性检查 | |
| `examples/01_basic_call/` | 同步 / 异步调用、指令与模型参数、多轮对话 | [01 基础调用](examples/01_basic_call/README.md) |
| `examples/02_streaming/` | 流式文本、完整事件流、流式多轮聊天 | [02 流式输出](examples/02_streaming/README.md) |
| `examples/03_structured_output/` | pydantic 输出、三种输出模式、校验与重试、流式结构化输出 | [03 结构化输出](examples/03_structured_output/README.md) |

约定：示例之间互不 import；示例里不写密钥、地址和模型名，一律用 `get_model()`。每章的详解放在该章目录下的 `README.md`。

## 模型来源

`providers.toml` 的每个 profile 有三种 `kind`：

| kind | 用途 | Pydantic AI 里的接法 |
|---|---|---|
| `openai-compatible` | 第三方的 OpenAI 规范接口 | `OpenAIChatModel` + `OpenAICompatibleProvider` |
| `anthropic-compatible` | 第三方的 Claude 规范接口 | `AnthropicModel` + 自定义 `base_url` 的 client |
| `official` | 官方 API | 内置 provider（`provider:model`） |

## 常见问题

下面几条多出现在第三方兼容接口上，官方 API 一般不会遇到。

- **401**：Claude 规范接口的密钥会同时放在 `Authorization: Bearer` 和 `x-api-key` 两个头里发送；仍然 401 时检查 `base_url` 是否多写或少写了 `/v1`。
- **`max_tokens` 不生效**：OpenAI 规范接口下，Pydantic AI 发送的是 `max_completion_tokens`，部分接口只认旧的 `max_tokens`。
- **400 提示 system 消息有问题**：run 级追加指令会产生两条 system 消息，部分后端只接受一条。
- **结构化输出失败**：先跑 `examples/03_structured_output/02_output_modes.py` 看当前模型支持哪种模式。

后两类问题都可以通过 Pydantic AI 的 model profile 调整，见官方文档的
[Model profile](https://pydantic.dev/docs/ai/models/compatible-apis/#model-profile) 一节。

## 开发

```bash
uv run ruff format . && uv run ruff check . && uv run pyright
```

Pydantic AI 发版很频繁，版本由 `uv.lock` 锁定；需要新特性时用 `uv lock --upgrade-package pydantic-ai` 升级。
