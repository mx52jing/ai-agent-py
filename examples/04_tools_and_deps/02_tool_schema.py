"""模型到底看到了什么：函数签名 → 工具定义（JSON Schema）。

模型看不到函数体，只看到三样东西：工具名、工具说明、参数的 JSON Schema。
它们全部从函数本身生成：

    函数名                → 工具名
    docstring 的正文      → 工具说明（Args 之前的所有段落）
    docstring 的 Args     → 每个参数的 description
    类型注解              → 参数类型（Literal → enum，X | None → 可空）
    没有默认值            → 进入 required；有默认值 → 可以不传

所以写工具 = 写好类型注解和 docstring，它们是写给模型看的提示词。
（Rust 里要 #[derive(JsonSchema)] 再手动拼工具定义，这里由函数签名直接生成。）

顺带一提：工具定义每次请求都会带上，算 input tokens。工具越多、说明越啰嗦，每次请求越贵，
所以说明要写清楚，但别写小作文。

这个例子还演示了另外两点：
- 用 tools=[...] 注册工具，而不是装饰器：同一个函数可以给多个 Agent 复用。
- FunctionModel：用一个你自己写的函数冒充模型，可以不发请求就看到“模型收到了什么”。
"""

import asyncio
import json
from typing import Literal

from pydantic import BaseModel
from pydantic_ai import Agent, ModelMessage, ModelResponse, TextPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from agentkit import console, header
from agentkit.models import get_model


class Product(BaseModel):
    name: str
    category: str
    price: float


CATALOG = [
    Product(name="K8 机械键盘", category="键盘", price=399),
    Product(name="K2 薄膜键盘", category="键盘", price=89),
    Product(name="M5 无线鼠标", category="鼠标", price=129),
    Product(name="M9 电竞鼠标", category="鼠标", price=349),
    Product(name="U27 4K 显示器", category="显示器", price=1899),
]


# 一个普通函数，没有装饰器。返回值可以是任何能序列化成 JSON 的东西，这里是 pydantic 对象的列表。
#
# 四个参数正好是四种写法，对照文件底部打印出来的 schema 看：
# - Literal[...] 相当于 TS 的 "键盘" | "鼠标" | "显示器"，在 schema 里变成 enum。
#   能用 Literal 就别用 str：模型只能从这几个里选，传别的值会被框架打回去重传。
# - 有默认值的参数模型可以不传，默认值也会写进 schema 告诉模型。
# - float | None 相当于 Rust 的 Option<f64>。
#
# docstring 里的 Args: 是 Google 风格写法，框架会自动识别（numpy、sphinx 风格也认）。
# 参数名要和函数签名里的一模一样，不然说明对不上号。
def search_products(
    category: Literal["键盘", "鼠标", "显示器"],
    keyword: str = "",
    max_price: float | None = None,
    limit: int = 3,
) -> list[Product]:
    """在商品目录里按分类搜索商品，按价格从低到高返回。

    Args:
        category: 商品分类
        keyword: 商品名里要包含的关键词，留空表示不限
        max_price: 价格上限（元），不限价格时不传
        limit: 最多返回几条
    """
    found = [
        p
        for p in CATALOG
        if p.category == category
        and keyword in p.name
        and (max_price is None or p.price <= max_price)
    ]
    return sorted(found, key=lambda p: p.price)[:limit]


def show_what_model_sees(
    messages: list[ModelMessage], info: AgentInfo
) -> ModelResponse:
    """冒充模型的函数：框架把“本来要发给模型的东西”原样交给它。"""
    # messages：到目前为止的消息历史；info：这次请求附带的东西，工具定义就在 info.function_tools 里
    for tool in info.function_tools:
        console.print(f"[bold]name[/]        {tool.name}")
        console.print(f"[bold]description[/] {tool.description}")
        console.print("[bold]parameters[/]")
        # ensure_ascii=False：不加的话中文会被转成 \uXXXX
        console.print_json(json.dumps(tool.parameters_json_schema, ensure_ascii=False))
    # 返回值就是“模型的回复”。这里回一段文字，运行就直接结束了。
    # 如果回一个 ToolCallPart，框架会真的去执行工具——写单元测试时就靠这招，不花钱也不用联网。
    return ModelResponse(parts=[TextPart("（假模型的回答）")])


model = get_model()
agent = Agent(
    model,
    # 和装饰器效果一样。框架看函数第一个参数是不是 RunContext，自动判断它要不要上下文（见 03）。
    tools=[search_products],
    instructions="你是商城导购，用中文简短回答。只推荐工具查到的商品。",
)


async def main() -> None:
    header("02 tool schema", model)

    console.rule("模型看到的工具定义")
    # run 时传 model= 可以临时换模型，这里换成假模型，不会发出任何请求
    await agent.run("随便问点什么", model=FunctionModel(show_what_model_sees))

    console.rule("真实调用")
    result = await agent.run("300 块以内有什么鼠标？再推荐一个最便宜的键盘。")
    print(result.output)
    console.print(f"[dim]用量：{result.usage}[/]")


# 怎么读下面这份 schema：
# - required 里只有 category：其他三个都有默认值，模型可以不传。
# - max_price 的 anyOf [number, null]：就是 float | None，“要么数字要么空”。
# - additionalProperties: false：不许模型传 schema 里没有的参数。
# - 真实调用那里 tool_calls=2、requests=2：模型一次回复里并行查了鼠标和键盘两次。
#
# 输出
# name        search_products
# description 在商品目录里按分类搜索商品，按价格从低到高返回。
# parameters
# {
#   "additionalProperties": false,
#   "properties": {
#     "category": {
#       "description": "商品分类",
#       "enum": [
#         "键盘",
#         "鼠标",
#         "显示器"
#       ],
#       "type": "string"
#     },
#     "keyword": {
#       "default": "",
#       "description": "商品名里要包含的关键词，留空表示不限",
#       "type": "string"
#     },
#     "max_price": {
#       "anyOf": [
#         {
#           "type": "number"
#         },
#         {
#           "type": "null"
#         }
#       ],
#       "default": null,
#       "description": "价格上限（元），不限价格时不传"
#     },
#     "limit": {
#       "default": 3,
#       "description": "最多返回几条",
#       "type": "integer"
#     }
#   },
#   "required": [
#     "category"
#   ],
#   "type": "object"
# }
# ─────────────────────────────────────────────────────────────── 真实调用 ───────────────────────────────────────────────────────────────
# - **300 元以内的鼠标**：M5 无线鼠标，129 元。
# - **最便宜的键盘**：K2 薄膜键盘，89 元。

# 两件一起买共 **218 元**。
# 用量：RunUsage(cost=Decimal('0.002096'), input_tokens=473, output_tokens=115, requests=2, tool_calls=2)

if __name__ == "__main__":
    asyncio.run(main())
