"""指令与模型参数，以及它们的三层覆盖关系：模型默认 < Agent 级 < 单次 run 级。

注意：部分推理模型不接受 temperature 等采样参数，中转站可能直接报 400，
遇到时删掉对应参数即可。
"""

from pydantic_ai import Agent, ModelSettings

from agentkit import console, get_model, header

model = get_model()

agent = Agent(
    model,
    instructions="你是一个取名助手，只输出名字本身，不要解释。",
    # Agent 级默认参数。ModelSettings 是 TypedDict，写成普通 dict 也可以
    model_settings=ModelSettings(temperature=0.2, max_tokens=100),
)

PROMPT = "给一个用 Rust 写的命令行 Agent 工具起一个名字"


def main() -> None:
    header("03 settings", model)

    console.print("[bold]Agent 级参数（temperature=0.2）[/]")
    print(agent.run_sync(PROMPT).output)

    console.print("[bold]run 级覆盖（temperature=1.0）[/]")
    print(agent.run_sync(PROMPT, model_settings=ModelSettings(temperature=1.0)).output)

    # run 级的 instructions 是追加，不是替换 Agent 上的 instructions
    console.print("[bold]run 级追加指令[/]")
    print(agent.run_sync(PROMPT, instructions="名字必须是中文，两个字。").output)


if __name__ == "__main__":
    main()
