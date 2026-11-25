# 01 基础调用

[← 返回总目录](../../README.md)

这一章只做一件事：把一段文字发给模型，拿回一段文字。四个示例依次回答四个问题：

| 示例 | 回答的问题 |
|---|---|
| [01_hello.py](./01_hello.py) | 最少要写几行才能调通一次模型？ |
| [02_async.py](./02_async.py) | 怎么同时发多个请求？ |
| [03_settings.py](./03_settings.py) | 指令和 temperature 这类参数写在哪，谁覆盖谁？ |
| [04_multi_turn.py](./04_multi_turn.py) | 模型怎么「记住」上一轮说了什么？ |

基于 Pydantic AI 2.73.0。文中的输出都是实际运行结果，模型回答的具体文字每次会不同。

## 1. 心智模型

整章只需要记住三个对象：

```
Agent   = 模型 + 指令（+ 工具、输出类型，后面章节再加）   → 配置，无状态，可复用
run     = 用 Agent 处理一次用户输入                      → 一次执行
result  = run 的产物：输出、用量、消息历史                → 数据
```

用熟悉的东西类比：

| Pydantic AI | JS / Rust 里像什么 |
|---|---|
| `Agent` | 一个配置好 baseURL 和拦截器的 axios 实例；或一个不带可变状态的 struct |
| `agent.run(...)` | 用这个实例发一次请求 |
| `result.conversation` | 你自己维护的 `messages: Message[]` 数组，框架帮你打包好了 |

最重要的一点：**Agent 不保存任何对话状态**。它定义成模块级变量，被所有请求共用；对话历史由调用方拿着，每次 run 时传进去。这和你用 Rust 手写时自己维护 `Vec<Message>` 是同一个模型，只是框架把「拼消息、发请求、解析响应」包了起来。

## 2. 前置知识

### 2.1 每个示例开头的三行

```python
from agentkit import console, get_model, header

model = get_model()
agent = Agent(model, instructions="你是一个简洁的助手，用中文回答。")
```

`agentkit` 是本项目 `src/agentkit/` 下的共享包，不是第三方库。三个名字的作用：

| 名字 | 是什么 | 定义在 |
|---|---|---|
| `get_model()` | 读配置，返回一个 Pydantic AI 的模型对象 | [models.py](../../src/agentkit/models.py) |
| `console` | `rich` 库的 `Console` 实例，支持 `[bold]…[/]` 这种样式标记 | [console.py](../../src/agentkit/console.py) |
| `header(title, model)` | 打印一条分隔线，写明示例名和当前模型 | [console.py](../../src/agentkit/console.py) |

`get_model()` 内部分两步：

```python
def get_model(profile: str | None = None, *, model: str | None = None) -> Model:
    return build_model(load_profile(profile, model=model))
```

1. `load_profile`：读 `.env` 和 `providers.toml`，得到一个 `Profile`（纯数据：地址、密钥的变量名、模型名）。
2. `build_model`：按 `profile.kind` 选协议，把 `Profile` 变成可调用的 `Model` 对象。

选哪个 profile 的优先级：**函数参数 > 环境变量 `LLM_PROFILE` / `LLM_MODEL` > `providers.toml` 里的 `default`**。所以示例里不写任何地址、密钥和模型名，换来源只需要改环境变量：

```bash
LLM_PROFILE=claude-relay uv run examples/01_basic_call/01_hello.py
LLM_MODEL=deepseek-chat  uv run examples/01_basic_call/01_hello.py
```

`build_model` 里有一个贯穿全项目的分层，先留个印象：

- **Model** 负责协议：请求和响应长什么样（OpenAI 的 `/chat/completions`，还是 Anthropic 的 `/v1/messages`）。
- **Provider** 负责连接：发到哪个地址、带什么密钥。

### 2.2 本章用到的 Python 语法

| 写法 | 含义 | JS / Rust 对照 |
|---|---|---|
| `"""..."""` 写在文件第一行 | 模块的文档字符串（docstring），不是普通注释，运行时能通过 `__doc__` 读到 | 文件顶部的 JSDoc / `//!` |
| `def main() -> None:` | `-> None` 是返回类型注解，只给类型检查器看，运行时不校验 | `function main(): void` / `fn main()` |
| `if __name__ == "__main__":` | 这个文件被直接运行时才执行；被别的文件 `import` 时不执行 | Node 的 `require.main === module` |
| `f"用量：{result.usage}"` | f-string，花括号里是表达式 | 模板字符串 `` `用量：${x}` `` / `format!` |
| `f"{elapsed:.1f}"` | 冒号后是格式说明，`.1f` 表示保留 1 位小数 | `x.toFixed(1)` / `{:.1}` |
| `(f(q) for q in QUESTIONS)` | 生成器表达式，惰性产出每一项 | `QUESTIONS.iter().map(f)` |
| `gather(*items)` | `*` 把可迭代对象展开成位置参数 | 展开运算符 `gather(...items)` |
| `zip(a, b, strict=True)` | 按位置配对；`strict=True` 时长度不一致会报错，而不是截断到较短的那个 | `a.iter().zip(b)`（Rust 的 zip 会截断） |
| `type(x).__name__` | 取对象的类名字符串 | `x.constructor.name` |
| `", ".join(items)` | 用分隔符拼接字符串，注意是分隔符调用 `join` | `items.join(", ")` |
| `ModelSettings(temperature=0.2)` | `ModelSettings` 是 `TypedDict`：运行时就是普通 `dict`，类型只在检查期存在 | TS 的 `interface`，所有字段可选 |

## 3. 示例讲解

### 3.1 [01_hello.py](./01_hello.py)：最小的一次调用

```bash
uv run examples/01_basic_call/01_hello.py
```

```python
model = get_model()
agent = Agent(model, instructions="你是一个简洁的助手，用中文回答。")


def main() -> None:
    # run_sync 是 run 的同步包装，脚本里用最方便
    result = agent.run_sync("用一句话解释什么是 AI Agent")

    print(result.output)  # 最终输出，这里是 str
    console.print(f"[dim]用量：{result.usage}[/]")
    console.print(f"[dim]实际响应的模型：{result.response.model_name}[/]")
```

要点：

- **`agent` 定义在模块顶层**，不在 `main` 里。它无状态、可复用，和定义一个路由或一个函数是同一种东西。
- **`instructions`** 就是 system prompt，告诉模型它的角色和约束。
- **`run_sync`** 发一次请求并阻塞到返回。它内部就是 `loop.run_until_complete(self.run(...))`，是异步版 `run` 的包装。
- **`result` 上最常用的三个属性**：

| 属性 | 内容 |
|---|---|
| `result.output` | 最终输出。没指定输出类型时是 `str`，第 3 章会变成 pydantic 对象 |
| `result.usage` | 本次 run 的用量（`RunUsage`）。是属性，不是方法，不加括号 |
| `result.response` | 最后一条模型响应（`ModelResponse`），上面有 `model_name`、`parts` 等 |

实际输出：

```
─────────────────── 01 hello  openai-relay · claude-opus-4-6 ───────────────────
AI Agent 是能够感知环境、自主做出决策并采取行动来达成目标的智能系统。
用量：RunUsage(details={...}, input_tokens=40, output_tokens=48, requests=1)
实际响应的模型：claude-opus-4-6
```

`requests=1` 表示这次 run 只向模型发了一次 HTTP 请求。加了工具之后，一次 run 会包含多次请求，这个数字会变大。

为什么要打印 `result.response.model_name`：它是服务端在响应里返回的模型名。走中转站时，它可能和你请求的名字不一样，这是确认「实际是谁在回答」的直接办法。

### 3.2 [02_async.py](./02_async.py)：异步与并发

```bash
uv run examples/01_basic_call/02_async.py
```

Pydantic AI 本身是异步的，`agent.run()` 才是本体，`run_sync` 只是包装。

#### 单次异步调用

```python
async def main() -> None:
    result = await agent.run(QUESTIONS[2])
    print(result.output)


if __name__ == "__main__":
    asyncio.run(main())
```

两个容易和 JS 混淆的地方：

1. **Python 的协程是惰性的。** `agent.run(...)` 只是创建一个协程对象，此时还没发请求；`await` 才会驱动它执行。这一点像 Rust 的 `Future`，不像 JS 的 `Promise`（创建即开始执行）。
2. **事件循环要手动启动。** `asyncio.run(main())` 是从同步代码进入异步代码的入口：创建事件循环，跑完 `main()` 后关闭。它相当于 tokio 的 `Runtime::block_on` 或 `#[tokio::main]`。JS 没有对应物，因为 JS 的事件循环是运行时自带、一直在跑的。

| | 创建后是否立刻执行 | 事件循环 |
|---|---|---|
| JS `Promise` | 是 | 运行时自带 |
| Rust `Future` | 否，要 `.await` 或 spawn | 手动启动（tokio） |
| Python 协程 | 否，要 `await` 或包装成 Task | 手动启动（`asyncio.run`） |

#### 并发调用

```python
start = time.perf_counter()
results = await asyncio.gather(*(agent.run(q) for q in QUESTIONS))
elapsed = time.perf_counter() - start

for question, r in zip(QUESTIONS, results, strict=True):
    console.print(f"[bold]{question}[/]")
    print(r.output)
```

`gather` 那一行拆成三步看：

1. `(agent.run(q) for q in QUESTIONS)`：生成器表达式，产出 3 个协程对象。此时一个请求都没发出去。
2. `asyncio.gather(*...)`：`*` 把生成器展开成位置参数，等价于 `gather(agent.run(Q[0]), agent.run(Q[1]), agent.run(Q[2]))`。`gather` 把每个协程包装成 Task 并注册到事件循环，3 个请求从这里开始同时在飞。
3. `await`：挂起 `main`，直到 3 个 Task 全部完成，拿到结果列表。

`gather` 的行为和 `Promise.all` / `join_all` 基本一致：

| 行为 | 说明 |
|---|---|
| 结果顺序 | 等于传入顺序，与谁先返回无关 |
| 总耗时 | 约等于最慢的那一个，而不是三者之和 |
| 任一失败 | `await` 立刻抛出第一个异常；**其余 Task 不会被取消**，仍在后台跑完 |
| 想拿到每个的成败 | `gather(..., return_exceptions=True)`，相当于 `Promise.allSettled` |

这是**单线程并发，不是多线程并行**：事件循环在一个线程里轮流推进各个 Task，谁在等网络就切到别人。LLM 调用几乎全是网络等待，所以单线程就够用。

同一个 `agent` 能同时跑多个 run 而互不影响，原因还是第 1 节那句话：Agent 无状态，每次 run 的消息历史是独立的。

`time.perf_counter()` 是高精度单调时钟，专门用来测耗时，相当于 `performance.now()` / `Instant::now()`。

实际输出（并发部分）：

```
Rust 的所有权是什么？
Rust的所有权是管理内存的规则，确保安全且无需垃圾回收。
React 的 hooks 是什么？
React Hooks 是函数组件中操作状态和生命周期的函数。
Python 的 GIL 是什么？
GIL 是全局解释器锁，限制多线程同时执行 Python 字节码。
3 个请求并发耗时 1.8s
```

从这段输出能读出两件事：

- **结果顺序和 `QUESTIONS` 的顺序一致**，与哪个请求先返回无关。
- **3 个请求一共只用了 1.8s**，大约是单个请求的耗时。如果改成 `for` 循环里逐个 `await`，耗时会是三者之和。

并发请求更容易触发中转站的限流，遇到 429 时的处理见 [4.2](#42-并发请求遇到-429)。

### 3.3 [03_settings.py](./03_settings.py)：指令与模型参数

```bash
uv run examples/01_basic_call/03_settings.py
```

```python
agent = Agent(
    model,
    instructions="你是一个取名助手，只输出名字本身，不要解释。",
    # Agent 级默认参数。ModelSettings 是 TypedDict，写成普通 dict 也可以
    model_settings=ModelSettings(temperature=0.2, max_tokens=100),
)

# 1) 用 Agent 级参数
agent.run_sync(PROMPT)

# 2) run 级覆盖 temperature
agent.run_sync(PROMPT, model_settings=ModelSettings(temperature=1.0))

# 3) run 级追加指令
agent.run_sync(PROMPT, instructions="名字必须是中文，两个字。")
```

这个示例讲两条规则，它们的合并方式不一样。

#### 规则一：`model_settings` 是三层覆盖

```
模型对象上的默认值  <  Agent 级  <  单次 run 级
```

合并是按 key 的浅合并，源码里就是字典的 `base | overrides`，等同 JS 的 `{ ...base, ...overrides }`。所以第 2 次调用实际生效的是：

```python
{"temperature": 1.0, "max_tokens": 100}   # temperature 被覆盖，max_tokens 保留
```

常用的 `ModelSettings` 字段：

| 字段 | 作用 |
|---|---|
| `temperature` | 采样随机性。越低越稳定，越高越发散 |
| `max_tokens` | 输出的 token 上限 |
| `top_p` | 核采样阈值，一般和 `temperature` 二选一调 |
| `timeout` | 请求超时（秒） |
| `stop_sequences` | 遇到这些字符串就停止生成 |
| `seed` | 随机种子，部分模型支持 |
| `extra_headers` / `extra_body` | 往请求里加自定义头或字段，对接中转站时偶尔用得上 |

这些是跨厂商的通用字段，但不是每个模型都支持每一项。

#### 规则二：run 级 `instructions` 是追加，不是替换

第 3 次调用时，两段指令都会发给模型。在 OpenAI 规范接口下，实际请求体是这样的（本地 mock 抓取，省略了无关字段）：

```json
{
  "messages": [
    { "role": "system", "content": "你是一个取名助手，只输出名字本身，不要解释。" },
    { "role": "system", "content": "名字必须是中文，两个字。" },
    { "role": "user", "content": "给一个用 Rust 写的命令行 Agent 工具起一个名字" }
  ],
  "max_completion_tokens": 100,
  "temperature": 0.2
}
```

两段指令是**两条独立的 system 消息**，不是拼成一条。记录到消息历史时，`ModelRequest.instructions` 字段里存的是用空行连接后的一个字符串。

顺带能看到 `max_tokens=100` 发出去时字段名变成了 `max_completion_tokens`，这两点都和 [4.4](#44-第三方接口的两个兼容问题) 的兼容问题有关。

实际输出印证了追加的效果。第三次既遵守了 Agent 级的「只输出名字」，也遵守了 run 级的「中文两个字」：

```
───────────────── 03 settings  openai-relay · claude-opus-4-6 ──────────────────
Agent 级参数（temperature=0.2）
Rustler
run 级覆盖（temperature=1.0）
Rustify
run 级追加指令
锈灵
```

对比记忆：

| | 合并方式 | 适合放什么 |
|---|---|---|
| `model_settings` | 同名 key 覆盖 | Agent 级放默认值，run 级放这一次的特殊值 |
| `instructions` | 拼接追加 | Agent 级放角色和固定规则，run 级放这一次的额外要求 |

### 3.4 [04_multi_turn.py](./04_multi_turn.py)：多轮对话

```bash
uv run examples/01_basic_call/04_multi_turn.py
```

```python
first = agent.run_sync("爱因斯坦是谁？一句话回答。")
print(first.output)

# 不传 conversation 的话，模型不知道“他”指谁
second = agent.run_sync("他最著名的公式是什么？", conversation=first.conversation)
print(second.output)
```

模型本身没有记忆，「多轮对话」的实现方式是每次都把完整历史重新发一遍。你用 Rust 手写时是自己往 `Vec<Message>` 里 push，这里换成：

1. 上一次的 `result.conversation` 里已经装好了到目前为止的全部消息；
2. 把它传给下一次 run 的 `conversation=` 参数。

#### `Conversation` 里有什么

| 字段 | 内容 |
|---|---|
| `messages` | 到目前为止的全部消息 |
| `usage` | 整个对话的累计用量 |
| `conversation_id` | 这场对话的 ID，同一场对话的每次 run 共用 |

也可以只传消息列表：`message_history=first.all_messages()`。这是旧写法，仍然可用，但只带消息，会丢掉累计用量和对话 ID。没有特殊理由就用 `conversation=`。

#### 消息结构

```python
for message in second.all_messages():
    parts = ", ".join(type(part).__name__ for part in message.parts)
    console.print(f"{type(message).__name__}: {parts}")
```

Pydantic AI 有一套自己的消息结构，与具体厂商的协议无关。发请求时再由 Model 层翻译成 OpenAI 或 Anthropic 的格式：

```
ModelMessage
├── ModelRequest    发给模型的    parts: UserPromptPart、ToolReturnPart ...
└── ModelResponse   模型返回的    parts: TextPart、ThinkingPart、ToolCallPart ...
```

一条消息由若干个 part 组成，和 Anthropic 协议里一条 message 有多个 content block 是同一个思路。本章只会遇到 `UserPromptPart` 和 `TextPart`，其余的在工具调用等章节出现。

实际输出：

```
──────────────── 04 multi turn  openai-relay · claude-opus-4-6 ─────────────────
爱因斯坦是20世纪最伟大的物理学家，以相对论和质能方程E=mc²而闻名。
---------------------------------------------------------------------
E=mc²，这个公式表示能量等于质量乘以光速的平方，揭示了质量和能量之间的等价关系。
─────────────────────────────────── 消息历史 ───────────────────────────────────
ModelRequest: UserPromptPart
ModelResponse: TextPart
ModelRequest: UserPromptPart
ModelResponse: TextPart
累计用量：RunUsage(details={...}, input_tokens=148, output_tokens=103, requests=2)
```

从这段输出能读出三件事：

- **历史是 请求 / 响应 交替的四条消息**，两轮各占两条。
- **指令不在 parts 里。** 列表里没有 system 相关的 part。`instructions` 存在 `ModelRequest.instructions` 字段上，每次请求时由当前 Agent 重新带上。
- **输入 token 会随轮数增长。** 累计 `input_tokens=148`，而 01 示例里类似长度的单次提问只有 40。原因是第二次请求把第一轮的问答也重新发了一遍。对话越长，每一轮越贵，这是后面要做历史裁剪和压缩的原因。

#### `all_messages()` 与 `new_messages()`

| 方法 | 返回 |
|---|---|
| `result.all_messages()` | 传入的历史 + 本次 run 新产生的消息 |
| `result.new_messages()` | 只有本次 run 新产生的消息 |

对上面的 `second` 来说，`all_messages()` 是 4 条，`new_messages()` 是 2 条。

## 4. 进阶与踩坑

### 4.1 `run_sync` 不能在异步代码里用

`run_sync` 内部要自己驱动事件循环。如果当前线程已经有事件循环在跑（比如在 `async def` 里、Jupyter 里、FastAPI 的异步处理函数里），会报错：

```
RuntimeError: This event loop is already running
```

规则很简单：

| 场景 | 用哪个 |
|---|---|
| 普通脚本、同步函数 | `agent.run_sync(...)` |
| `async def` 内部 | `await agent.run(...)` |

### 4.2 并发请求遇到 429

`gather` 默认是「一个失败就整体抛异常」。3 个请求里只要有 1 个被限流，另外 2 个的结果也拿不到了，虽然它们可能已经成功并计费。

实际使用时有两种处理：

```python
# 1) 每个请求单独看成败，不让一个失败拖垮全部
results = await asyncio.gather(*(agent.run(q) for q in QUESTIONS), return_exceptions=True)
for q, r in zip(QUESTIONS, results, strict=True):
    if isinstance(r, Exception):
        print(f"{q} 失败：{r}")
    else:
        print(r.output)
```

```python
# 2) 用信号量限制同时在飞的请求数
sem = asyncio.Semaphore(2)

async def ask(q: str):
    async with sem:
        return await agent.run(q)

results = await asyncio.gather(*(ask(q) for q in QUESTIONS))
```

`asyncio.Semaphore` 相当于 tokio 的 `Semaphore`。这两段是标准库的通用写法，不在本章示例代码里。

### 4.3 采样参数被拒绝

部分推理模型不接受 `temperature` 等采样参数，中转站可能直接返回 400。遇到时删掉对应参数即可。

### 4.4 第三方接口的两个兼容问题

- **`max_tokens` 不生效**：OpenAI 规范接口下，Pydantic AI 发送的字段名是 `max_completion_tokens`，部分接口只认旧的 `max_tokens`。
- **run 级追加指令报 400**：追加指令会产生两条 system 消息，部分后端只接受一条。

两者都可以通过 Pydantic AI 的 model profile 调整，见根目录 README 的[常见问题](../../README.md#常见问题)。

### 4.5 `instructions` 与 `system_prompt`

`Agent` 上还有一个 `system_prompt` 参数，作用相近，区别在于是否进入消息历史：

| | 是否写进历史的 parts |
|---|---|
| `instructions` | 否。存在 `ModelRequest.instructions` 字段上 |
| `system_prompt` | 是。作为 `SystemPromptPart` 出现在第一条 `ModelRequest` 里 |

本项目统一用 `instructions`。

### 4.6 `result.usage` 的统计范围

`result.usage` 是「本次 run」的用量，但传入 `conversation=` 时，之前的累计值会被一起带进来。所以在 04 示例里，`second.usage` 和 `second.conversation.usage` 的 `requests` 都是 2。想要明确的对话总量，读 `result.conversation.usage`。

## 5. 速查

```python
from pydantic_ai import Agent, ModelSettings
from agentkit import get_model

agent = Agent(
    get_model(),
    instructions="...",                                   # Agent 级指令
    model_settings=ModelSettings(temperature=0.2),        # Agent 级参数
)

# 同步
result = agent.run_sync("问题")

# 异步
result = await agent.run("问题")

# 并发
results = await asyncio.gather(*(agent.run(q) for q in questions))

# 单次覆盖参数 / 追加指令
result = agent.run_sync("问题", model_settings=ModelSettings(temperature=1.0))
result = agent.run_sync("问题", instructions="这一次的额外要求")

# 多轮
second = agent.run_sync("追问", conversation=first.conversation)

# 读结果
result.output                 # 最终输出
result.usage                  # 用量（属性，不加括号）
result.response.model_name    # 实际响应的模型
result.all_messages()         # 全部消息
result.new_messages()         # 本次新增的消息
result.conversation           # 传给下一次 run
```

| 概念 | 一句话 |
|---|---|
| Agent | 模型 + 指令的配置，无状态，定义在模块顶层复用 |
| `run` / `run_sync` | 异步本体 / 同步包装 |
| `model_settings` | 三层覆盖：模型默认 < Agent 级 < run 级，按 key 合并 |
| `instructions` | run 级是追加，不是替换 |
| 多轮对话 | Agent 不存历史，把 `result.conversation` 传给下一次 run |
| 消息结构 | `ModelRequest` / `ModelResponse` 交替，各自由 part 组成 |

---

下一章：`02_streaming`（详解待写）
