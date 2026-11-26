"""带工具的流式输出：边跑边看到“模型调了什么工具、拿到了什么结果”。

第 02 章说过：Agent 带工具时不要用 run_stream，要用 run_stream_events，
因为它会把整个 Agent 跑完（模型 → 工具 → 模型 → ……），并把每一步都作为事件给你。

这一章新增两个事件（第 02 章的 `case _: pass` 跳过的就是它们）：

    FunctionToolCallEvent    框架即将执行一个工具，event.part 是 ToolCallPart
    FunctionToolResultEvent  工具执行完了，event.part 是 ToolReturnPart

做聊天界面时，这两个事件对应“正在查询天气…”“查询完成”这类状态提示。

还有两点：
- 并行工具调用：模型可以在一次响应里要求调用多个工具，框架会用 asyncio 并发执行。
  下面每个工具都要 1 秒，三个一起调用总共也只要 1 秒左右。
  是否并行由模型决定，有的模型或中转站会一个一个调，那样就是 3 秒、请求次数也更多。
- UsageLimits：给一次运行设上限，防止模型陷入反复调工具的死循环。超限抛 UsageLimitExceeded。
"""

import asyncio
import time

from pydantic_ai import (
    Agent,
    AgentRunResultEvent,
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    PartDeltaEvent,
    PartStartEvent,
    TextPart,
    TextPartDelta,
    UsageLimits,
)
from rich.markup import escape

from agentkit import console, get_model, header

model = get_model()
agent = Agent(model, instructions="用中文简短回答。天气信息必须用工具查询。")

WEATHER = {
    "北京": "晴，2°C，西北风 4 级",
    "上海": "小雨，11°C",
    "广州": "多云，22°C，微风",
}


# 工具可以是 async 函数：里面可以 await 数据库、HTTP 请求等
@agent.tool_plain
async def get_weather(city: str) -> str:
    """查询某个城市今天的天气。

    Args:
        city: 城市名，例如 北京
    """
    await asyncio.sleep(1)  # 模拟一次耗时 1 秒的网络请求
    return WEATHER.get(city, "没有这个城市的数据")


async def main() -> None:
    header("05 stream tool events", model)
    start = time.perf_counter()

    def elapsed() -> str:
        return f"{time.perf_counter() - start:4.1f}s"

    async with agent.run_stream_events(
        "北京、上海、广州今天哪个城市最适合户外跑步？",
        # 最多请求模型 5 次、最多成功执行 10 次工具
        usage_limits=UsageLimits(request_limit=5, tool_calls_limit=10),
    ) as events:
        async for event in events:
            match event:
                case FunctionToolCallEvent(part=part):
                    args = escape(part.args_as_json_str())
                    console.print(f"[cyan]{elapsed()} 调用[/] {part.tool_name}({args})")
                case FunctionToolResultEvent(part=part):
                    content = escape(str(part.content))
                    console.print(
                        f"[green]{elapsed()} 结果[/] {part.tool_name} → {content}"
                    )
                case PartStartEvent(part=TextPart(content=content)):
                    print(content, end="", flush=True)
                case PartDeltaEvent(delta=TextPartDelta(content_delta=delta)):
                    print(delta, end="", flush=True)
                case AgentRunResultEvent(result=result):
                    print()
                    console.print(f"[dim]{elapsed()} 结束，用量：{result.usage}[/]")
                case _:
                    pass


# 输出
#  2.9s 调用 get_weather({"city":"北京"})
#  2.9s 调用 get_weather({"city":"上海"})
#  2.9s 调用 get_weather({"city":"广州"})
#  3.9s 结果 get_weather → 晴，2°C，西北风 4 级
#  3.9s 结果 get_weather → 小雨，11°C
#  3.9s 结果 get_weather → 多云，22°C，微风
# 今天最适合户外跑步的是广州：多云、22°C、微风，比北京暖和，也不像上海那样下雨。

# 北京晴，2°C，西北风4级，偏冷且风较大；上海小雨，11°C，跑步时要留意路面湿滑。
#  7.8s 结束，用量：RunUsage(cost=Decimal('0.001948'), details={'accepted_prediction_tokens': 0, 'reasoning_tokens': 0,
# 'rejected_prediction_tokens': 0}, input_tokens=304, output_tokens=134, requests=2, tool_calls=3)

if __name__ == "__main__":
    asyncio.run(main())
