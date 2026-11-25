"""多轮对话：Agent 不保存历史，每次 run 结束后把 conversation 传给下一次 run。

conversation 里是 Pydantic AI 统一的消息结构（与具体厂商协议无关）：
ModelRequest（发给模型的）和 ModelResponse（模型返回的），各自由若干 part 组成。
"""

from pydantic_ai import Agent

from agentkit import console, get_model, header

model = get_model()
agent = Agent(model, instructions="你是一个简洁的助手，用中文回答。")


def main() -> None:
    header("04 multi turn", model)

    first = agent.run_sync("爱因斯坦是谁？一句话回答。")
    print(first.output)
    print("---------------------------------------------------------------------")
    # 不传 conversation 的话，模型不知道“他”指谁
    second = agent.run_sync("他最著名的公式是什么？", conversation=first.conversation)
    print(second.output)

    console.rule("消息历史")
    for message in second.all_messages():
        parts = ", ".join(type(part).__name__ for part in message.parts)
        console.print(f"{type(message).__name__}: {parts}")

    # usage 是整个对话的累计值
    console.print(f"[dim]累计用量：{second.conversation.usage}[/]")


if __name__ == "__main__":
    main()
