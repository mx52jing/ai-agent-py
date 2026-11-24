"""把 profile 变成 Pydantic AI 的模型对象。所有示例都通过 get_model() 拿模型。"""

from collections.abc import Callable

from anthropic import AsyncAnthropic
from pydantic_ai.models import Model, infer_model
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.profiles import ModelProfile, merge_profile
from pydantic_ai.profiles.anthropic import anthropic_model_profile
from pydantic_ai.profiles.deepseek import deepseek_model_profile
from pydantic_ai.profiles.google import google_model_profile
from pydantic_ai.profiles.grok import grok_model_profile
from pydantic_ai.profiles.openai import (
    OpenAIJsonSchemaTransformer,
    OpenAIModelProfile,
    openai_model_profile,
)
from pydantic_ai.providers.anthropic import AnthropicProvider
from pydantic_ai.providers.openai_compatible import OpenAICompatibleProvider

from .config import ConfigError, Profile, load_profile

# 名词区分：
# - Profile（本项目，config.py）：providers.toml 里的一个模型来源，记录地址、密钥、模型名。
# - ModelProfile（Pydantic AI）：一个模型的"能力说明"，是个 dict，
#   描述该模型支持哪种结构化输出、工具的 JSON Schema 要怎么改写、思考内容怎么处理等。
#   Pydantic AI 构造请求时会查它，所以配错了会导致工具调用或结构化输出失败。

# providers.toml 里 family 字段的可选值 -> 该家族的 ModelProfile 生成函数。
# 值的类型 Callable[[str], ModelProfile | None] 等同 TS 的 (modelName: string) => ModelProfile | null：
# 传入模型名，返回这个模型的能力说明（不认识的模型名返回 None）。
_FAMILY_PROFILES: dict[str, Callable[[str], ModelProfile | None]] = {
    "openai": openai_model_profile,
    "anthropic": anthropic_model_profile,
    "deepseek": deepseek_model_profile,
    "grok": grok_model_profile,
    "google": google_model_profile,
}


def _family_profile(family: str) -> Callable[[str], ModelProfile | None]:
    """中转站的模型名不带 vendor/ 前缀时，告诉 Pydantic AI 按哪个模型家族来构造请求。"""
    if family not in _FAMILY_PROFILES:
        raise ConfigError(
            f"未知的 family '{family}'，可选：{', '.join(_FAMILY_PROFILES)}"
        )
    family_func = _FAMILY_PROFILES[family]

    # 闭包：内层函数捕获了外层的 family_func，和 JS 的闭包一样。
    # 这里不直接返回 family_func，是因为还要垫一层 OpenAI 兼容接口的通用设置。
    def profile(model_name: str) -> ModelProfile | None:
        # merge_profile 等同 JS 的 { ...base, ...override }，后面的覆盖前面的，None 当空对象。
        # 底层：请求走的是 OpenAI 格式的接口，工具的 JSON Schema 先按 OpenAI 的规则改写；
        # 上层：模型家族自己的设置（比如 google 家族会换成自己的 Schema 改写器）。
        return merge_profile(
            OpenAIModelProfile(json_schema_transformer=OpenAIJsonSchemaTransformer),
            family_func(model_name),
        )

    return profile


def build_model(profile: Profile) -> Model:
    """按 profile.kind 选择接口协议，构造对应的模型对象。

    Pydantic AI 里分两层：Model 负责协议（请求和响应长什么样），
    Provider 负责连接（发到哪个地址、带什么密钥）。下面每个分支都是"Model + Provider"的组合。
    """
    # match / case 类似 Rust 的 match，但 Python 不检查是否穷尽。
    # 这里没有兜底分支也安全：kind 的取值在 Profile 构造时已被 Pydantic 校验过。
    match profile.kind:
        # 中转站，OpenAI 规范（/chat/completions）
        case "openai-compatible":
            if not profile.base_url:
                raise ConfigError(
                    f"profile '{profile.name}' 缺少 base_url 或 base_url_env"
                )
            return OpenAIChatModel(
                profile.model,
                provider=OpenAICompatibleProvider(
                    # 中转站的名字，只用于标记响应来源和日志
                    profile.name,
                    base_url=profile.base_url,
                    api_key=profile.api_key,
                    # 不传（None）时用默认规则：模型名是 vendor/model 形式就按 vendor 取能力说明，
                    # 否则用 OpenAI 兼容接口的通用设置。
                    # 传函数时完全替换默认规则，所以 _family_profile 里要自己垫 OpenAI 那一层。
                    profile=_family_profile(profile.family) if profile.family else None,
                ),
            )
        # 中转站，Claude 规范（/v1/messages）
        case "anthropic-compatible":
            if not profile.base_url:
                raise ConfigError(
                    f"profile '{profile.name}' 缺少 base_url 或 base_url_env"
                )
            # anthropic SDK 2.x 把密钥放在 Authorization: Bearer 里发送；
            # 不少中转站仍按旧约定读 x-api-key，所以两个头都带上。
            client = AsyncAnthropic(
                base_url=profile.base_url,
                api_key=profile.api_key,
                default_headers={"x-api-key": profile.api_key},
            )
            # 需要自定义请求头，所以自己建 SDK 客户端再交给 Provider，
            # 而不是让 Provider 按 base_url / api_key 自动创建。
            return AnthropicModel(
                profile.model, provider=AnthropicProvider(anthropic_client=client)
            )
        # 官方接口：拼成 "openai:gpt-5" 这样的字符串，由 Pydantic AI 自己选 Model 和 Provider
        case "official":
            if not profile.provider:
                raise ConfigError(f"profile '{profile.name}' 缺少 provider")
            # 官方来源由 Pydantic AI 自己读取各家的环境变量（OPENAI_API_KEY 等）
            return infer_model(f"{profile.provider}:{profile.model}")


def get_model(profile: str | None = None, *, model: str | None = None) -> Model:
    """返回当前 profile 对应的模型对象。

    不传参数时：用环境变量 LLM_PROFILE / LLM_MODEL，否则用 providers.toml 的默认值。
    """
    # 两步：load_profile 读配置得到 Profile（数据），build_model 把它变成 Model（可调用的对象）
    return build_model(load_profile(profile, model=model))
