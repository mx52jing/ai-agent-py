"""三种结构化输出模式，逐个试一遍，顺便探测当前中转站 / 模型支持哪些。

    ToolOutput     把 schema 包装成一个“输出工具”让模型调用。默认模式，支持面最广。
    NativeOutput   用接口原生的 JSON Schema 响应格式，模型被强制按 schema 输出。
                   需要模型和接口都支持，中转站未必透传。
    PromptedOutput 把 schema 写进指令，再从纯文本里解析。任何模型都能用，但最不可靠。

直接写 output_type=City 等价于 ToolOutput(City)。
"""

from pydantic import BaseModel
from pydantic_ai import Agent, NativeOutput, PromptedOutput, ToolOutput

from agentkit import console, get_model, header


class City(BaseModel):
    name: str
    country: str
    population_millions: float


model = get_model()
agent = Agent(model)

MODES = {
    "ToolOutput": ToolOutput(City),
    "NativeOutput": NativeOutput(City),
    "PromptedOutput": PromptedOutput(City),
}


def main() -> None:
    header("02 output modes", model)

    for name, output_type in MODES.items():
        console.print(f"[bold]{name}[/]")
        try:
            # output_type 也可以在 run 时指定，覆盖 Agent 上的设置
            result = agent.run_sync(
                "世界上人口最多的城市是哪个？", output_type=output_type
            )
        # 这里就是要看每种模式会不会失败，所以兜住所有异常
        except Exception as e:  # noqa: BLE001
            console.print(f"  [red]失败[/] {type(e).__name__}")
            console.print(f"  {e}", markup=False, highlight=False)
        else:
            console.print("  [green]成功[/]", result.output)

# 输出
#   成功
# City(name='雅加达', country='印度尼西亚', population_millions=41.9)
# NativeOutput
#   成功
# City(name='雅加达', country='印度尼西亚', population_millions=41.9)
# PromptedOutput
#   成功
# City(name='雅加达', country='印度尼西亚', population_millions=41.9)

if __name__ == "__main__":
    main()
