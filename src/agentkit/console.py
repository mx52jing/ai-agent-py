"""终端输出辅助。"""

from pydantic_ai.models import Model
from rich.console import Console

console = Console()


def header(title: str, model: Model) -> None:
    """打印示例标题和当前使用的模型，方便确认请求发给了谁。"""
    console.rule(f"[bold]{title}[/]  [dim]{model.system} · {model.model_name}[/]")
