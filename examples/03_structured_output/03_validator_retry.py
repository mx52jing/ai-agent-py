"""输出校验与自动重试。

校验分两层：
1. pydantic 校验（类型、字段约束）：不通过时，Pydantic AI 自动把错误信息发回模型让它重试。
2. output_validator：自己写的业务校验（可以是 async，可以查库），抛 ModelRetry 让模型重试。

重试次数用 retries={'output': N} 控制，用完仍不通过则抛 UnexpectedModelBehavior。

一次运行的完整流程：

    模型输出 ──> 第 1 层 pydantic 校验 ──> 第 2 层 output_validator ──> 得到 result.output
                      │ 不通过                    │ 抛 ModelRetry
                      └────── 把错误信息发回模型，让它重新输出 ──────┘
"""

from pydantic import BaseModel, Field
from pydantic_ai import Agent, ModelRetry

from agentkit import console, get_model, header

# 假装这是数据库里已有的用户名。
# 真实项目里这里会是一次数据库查询，所以这类校验没法写进 schema，只能放到第 2 层。
TAKEN = {"alice", "alice1", "alice_dev"}


class Username(BaseModel):
    # 第 1 层校验：格式约束，写在 schema 里，由 pydantic 自动执行。
    # pattern 含义：小写字母开头，后面跟 2~15 个小写字母 / 数字 / 下划线（总长 3~16）。
    # description 会进入发给模型的 JSON Schema，等于是给模型看的提示。
    value: str = Field(
        pattern=r"^[a-z][a-z0-9_]{2,15}$", description="小写字母开头的用户名"
    )


model = get_model()
agent = Agent(
    model,
    output_type=Username,
    # 故意让模型倾向于给出 "alice" 这种最直接的名字，这样才会撞上 TAKEN，触发重试
    instructions="为用户生成一个用户名，优先使用最短、最直接的形式。",
    # 输出校验不通过时，最多让模型重试 3 次；用完还不通过就抛 UnexpectedModelBehavior
    retries={"output": 3},
)


# 第 2 层校验：业务规则。用装饰器把函数注册到 agent 上。
# 它在第 1 层通过之后才执行，所以这里拿到的 output 一定已经是格式合法的 Username。
@agent.output_validator
def check_available(output: Username) -> Username:
    if output.value in TAKEN:
        console.print(f"[yellow]'{output.value}' 已被占用，要求模型重试[/]")
        # ModelRetry 不是普通的报错：它不会让程序崩溃，
        # 而是把括号里的这句话发回给模型，模型据此重新生成。
        # 所以这句话是写给模型看的，要说清楚错在哪、该怎么改。
        raise ModelRetry(f"用户名 '{output.value}' 已被占用，请换一个不同的。")
    # 校验通过必须把结果 return 出去，它就是最终的 result.output
    return output


def main() -> None:
    header("03 validator retry", model)

    # 重试循环全部发生在 run_sync 内部，调用方只会拿到最终通过校验的结果
    result = agent.run_sync("我叫 Alice，是一名开发者")
    console.print(f"最终用户名：[bold]{result.output.value}[/]")
    # requests 是这次运行里请求模型的总次数：1 表示一次通过，> 1 说明发生过重试
    console.print(f"[dim]共请求模型 {result.usage.requests} 次[/]")

# 输出
# 'alice' 已被占用，要求模型重试
# 最终用户名：ali
# 共请求模型 2 次

if __name__ == "__main__":
    main()
