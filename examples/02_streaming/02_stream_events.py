"""完整事件流：run_stream_events。

run_stream 只关心“最终输出”，而且把第一个匹配输出类型的内容当作最终结果就结束：
同一条响应里的工具调用即使被执行，结果也不会再回传给模型。Agent 带工具时，
应该用 run_stream_events：它一定把整个 Agent 跑完，并把过程中的每个事件都给你。

事件模型（与厂商协议无关）：
    PartStartEvent   一个新的 part 开始（文本 / 思考 / 工具调用），第一段内容就在这里面
    PartDeltaEvent   该 part 的增量
    PartEndEvent     该 part 结束，带完整内容
    FinalResultEvent 模型开始产出最终结果
    AgentRunResultEvent 整个 run 结束，带最终结果
"""

import asyncio

from pydantic_ai import (
    Agent,
    AgentRunResultEvent,
    FinalResultEvent,
    PartDeltaEvent,
    PartEndEvent,
    PartStartEvent,
    TextPart,
    TextPartDelta,
    ThinkingPart,
    ThinkingPartDelta,
)

from agentkit import console, get_model, header

model = get_model()
agent = Agent(model, instructions="用中文回答。")


async def main() -> None:
    header("02 stream events", model)

    async with agent.run_stream_events("9.11 和 9.9 哪个大？简短说明理由。") as events:
        async for event in events:
            match event:
                case PartStartEvent(part=TextPart(content=content)):
                    console.print("[cyan]\\[文本开始][/]")
                    print(content, end="", flush=True)
                case PartStartEvent(part=ThinkingPart(content=content)):
                    console.print("[magenta]\\[思考开始][/]")
                    print(content, end="", flush=True)
                case PartDeltaEvent(delta=TextPartDelta(content_delta=delta)):
                    print(delta, end="", flush=True)
                case PartDeltaEvent(delta=ThinkingPartDelta(content_delta=delta)) if (
                    delta
                ):
                    print(delta, end="", flush=True)
                case PartEndEvent():
                    print()
                case FinalResultEvent():
                    # 纯文本输出时，它紧跟在第一个文本 part 开始之后，所以标记打在行内
                    console.print("[green]⟨最终结果⟩[/]", end="")
                case AgentRunResultEvent(result=result):
                    console.print(f"[dim]\\[结束] 用量：{result.usage}[/]")
                case _:
                    # 其他事件（工具调用等）在后面的章节再处理
                    pass


if __name__ == "__main__":
    asyncio.run(main())
