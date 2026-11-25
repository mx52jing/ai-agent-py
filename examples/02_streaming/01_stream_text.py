"""流式文本：run_stream + stream_text。

run_stream 是异步上下文管理器，退出时关闭连接。
stream_text(delta=True) 每次给增量；默认（delta=False）每次给到目前为止的完整文本。
"""

import asyncio

from pydantic_ai import Agent

from agentkit import console, get_model, header

model = get_model()
agent = Agent(model, instructions="请使用中文回答。")


async def main() -> None:
    header("01 stream text", model)

    async with agent.run_stream("用三句话介绍一下流式输出（SSE）的原理") as response:
        # debounce_by=None：收到一个 chunk 就立刻给出，不做合并
        async for delta in response.stream_text(delta=True, debounce_by=None):
            print(delta, end="", flush=True)
        print()
        # 流结束后才有完整的用量
        console.print(f"[dim]用量：{response.usage}[/]")


if __name__ == "__main__":
    asyncio.run(main())
