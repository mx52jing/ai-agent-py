"""流式结构化输出：边生成边拿到“部分校验”过的对象，适合边生成边渲染 UI。

stream_output() 每次给出到目前为止能解析出的对象，字段会逐步补全。
用 TypedDict + NotRequired 表达“这个字段可能还没生成出来”。

和前几个示例的区别：

    run_sync()    等模型全部输出完，一次性拿到完整对象
    run_stream()  模型一边输出，这边一边拿到“半成品”对象，字段越来越全

打印出来大致是这样逐步长大的：

    {'title': '为什么前端'}
    {'title': '为什么前端工程师适合学习 Agent 开发', 'tags': ['前端']}
    {'title': '...', 'tags': ['前端', 'Agent'], 'summary': '前端工程师...'}
"""

import asyncio
from typing import NotRequired, TypedDict

from pydantic_ai import Agent

from agentkit import console, get_model, header


# 这里用 TypedDict 而不是 BaseModel。
# TypedDict 运行时就是普通 dict，只是带了类型标注，相当于 TS 的 interface：
#     interface Article { title: string; tags?: string[]; summary?: string }
# 所以下面拿到的 partial / article 都是 dict，取值用 article["title"]，不是 article.title。
class Article(TypedDict):
    title: str
    # NotRequired 表示这个 key 可以不存在，对应 TS 里的 `?`。
    # 流式过程中模型还没写到这个字段时，dict 里就没有这个 key。
    tags: NotRequired[list[str]]
    summary: NotRequired[str]


model = get_model()
agent = Agent(
    model, output_type=Article, instructions="根据主题写一篇短文的元信息，用中文。"
)


# run_stream 是异步 API，所以 main 要写成 async def
async def main() -> None:
    header("04 stream structured", model)

    # async with 打开一个流式响应，离开这个代码块时自动关闭连接，
    # 类似 Rust 里变量离开作用域自动 Drop。流只在这个代码块内可用。
    async with agent.run_stream(
        "主题：为什么前端工程师适合学习 Agent 开发"
    ) as response:
        # async for 相当于 JS 的 for await...of。
        # 每次拿到的 partial 是“到目前为止的完整快照”，不是增量：
        # 后一个包含前一个的全部内容，所以渲染 UI 时直接整体替换即可，不用自己拼接。
        async for partial in response.stream_output():
            console.print(partial)

        # 流结束后，get_output() 返回最终的完整对象
        article = await response.get_output()
        console.rule("最终结果")
        console.print(article)

# 输出
# {'title': '为什么前端工程师适合学习 Agent'}
# {'title': '为什么前端工程师适合学习 Agent 开发？', 'summary': '前端工程师'}
# {'title': '为什么前端工程师适合学习 Agent 开发？', 'summary': '前端工程师熟悉用户交互、状态管理与 API 集成，这'}
# {
#     'title': '为什么前端工程师适合学习 Agent 开发？',
#     'summary': '前端工程师熟悉用户交互、状态管理与 API 集成，这些经验可以直接用于构建 Agent'
# }
# {
#     'title': '为什么前端工程师适合学习 Agent 开发？',
#     'summary': '前端工程师熟悉用户交互、状态管理与 API 集成，这些经验可以直接用于构建 Agent：展示任务进度、处理工具'
# }
# {
#     'title': '为什么前端工程师适合学习 Agent 开发？',
#     'summary': '前端工程师熟悉用户交互、状态管理与 API 集成，这些经验可以直接用于构建
# Agent：展示任务进度、处理工具调用失败，并在关键操作前让用户确认。本文'
# }
# {
#     'title': '为什么前端工程师适合学习 Agent 开发？',
#     'summary': '前端工程师熟悉用户交互、状态管理与 API 集成，这些经验可以直接用于构建
# Agent：展示任务进度、处理工具调用失败，并在关键操作前让用户确认。本文也会介绍从'
# }
# {
#     'title': '为什么前端工程师适合学习 Agent 开发？',
#     'summary': '前端工程师熟悉用户交互、状态管理与 API 集成，这些经验可以直接用于构建
# Agent：展示任务进度、处理工具调用失败，并在关键操作前让用户确认。本文也会介绍从前端迈向 Agent 开发时'
# }
# {
#     'title': '为什么前端工程师适合学习 Agent 开发？',
#     'summary': '前端工程师熟悉用户交互、状态管理与 API 集成，这些经验可以直接用于构建
# Agent：展示任务进度、处理工具调用失败，并在关键操作前让用户确认。本文也会介绍从前端迈向 Agent 开发时，需要补上的 LLM'
# }
# {
#     'title': '为什么前端工程师适合学习 Agent 开发？',
#     'summary': '前端工程师熟悉用户交互、状态管理与 API 集成，这些经验可以直接用于构建
# Agent：展示任务进度、处理工具调用失败，并在关键操作前让用户确认。本文也会介绍从前端迈向 Agent 开发时，需要补上的 LLM
# 基础、工具调用与效果'
# }
# {
#     'title': '为什么前端工程师适合学习 Agent 开发？',
#     'tags': ['前端工程', 'Agent 开'],
#     'summary': '前端工程师熟悉用户交互、状态管理与 API 集成，这些经验可以直接用于构建
# Agent：展示任务进度、处理工具调用失败，并在关键操作前让用户确认。本文也会介绍从前端迈向 Agent 开发时，需要补上的 LLM
# 基础、工具调用与效果评估。'
# }
# {
#     'title': '为什么前端工程师适合学习 Agent 开发？',
#     'tags': ['前端工程', 'Agent 开发', '大语言模型', '人机交互', '工具'],
#     'summary': '前端工程师熟悉用户交互、状态管理与 API 集成，这些经验可以直接用于构建
# Agent：展示任务进度、处理工具调用失败，并在关键操作前让用户确认。本文也会介绍从前端迈向 Agent 开发时，需要补上的 LLM
# 基础、工具调用与效果评估。'
# }
# {
#     'title': '为什么前端工程师适合学习 Agent 开发？',
#     'tags': ['前端工程', 'Agent 开发', '大语言模型', '人机交互', '工具调用'],
#     'summary': '前端工程师熟悉用户交互、状态管理与 API 集成，这些经验可以直接用于构建
# Agent：展示任务进度、处理工具调用失败，并在关键操作前让用户确认。本文也会介绍从前端迈向 Agent 开发时，需要补上的 LLM
# 基础、工具调用与效果评估。'
# }
# {
#     'title': '为什么前端工程师适合学习 Agent 开发？',
#     'tags': ['前端工程', 'Agent 开发', '大语言模型', '人机交互', '工具调用'],
#     'summary': '前端工程师熟悉用户交互、状态管理与 API 集成，这些经验可以直接用于构建
# Agent：展示任务进度、处理工具调用失败，并在关键操作前让用户确认。本文也会介绍从前端迈向 Agent 开发时，需要补上的 LLM
# 基础、工具调用与效果评估。'
# }
# ─────────────────────────────────────────────────────────────── 最终结果 ───────────────────────────────────────────────────────────────
# {
#     'title': '为什么前端工程师适合学习 Agent 开发？',
#     'tags': ['前端工程', 'Agent 开发', '大语言模型', '人机交互', '工具调用'],
#     'summary': '前端工程师熟悉用户交互、状态管理与 API 集成，这些经验可以直接用于构建
# Agent：展示任务进度、处理工具调用失败，并在关键操作前让用户确认。本文也会介绍从前端迈向 Agent 开发时，需要补上的 LLM
# 基础、工具调用与效果评估。'
# }

if __name__ == "__main__":
    # asyncio.run 启动事件循环并执行 main()，是从同步代码进入异步代码的入口
    asyncio.run(main())
