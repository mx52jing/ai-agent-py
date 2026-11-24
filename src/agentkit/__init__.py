"""各示例共用的薄封装：配置读取、模型创建、终端输出。"""

from .config import ConfigError, Profile, load_profile
from .console import console, header
from .models import build_model, get_model

__all__ = [
    "ConfigError",
    "Profile",
    "build_model",
    "console",
    "get_model",
    "header",
    "load_profile",
]
