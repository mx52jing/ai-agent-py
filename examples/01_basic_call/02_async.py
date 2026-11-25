"""异步运行与并发。

Pydantic AI 本身是 async 的，agent.run() 返回协程。
asyncio.run ≈ tokio 的 block_on；asyncio.gather ≈ Promise.all / join_all。
"""

import asyncio
import time

from pydantic_ai import Agent

from agentkit import console, get_model, header

model = get_model()
agent = Agent(model, instructions="用中文回答，不超过 30 个字。")

QUESTIONS = [
    "Rust 的所有权是什么？",
    "React 的 hooks 是什么？",
    "Python 的 GIL 是什么？",
]


async def main() -> None:
    header("02 async", model)

    # 单次异步调用
    # agent.run(...) 只是「创建」一个协程对象，此时还没发请求；
    # await 才会驱动它执行，并在等待网络响应时把控制权让给事件循环。
    # 这点像 Rust 的 Future（惰性），不像 JS 的 Promise（创建即开始执行）。
    result = await agent.run(QUESTIONS[2])
    print(result.output)

    # 并发调用：同一个 agent 可以同时跑多个 run，互不影响
    # （Agent 本身无状态，每次 run 的消息历史都是独立的）
    start = time.perf_counter()  # 高精度单调时钟，适合测耗时 ≈ performance.now() / Instant::now()

    # 这一行拆成三步看：
    #
    # 1) (agent.run(q) for q in QUESTIONS)
    #    生成器表达式，产出 3 个协程对象。此时一个请求都没发出去。
    #
    # 2) asyncio.gather(*...)
    #    * 把生成器展开成位置参数，等价于
    #    gather(agent.run(Q[0]), agent.run(Q[1]), agent.run(Q[2]))。
    #    gather 把每个协程包装成 Task 并注册到事件循环，3 个请求从这里开始「同时在飞」。
    #
    # 3) await
    #    挂起 main，直到 3 个 Task 全部完成，拿到结果列表。
    #    结果顺序 = 传入顺序，与谁先返回无关（和 Promise.all 一样）。
    #
    # 注意这是单线程并发，不是多线程并行：
    # 事件循环在一个线程里轮流推进各个 Task，谁在等网络就切到别人。
    # LLM 调用几乎全是网络等待，所以总耗时 ≈ 最慢的那一个，而不是三者之和。
    #
    # 异常行为：任一请求抛异常，await 会立刻抛出第一个异常，
    # 但其余 Task 不会被取消，仍在后台跑完。
    # 想拿到「每个的成功或失败」用 gather(..., return_exceptions=True) ≈ Promise.allSettled。
    results = await asyncio.gather(*(agent.run(q) for q in QUESTIONS))
    elapsed = time.perf_counter() - start

    # zip 把问题和结果按位置配对；strict=True 表示两边长度不一致就报错，
    # 而不是默默截断到较短的那个。
    for question, r in zip(QUESTIONS, results, strict=True):
        console.print(f"[bold]{question}[/]")
        print(r.output)
    console.print(f"[dim]{len(QUESTIONS)} 个请求并发耗时 {elapsed:.1f}s[/]")


if __name__ == "__main__":
    # 同步世界进入异步世界的唯一入口：创建事件循环，跑完 main() 后关闭。
    # ≈ tokio 的 Runtime::block_on / #[tokio::main]。
    # JS 没有对应物，因为 JS 的事件循环是运行时自带、一直在跑的。
    asyncio.run(main())
