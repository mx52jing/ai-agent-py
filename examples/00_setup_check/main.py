"""检查当前 profile 是否可用：打印配置 → 列出中转站支持的模型 → 发一次真实请求。

uv run examples/00_setup_check/main.py
LLM_PROFILE=claude-relay uv run examples/00_setup_check/main.py
"""

import asyncio

from pydantic_ai import Agent

from agentkit import Profile, build_model, console, load_profile


async def list_models(profile: Profile) -> list[str] | None:
    """直接用底层 SDK 调中转站的模型列表接口，返回排好序的模型名。

    这里绕过了 Pydantic AI：它只负责对话，不提供"列出模型"的功能。
    kind = "official" 时不查询，返回 None，和"查了但结果为空"的空列表区分开。
    """
    if profile.kind == "openai-compatible":
        # 在函数内部 import：只有走到这个分支才加载对应的 SDK，
        # 类似 JS 的动态 import()。
        from openai import AsyncOpenAI

        openai_client = AsyncOpenAI(base_url=profile.base_url, api_key=profile.api_key)
        # models.list() 返回异步迭代器，会自动翻页；
        # [... async for ...] 是异步列表推导式，等同 JS 的
        # for await (const m of client.models.list()) ids.push(m.id)
        return sorted([m.id async for m in openai_client.models.list()])
    if profile.kind == "anthropic-compatible":
        from anthropic import AsyncAnthropic

        anthropic_client = AsyncAnthropic(
            base_url=profile.base_url,
            api_key=profile.api_key,
            default_headers={"x-api-key": profile.api_key},  # 原因见 agentkit/models.py
        )
        return sorted([m.id async for m in anthropic_client.models.list()])
    return None


async def main() -> None:
    # 第一步：打印当前配置。不传参数，按 LLM_PROFILE 环境变量或 providers.toml 的 default 选 profile。
    # 配置有问题（文件缺失、profile 名写错、密钥没填）会在这一段抛 ConfigError。
    profile = load_profile()
    # console 是 rich 的 Console：rule() 画一条带标题的分隔线，
    # 字符串里的 [bold]、[red]...[/] 是 rich 的样式标记，不是普通文本。
    console.rule(f"[bold]profile: {profile.name}")
    console.print(f"kind     = {profile.kind}")
    # 地址来自环境变量时，标出变量名，方便知道该去 .env 改哪一项
    base_url_source = f"（来自 {profile.base_url_env}）" if profile.base_url_env else ""
    console.print(f"base_url = {profile.base_url}{base_url_source}")
    console.print(f"model    = {profile.model}")
    # 只显示密钥的前 6 个字符，够确认填的是哪一个，又不会把完整密钥打到终端
    console.print(f"api_key  = {profile.api_key[:6]}…（来自 {profile.api_key_env}）")

    # 第二步：列出中转站支持的模型，用来核对 providers.toml 里的 model 写得对不对
    console.rule("可用模型")
    try:
        names = await list_models(profile)
        # markup=False：按原样输出，不解析样式标记。
        # 模型名、错误信息这类外部内容可能含有方括号，不关掉会被 rich 当成样式。
        if names is None:
            console.print("（官方来源不查询模型列表）")
        else:
            console.print(
                "\n".join(names) if names else "（接口返回了空列表）", markup=False
            )
    # 不少中转站不提供模型列表接口，失败不影响后面的调用。
    # 所以这里捕获所有异常，只提示不退出；noqa 是让 ruff 不要对"捕获范围太宽"报警。
    except Exception as e:  # noqa: BLE001
        console.print(f"[yellow]列出模型失败（可忽略）：{type(e).__name__}[/]")
        console.print(str(e), markup=False)

    # 第三步：发一次真实请求，这才是"能不能用"的最终判断
    console.rule("测试调用")
    try:
        # 最小的 Agent：只有模型，没有系统提示词和工具。run() 发一次请求并等完整回复。
        result = await Agent(build_model(profile)).run("用一句话介绍你自己")
    except Exception as e:
        console.print(f"[red]调用失败：{type(e).__name__}[/]")
        console.print(str(e), markup=False)
        # 以退出码 1 结束，等同 JS 的 process.exit(1)。
        # from e 把原始异常挂为"起因"（类似 JS 的 new Error(msg, { cause: e })）。
        raise SystemExit(1) from e
    console.print(result.output, markup=False)
    # 响应里带的模型名，可能和请求的不一样：中转站有时会把模型名映射到别的模型
    console.print(f"[green]OK[/] 实际响应的模型：{result.response.model_name}")


# 只有直接运行本文件时才执行，被 import 时不执行。
# asyncio.run() 启动事件循环并跑完 main()：Python 没有顶层 await，需要这样进入异步代码。
if __name__ == "__main__":
    asyncio.run(main())
