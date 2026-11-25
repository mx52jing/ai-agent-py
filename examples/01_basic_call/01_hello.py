"""最基础的一次调用：创建 Agent，同步运行，拿到文本输出和用量。

Agent 是 Pydantic AI 的核心对象：模型 + 指令（+ 工具、输出类型，后面章节再加）。
它是无状态、可复用的，通常定义成模块级变量，类似一个路由或一个函数。
"""

from pydantic_ai import Agent

from agentkit import console, get_model, header

model = get_model()
agent = Agent(model, instructions="你是一个简洁的助手，用中文回答。")


def main() -> None:
    header("01 hello", model)

    # run_sync 是 run 的同步包装，脚本里用最方便
    result = agent.run_sync("用一句话解释什么是 AI Agent")

    print(result.output)  # 最终输出，这里是 str
    console.print(f"[dim]用量：{result.usage}[/]")
    console.print(f"[dim]实际响应的模型：{result.response.model_name}[/]")


if __name__ == "__main__":
    main()
