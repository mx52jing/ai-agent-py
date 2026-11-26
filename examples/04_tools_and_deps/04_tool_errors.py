"""工具出错了怎么办：三种失败，三种处理方式。

    情况                                在工具里怎么做            结果
    ─────────────────────────────────────────────────────────────────────────────
    参数不对，换个参数还能成功            raise ModelRetry(...)    错误信息发回模型，模型重新调用
    调用本身没问题，但结果就是失败        raise ToolFailed(...)    失败结果发回模型，由模型决定怎么办
    代码 bug、不该让模型知道的错误        其他任何异常              不发给模型，整个 run 直接抛出

另外还有第 0 种：模型传的参数类型不对（比如 hour 传了 "下午两点"）。
这种不用你处理，pydantic 校验失败后框架会自动把校验错误发回模型，效果等同于 ModelRetry。

重试次数：ModelRetry 和参数校验失败共用同一个计数，每个工具各算各的，默认只能重试 1 次。
用 @agent.tool(retries=N) 单独设置，或 Agent(retries={"tools": N}) 统一设置。
次数用完还不行，run 抛 UnexpectedModelBehavior。ToolFailed 不占用这个次数。

括号里的消息是写给模型看的，要说清楚错在哪、接下来可以怎么做。
"""

from typing import Literal

from pydantic_ai import Agent, ModelRetry, RunContext, ToolFailed, ToolReturnPart

from agentkit import console, get_model, header

model = get_model()
agent = Agent(model, instructions="你是会议室预订助手，用中文简短回答。")

# 已被占用的时段：会议室 -> 小时
BOOKED: dict[str, set[int]] = {"A": {14}, "B": set(), "C": set()}
MAINTENANCE = {"C"}


# 这个工具不需要依赖，但想读 ctx.retry，所以用 @agent.tool；
# Agent 没有声明 deps_type 时，ctx 的类型直接写 RunContext（不带方括号）
@agent.tool(retries=2)
def book_room(ctx: RunContext, room: Literal["A", "B", "C"], hour: int) -> str:
    """预订会议室，每次预订 1 小时。

    Args:
        room: 会议室编号
        hour: 开始时间，24 小时制的整点，例如 14 表示下午 2 点
    """
    # ctx.retry：这是这个工具的第几次重试（第一次调用是 0）
    console.print(f"[dim]  book_room(room={room!r}, hour={hour}) retry={ctx.retry}[/]")

    if room in MAINTENANCE:
        # 换什么参数都没用，属于“确定的失败”
        raise ToolFailed(f"{room} 会议室维修中，本周无法预订。")

    if hour in BOOKED[room]:
        # 换个参数就能成功，把可选项告诉模型
        free = [h for h in range(9, 18) if h not in BOOKED[room]]
        raise ModelRetry(f"{room} 会议室 {hour} 点已被占用，空闲的开始时间：{free}")

    BOOKED[room].add(hour)
    return f"已预订 {room} 会议室 {hour}:00-{hour + 1}:00"


@agent.tool_plain
def export_schedule() -> str:
    """导出本周的会议室日程表。"""
    # 模拟代码 bug。普通异常不会发给模型，会原样从 run_sync 里抛出来
    raise RuntimeError("导出服务连接失败")


def run(title: str, prompt: str) -> None:
    console.print(f"[bold]{title}[/]  {prompt}")
    result = agent.run_sync(prompt)
    print(result.output)
    # ToolReturnPart.outcome 记录了每次工具调用的结局：success / retried / failed
    for message in result.all_messages():
        for part in message.parts:
            if isinstance(part, ToolReturnPart):
                console.print(f"[dim]  {part.tool_name} → outcome={part.outcome}[/]")


def main() -> None:
    header("04 tool errors", model)

    run("ModelRetry", "帮我订 A 会议室下午 2 点，被占了就往后顺延到最近的空档。")
    run("ToolFailed", "帮我订 C 会议室上午 10 点。")

    console.print("[bold]普通异常[/]  导出本周日程表")
    try:
        agent.run_sync("导出本周日程表")
    except RuntimeError as e:
        console.print(f"[red]run 直接抛出了异常：[/]{type(e).__name__}: {e}")


# 输出
# ModelRetry  帮我订 A 会议室下午 2 点，被占了就往后顺延到最近的空档。
#   book_room(room='A', hour=14) retry=0
#   book_room(room='A', hour=15) retry=1
# A 会议室 14:00 已被占用，已顺延至最近的空档 15:00–16:00，预订成功。
#   book_room → outcome=retried
#   book_room → outcome=success
# ToolFailed  帮我订 C 会议室上午 10 点。
#   book_room(room='C', hour=10) retry=0
# C 会议室本周维修，上午 10 点没能订上。要我查一下 A 或 B 会议室同一时段是否有空吗？
#   book_room → outcome=failed
# 普通异常  导出本周日程表
# run 直接抛出了异常：RuntimeError: 导出服务连接失败

if __name__ == "__main__":
    main()
