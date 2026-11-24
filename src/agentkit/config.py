"""读取 providers.toml 和 .env，解析出当前要使用的模型来源（profile）。"""

import os
import tomllib
from pathlib import Path
from typing import Any, Literal

from dotenv import load_dotenv
from pydantic import BaseModel

# 项目根目录的绝对路径。
# __file__：Python 自动注入的模块级变量，值是当前 .py 文件的路径（类似 JS 的 __filename）。
# .resolve()：转成绝对路径，并解析软链接和 ".."。
# .parents[2]：向上第三层，config.py -> agentkit -> src -> 项目根。
# 按文件位置定位而不是按 cwd，所以从任何目录运行都能找到 providers.toml 和 .env；
# 但层级是写死的，移动本文件后要同步改这个数字。
ROOT = Path(__file__).resolve().parents[2]
PROVIDERS_FILE = ROOT / "providers.toml"

# 类型别名（不是内置类型）：值只能是这三个字符串之一，
# 等价于 TS 的 type Kind = "openai-compatible" | "anthropic-compatible" | "official"。
# Literal 本身只给类型检查器看，运行时不校验；
# 但 Profile 是 Pydantic 模型，会按这个注解校验，providers.toml 里写了别的值会抛 ValidationError。
Kind = Literal["openai-compatible", "anthropic-compatible", "official"]


class ConfigError(RuntimeError):
    """配置缺失或写错时抛出，消息里会说明该改哪里。"""


class Profile(BaseModel):
    """providers.toml 里的一个 [profiles.<name>] 段。"""

    name: str
    kind: Kind
    model: str
    # 接口地址，两种写法：base_url 直接写地址；base_url_env 写环境变量名，地址放在 .env。
    # 两个都写时，环境变量有值就用环境变量，否则用 base_url。
    # load_profile 会把最终地址填回 base_url，所以使用方只读 base_url 即可。
    base_url: str | None = None
    base_url_env: str | None = None
    api_key_env: str | None = None
    # 仅 kind = "official"：openai / anthropic / deepseek / xai ...
    provider: str | None = None
    # 仅 kind = "openai-compatible"：模型名不是 vendor/model 形式时，指明模型家族
    family: str | None = None

    # @property：把方法变成只读属性，用 profile.api_key 访问而不是 profile.api_key()，
    # 类似 JS 的 getter（get apiKey() { ... }）。
    @property
    def api_key(self) -> str:
        """按 api_key_env 记录的变量名，从环境变量里取出真正的密钥。

        密钥不是模型字段，每次访问时才读取，所以打印或序列化 Profile 时不会带出密钥。
        没配置变量名、或变量没有值时抛 ConfigError。
        """
        if not self.api_key_env:
            raise ConfigError(f"profile '{self.name}' 没有配置 api_key_env")
        # .get() 在变量不存在时返回 None 而不是抛异常，类似 JS 的 process.env.X 得到 undefined
        key = os.environ.get(self.api_key_env)
        # 变量不存在（None）和值为空字符串都算没设置
        if not key:
            raise ConfigError(
                f"环境变量 {self.api_key_env} 未设置，请在 {ROOT / '.env'} 里填写（参考 .env.example）"
            )
        return key


# 参数列表里单独的 * 表示它后面的参数只能用关键字传：
# load_profile("claude-relay", model="xxx") 可以，load_profile("claude-relay", "xxx") 会报错。
def load_profile(name: str | None = None, *, model: str | None = None) -> Profile:
    """读取 .env 和 providers.toml，返回要使用的 Profile。

    优先级：函数参数 > 环境变量 LLM_PROFILE / LLM_MODEL > providers.toml 默认值。

    name：profile 名，即 providers.toml 里 [profiles.<name>] 的 <name>。
    model：临时覆盖该 profile 里写的模型名。
    配置文件缺失、没指定 profile、profile 名不存在、
    或 base_url_env 指向的环境变量没有值（且没写 base_url）时抛 ConfigError。
    """
    # 把 .env 里的键值加载进 os.environ；已存在的环境变量不会被覆盖，
    # 所以命令行里写的 LLM_PROFILE=xxx 优先于 .env。
    load_dotenv(ROOT / ".env")

    if not PROVIDERS_FILE.exists():
        raise ConfigError(f"找不到 {PROVIDERS_FILE}")
    # tomllib 是标准库的 TOML 解析器，结果是嵌套的 dict
    data = tomllib.loads(PROVIDERS_FILE.read_text(encoding="utf-8"))
    # 所有 [profiles.xxx] 段：{"openai-relay": {...}, "claude-relay": {...}}
    profiles: dict[str, dict[str, Any]] = data.get("profiles", {})

    # or 链返回第一个"真值"，等同 JS 的 a || b || c
    name = name or os.environ.get("LLM_PROFILE") or data.get("default")
    if not name:
        raise ConfigError(
            "没有指定 profile：设置 LLM_PROFILE，或在 providers.toml 里写 default"
        )
    if name not in profiles:
        raise ConfigError(
            f"providers.toml 里没有 profile '{name}'，可选：{', '.join(profiles)}"
        )

    # **dict 是展开，等同 JS 的 { name, ...profiles[name] }；name 来自段名，不在段内容里。
    # model_validate 按字段类型校验这个 dict 并构造 Profile，不合法时抛 ValidationError。
    profile = Profile.model_validate({"name": name, **profiles[name]})
    # := 是"赋值并判断"：算出覆盖用的模型名赋给 model，非空才进入分支，
    # 类似 Rust 的 if let Some(model) = ...
    if model := model or os.environ.get("LLM_MODEL"):
        profile.model = model

    # 写了 base_url_env 时，从环境变量取地址填进 base_url；
    # 变量没有值就保留 toml 里直接写的 base_url，两边都没有才报错。
    if profile.base_url_env:
        if url := os.environ.get(profile.base_url_env):
            profile.base_url = url
        elif not profile.base_url:
            raise ConfigError(
                f"环境变量 {profile.base_url_env} 未设置，请在 {ROOT / '.env'} 里填写（参考 .env.example）"
            )
    return profile
