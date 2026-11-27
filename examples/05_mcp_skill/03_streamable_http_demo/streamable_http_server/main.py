# 演示同一个 POST 端点如何返回普通 JSON 或 SSE 流。
# 请求体和 SSE 事件使用自定义格式，尚未实现标准 MCP 的 JSON-RPC 消息和工具发现。
import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import asdict, dataclass
import json
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse
import uvicorn

app = FastAPI()

@dataclass
class Progress:
    # 用独立类型区分「执行中的进度」和「最终结果字典」。
    done: int
    total: int
    message: str

# 用内存数据模拟 issue 查询，无需连接 GitHub 或数据库。
FAKE_ISSUES={
    22: {
        "title": "登录偶发500",
        "state": "open",
        "author": "jak",
        "comments": 8
    }
}

async def get_issue(args: dict[str, Any]) -> dict[str, Any]:
    # 普通异步工具：调用后得到协程，await 后一次性拿到结果字典。
    issue_id = args.get("issue_id")
    issue = FAKE_ISSUES.get(issue_id)
    if issue is None:
        # 这里返回业务错误数据；外层仍会把它包装成 HTTP 200 的 result。
        return { "error": f"id 为{issue_id}的 issue 不存在" }
    return { "issue_id": issue_id, **issue }

# 模拟需要汇总的 PR 总数，每批处理 50 个。
TOTAL = 500
async def summarize_prs(args: dict[str, Any]) -> AsyncIterator[Progress | dict[str, Any]]:
    # async def 中包含 yield，因此这是异步生成器，要用 async for 逐项读取。
    months = args.get("months", 3)
    for done in range(50, TOTAL + 1, 50):
        # 模拟耗时 I/O；等待期间让出事件循环，其他请求仍可继续处理。
        await asyncio.sleep(1)
        yield Progress(done, TOTAL, f"已读 {done} / 共{TOTAL} 个PR")
    # 最终结果也通过 yield 交给外层；随后生成器结束，响应流随之关闭。
    yield { "summary":  f"最近{months}个月合并进main分支的{TOTAL}个 PR功能 210 个，修复 200个，其他90个" }


@dataclass
class Tool:
    # 两种处理函数：返回可等待结果的函数，或返回异步迭代器的函数。
    handler: Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]|Callable[[dict[str, Any]], AsyncIterator[Any]]
    # 注册时必须与 handler 配对：False 用 await，True 用 async for。
    # 这是运行时约定，独立的 bool 字段无法让类型检查器缩小上面的联合类型。
    streaming: bool

# 将请求中的工具名映射到处理函数及其调用方式。
TOOLS = {
   "get_issue": Tool(get_issue, False),
   "summarize_prs": Tool(summarize_prs, True)
}

def sse(event: str, data: dict[str, Any]) -> str:
    """拼一个 SSE 事件：event 区分类型，data 放 JSON"""
    # 一个事件以空行（\n\n）结束；ensure_ascii=False 让中文保持可读。
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

async def stream_tool_call(tool_name: str, tool: Tool, args: dict[str, Any]) -> AsyncIterator[str]:
    # 把工具产出的 Python 对象逐项转换成 SSE 文本，交给 StreamingResponse 发送。
    try:
        async for item in tool.handler(args):
            if isinstance(item, Progress):
                print(f"Server 【{tool_name}】 推进度: {item.message}")
                # dataclass 先转成字典，才能交给 json.dumps 序列化。
                yield sse("progress", asdict(item))
            else:
                # 按本例约定，非 Progress 的项就是最终结果字典。
                print(f"Server 【{tool_name}】 最终结果: {item}")
                yield sse("result", item)
    except asyncio.CancelledError:
        # 当前 Uvicorn/Starlette 组合会在客户端断开时取消流任务，
        # 取消可在工具的 await 处传播到这里；服务关闭等情况也可能触发取消。
        print(f"Server {tool_name}: 客户端关掉了流，停止干活")
        # 记录后继续抛出，让上层完成取消和清理，不要吞掉取消信号。
        raise

@app.post("/mcp")
async def handle_mcp(request: Request) -> Response:
    # 自定义请求示例：{"name": "get_issue", "arguments": {"issue_id": 22}}。
    # 本例尚未做参数校验，假定请求体和 arguments 都是 JSON 对象。
    body = await request.json()
    tool_name = body.get("name")
    args = body.get("arguments", {})
    tool = TOOLS.get(tool_name)
    if tool is None:
        return JSONResponse({"error": f"工具 {tool_name} 不存在"}, status_code=404)
    if not tool.streaming:
        # 快工具：等待执行完成，再一次性返回 application/json。
        print(f"Server: {tool_name} 直接返回 json")
        return JSONResponse({ "result": await tool.handler(args) })
    # 流式工具：把生成器交给框架消费，结果仍从本次 POST 的响应体返回。
    # 不需要额外建立 GET /sse 连接，也不在这里等待所有进度收集完毕。
    print(f"Server: {tool_name}  将 回复 SSE 流")
    return StreamingResponse(
        stream_tool_call(tool_name, tool, args),
        media_type="text/event-stream",
        # no-cache 要求缓存复用前重新验证；X-Accel-Buffering: no 提示 Nginx 关闭缓冲。
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
    
def main() -> None:
    # 仅监听本机，测试地址为 http://127.0.0.1:8900/mcp。
    uvicorn.run(app, host="127.0.0.1", port=8900)

if __name__ == "__main__":
    main()

