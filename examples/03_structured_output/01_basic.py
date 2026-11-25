"""结构化输出：把 pydantic 模型作为 output_type，result.output 就是校验过的对象。

pydantic 之于 Python ≈ serde + 校验 之于 Rust / zod 之于 TS。
字段的类型和 description 会进入发给模型的 JSON Schema，等于是给模型看的提示。
"""

from typing import Literal

from pydantic import BaseModel, Field
from pydantic_ai import Agent

from agentkit import console, get_model, header


class LineItem(BaseModel):
    name: str
    quantity: int
    unit_price: float = Field(description="单价，单位：元")


class Order(BaseModel):
    customer: str
    items: list[LineItem]
    urgency: Literal["low", "normal", "high"] = Field(
        description="根据语气判断紧急程度"
    )
    note: str | None = Field(default=None, description="客户的额外要求，没有则为空")


model = get_model()
agent = Agent(model, output_type=Order, instructions="从用户消息里提取订单信息。")

MESSAGE = "我是王磊，要 3 个机械键盘（每个 399）和 2 根 Type-C 线（15 块一根），明天必须到！发顺丰。"


def main() -> None:
    header("01 structured output", model)

    result = agent.run_sync(MESSAGE)
    order = result.output  # 类型是 Order，IDE 和 pyright 都认识

    console.print(order)
    total = sum(item.quantity * item.unit_price for item in order.items)
    console.print(f"合计：{total:.2f} 元，紧急程度：{order.urgency}")

# 输出
# Order(
#     customer='王磊',
#     items=[LineItem(name='机械键盘', quantity=3, unit_price=399.0), LineItem(name='Type-C 线', quantity=2, unit_price=15.0)],
#     urgency='high',
#     note='发顺丰，明天必须送达。'
# )
# 合计：1227.00 元，紧急程度：high

if __name__ == "__main__":
    main()
