"""流式 + 多轮：一个最小的终端聊天。输入空行或 Ctrl-D 退出。

这里用 run_stream_events 而不是 run_stream，因为结束事件里带完整的 result，
可以直接取 result.conversation 传给下一轮。
"""

import asyncio

from pydantic_ai import (
    Agent,
    AgentRunResultEvent,
    Conversation,
    PartDeltaEvent,
    PartStartEvent,
    TextPart,
    TextPartDelta,
)

from agentkit import console, get_model, header

model = get_model()
agent = Agent(model, instructions="你是一个简洁的助手，用中文回答。")


async def chat_once(prompt: str, conversation: Conversation | None) -> Conversation:
    async with agent.run_stream_events(prompt, conversation=conversation) as events:
        async for event in events:
            # 模型的回复由若干 part 组成（文本 / 思考 / 工具调用），每个 part 按
            # “开始 → 若干增量 → 结束”的顺序到达。这里只挑文本 part 打印。
            match event:
                # 一段文本开始了。第一小段文字就带在这个事件里，不打印会丢开头几个字。
                case PartStartEvent(part=TextPart(content=content)):
                    print(content, end="", flush=True)
                # 这段文本的后续增量：每次只有新增的几个字，接着往后打印就是打字机效果。
                case PartDeltaEvent(delta=TextPartDelta(content_delta=delta)):
                    print(delta, end="", flush=True)
                # 整个 run 结束，只会出现一次，且是最后一个事件。result 里有完整结果，
                # 其中 conversation 是“历史 + 本轮问答”，交给下一轮就实现了多轮记忆。
                case AgentRunResultEvent(result=result):
                    print()
                    return result.conversation
                # 其余事件（思考 part、part 结束、工具调用等）这个例子用不到，忽略。
                case _:
                    pass
    raise RuntimeError("事件流结束时没有收到最终结果")


async def main() -> None:
    header("03 chat repl", model)
    conversation: Conversation | None = None
    while True:
        try:
            prompt = console.input("[bold green]你> [/]").strip()
        except EOFError:
            break
        if not prompt:
            break
        conversation = await chat_once(prompt, conversation)


if __name__ == "__main__":
    asyncio.run(main())
