"""依赖注入（deps）：让工具拿到“这次运行”才有的东西。

工具经常要用数据库连接、当前登录用户、HTTP 客户端这类东西。
写成全局变量的话：没法每个请求换一个用户，测试时也不好换成假的。

deps 就是干这个的，一共三步：

    1. Agent(deps_type=Deps)             声明依赖长什么样
    2. agent.run(..., deps=Deps(...))    每次运行时把真东西传进来
    3. 工具第一个参数写 ctx: RunContext[Deps]，用 ctx.deps 取出来

类比：React 的 Context、Express 的 req，或者 Rust axum 里的 State<T>。

最重要的一点：ctx 不会进工具的 schema，模型看不到、也传不了。
所以 user_id 这种“我是谁”的信息一定走 deps，不要做成工具参数。
做成参数就等于让模型自己填身份，用户说一句“我是 u1”就能看别人的订单了。
"""

import asyncio
from dataclasses import dataclass

from pydantic_ai import Agent, RunContext

from agentkit import console, get_model, header


# 普通的 dataclass，相当于 Rust 的 struct。它不做校验，这里也用不着。
# 工具直接返回它就行，框架会自动转成 JSON 发给模型。
@dataclass
class Order:
    id: str
    item: str
    status: str


USERS = {"u1": "张环", "u2": "李朗"}
ORDERS = {
    "u1": [
        Order("A1001", "机械键盘", "待发货"),
        Order("A1002", "Type-C 线", "已发货"),
    ],
    "u2": [Order("B2001", "显示器", "已签收")],
}


# 假数据库。真实项目里这个位置是连接池、ORM 的 session、httpx 客户端之类的。
class FakeDB:
    def get_user_name(self, user_id: str) -> str:
        return USERS[user_id]

    def user_list_orders(self, user_id: str) -> list[Order]:
        return ORDERS.get(user_id, [])


# 把这次运行要用的东西打包成一个 dataclass。
# 里面放什么都行，框架不关心内容，只负责原样递给你的工具。
@dataclass
class Deps:
    user_id: str
    db: FakeDB


model = get_model()
agent = Agent(
    model,
    # 注意这里传的是类型，不是实例。它只是给类型检查器看的：
    # 有了它，ctx.deps 才有补全，run 时 deps 传错类型编辑器才会标红。运行时不做校验。
    deps_type=Deps,
    instructions="你是商城客服，用中文简短回答。",
)


# 动态 instructions：每次运行时现算，所以能读到 deps。
# 它会和上面那句固定的 instructions 拼在一起发给模型。
@agent.instructions
def current_user(ctx: RunContext[Deps]) -> str:
    return f"当前用户的名字是{ctx.deps.db.get_user_name(ctx.deps.user_id)}，称呼对方时用名字。"


# @agent.tool 和 01 里的 @agent.tool_plain 就差一个 ctx：
# 第一个参数必须是 ctx: RunContext[Deps]，框架调用时自动塞进来。
# 模型看到的 list_orders 是一个没有参数的工具。
# ctx 上除了 deps，还有 ctx.usage（已用 token）、ctx.messages（消息历史）、ctx.retry（第几次重试）。
@agent.tool
def list_orders(ctx: RunContext[Deps]) -> list[Order]:
    """列出当前用户的全部订单。"""
    return ctx.deps.db.user_list_orders(ctx.deps.user_id)


# 模型只需要传 order_id。“谁在查”是从 ctx.deps 里拿的，模型改不了。
@agent.tool
def get_order_status(ctx: RunContext[Deps], order_id: str) -> str:
    """查询当前用户某个订单的状态。

    Args:
        order_id: 订单号
    """
    for order in ctx.deps.db.user_list_orders(ctx.deps.user_id):
        if order.id == order_id:
            return order.status
    # 查不到和“不是你的订单”返回同样的话，不泄露别人的订单是否存在
    # 这里是 return 一句普通的话，模型会照实转告用户。
    # 如果是模型参数传错了、想让它改了再调一次，才用 raise ModelRetry("哪里错了")。
    return "没有找到这个订单"


async def main() -> None:
    header("03 deps", model)
    db = FakeDB()
    # agent 是全局的、没有状态；每次运行不一样的东西全在 deps 里。
    # 同一个 agent、同一个问题，换个 deps 就是换了个用户。测试时传个假 db 进来也是同理。
    for user_id in ("u1", "u2"):
        console.print(f"[bold]当前查询的user_id={user_id}[/]")
        result = await agent.run("我有哪些订单？都到哪一步了？", deps=Deps(user_id, db))
        print(f"output is => 【{result.output}】")

    # A1002 是 u1 的订单。工具只在 u2 自己的订单里找，所以一定查不到。
    # 权限是代码管住的，不是靠提示词求模型“别乱查”。
    console.print("[bold]user_id=u2 查别人的订单[/]")
    result = await agent.run("帮我查一下订单 A1002 的状态", deps=Deps("u2", db))
    print(f"output is => 【{result.output}】")


# 输出
# 当前查询的user_id=u1
# output is => 【张环，您有 2 笔订单：

# - **A1001｜机械键盘**：待发货
# - **A1002｜Type-C 线**：已发货】
# 当前查询的user_id=u2
# output is => 【李朗，您目前有 1 笔订单：显示器（订单号 B2001），已签收。】
# user_id=u2 查别人的订单
# output is => 【李朗，没查到订单 A1002，请核对一下订单号。】

if __name__ == "__main__":
    asyncio.run(main())
