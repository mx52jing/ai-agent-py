"""第一个工具：把普通函数交给模型调用。

模型只会生成文字，它不知道今天几号，也不会精确地算日期。
工具（tool）就是你写的函数：模型决定“调用哪个、传什么参数”，框架负责真正执行，
再把返回值发回给模型，模型据此继续回答。

一次带工具的运行，消息往返是这样的（就是你在 Rust 里手写过的那个循环）：

    你    ──> 模型：用户问题 + 可用工具列表
    模型  ──> 你  ：我要调用 get_today()            （ToolCallPart）
    框架执行函数
    你    ──> 模型：get_today 的返回值              （ToolReturnPart）
    模型  ──> 你  ：最终回答                        （TextPart）

@agent.tool_plain：注册一个不需要运行上下文的工具（需要上下文的 @agent.tool 见 03）。
函数名 = 工具名，docstring = 给模型看的工具说明，参数的类型注解 = 参数 schema。
"""

import asyncio
from datetime import date

from pydantic_ai import Agent, TextPart, ToolCallPart, ToolReturnPart, UserPromptPart
from rich.markup import escape

from agentkit import console, get_model

model = get_model()
agent = Agent(
    model,
    # 光注册工具，模型不一定会用（它可能觉得自己能算）。在 instructions 里点名要求，更稳。
    instructions="请使用简短中文来回答。涉及日期时必须用工具，不要自己推算。",
)

WEEKDAYS = ["一", "二", "三", "四", "五", "六", "日"]


# 没有参数的工具：模型调用时传一个空对象 {}。
# 工具写成普通 def 就行，框架会把它丢到线程池里跑，不会卡住事件循环；
# 函数里要 await（查库、发请求）时再写成 async def。
@agent.tool_plain
def get_today() -> str:
    """获取今天的日期和星期。"""
    today = date.today()
    # weekday()：周一是 0，周日是 6（JS 的 getDay() 是周日为 0，别搞混）
    return f"{today.isoformat()} 星期{WEEKDAYS[today.weekday()]}"


@agent.tool_plain
def days_until(target: date) -> int:
    """计算从今天到目标日期还有多少天。

    Args:
        target: 目标日期，格式 YYYY-MM-DD
    """
    # 模型传来的是 JSON 字符串 "2027-01-01"，框架按类型注解用 pydantic 校验并转成了 date，
    # 所以这里拿到的 target 已经是 date 对象。
    # 要是模型传了个 "明年元旦" 这种转不了的，函数根本不会执行：
    # 框架直接把校验错误发回给模型让它重传（默认重试 1 次，Agent(retries={"tools": N}) 可调）。
    #
    # 返回值不一定是 str：int、dict、list、pydantic 对象都行，框架会转成 JSON 再发给模型。
    return (target - date.today()).days


async def main() -> None:
    # 整个“调用工具 → 把结果发回去 → 再问模型”的循环都在 run 里面跑完了，这里拿到的已经是最终回答
    resp = await agent.run("今天星期几？距离2027年元旦还有多久？")
    print("llm 返回结果：", resp.output)
    # 工具调用的全过程都记录在消息历史里
    console.rule("消息历史")
    for message in resp.all_messages():
        for part in message.parts:
            # Python 的 match 和 Rust 的 match 差不多：
            # UserPromptPart(content=content) = “类型是 UserPromptPart，顺手把 content 字段解构出来”
            # escape()：rich 会把 [xxx] 当成样式标签，内容里万一有方括号就先转义掉
            match part:
                case UserPromptPart(content=content):
                    console.print(f"[bold]用户[/]      {escape(str(content))}")
                case ToolCallPart(tool_name=name):
                    args = escape(part.args_as_json_str())
                    console.print(f"[cyan]模型→调用[/]  {name}({args})")
                case ToolReturnPart(tool_name=name, content=content):
                    console.print(f"[green]框架→返回[/]  {name} = {content!r}")
                case TextPart(content=content):
                    console.print(f"[bold]模型[/]      {escape(content)}")
                case _:
                    pass
    # 每次工具往返都要多请求一次模型，所以 requests >= 2
    console.print(f"[dim]用量：{resp.usage}[/]")


# 看下面的输出：两个“模型→调用”是挨在一起的。
# 这是并行工具调用：模型一次回复里同时要了两个工具，框架并发执行完，再把两个结果一起发回去。
# 所以 tool_calls=2 但 requests 还是 2，而不是 3。
#
# 输出
# ─────────────────────────────────────────────────────────────── 消息历史 ───────────────────────────────────────────────────────────────
# 用户      今天星期几？距离2027年元旦还有多久？
# 模型→调用  get_today({})
# 模型→调用  days_until({"target":"2027-01-01"})
# 框架→返回  get_today = '2026-11-25 星期三'
# 框架→返回  days_until = 37
# 模型      今天是2026年11月25日，星期三。距离2027年元旦还有37天。
# 用量：RunUsage(cost=Decimal('0.001428'), input_tokens=329, output_tokens=77, requests=2, tool_calls=2)

if __name__ == "__main__":
    asyncio.run(main())
