"""DeepSeek API 客户端（OpenAI 兼容格式）"""

from openai import OpenAI
from core.database import get_connection


def get_client() -> OpenAI | None:
    """获取配置好的 DeepSeek 客户端"""
    conn = get_connection()
    row = conn.execute("SELECT value FROM settings WHERE key = 'api_key'").fetchone()
    conn.close()
    if not row:
        return None
    from core.security import decrypt
    api_key = decrypt(row["value"])
    return OpenAI(api_key=api_key, base_url="https://api.deepseek.com")


def get_api_key() -> str | None:
    """获取解密后的 API Key"""
    conn = get_connection()
    row = conn.execute("SELECT value FROM settings WHERE key = 'api_key'").fetchone()
    conn.close()
    if not row:
        return None
    from core.security import decrypt
    return decrypt(row["value"])


def _get_setting(key: str, default: str = "") -> str:
    """从数据库读取设置"""
    conn = get_connection()
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else default


def get_model_fast() -> str:
    """获取快速模型名称"""
    return _get_setting("model_fast", "deepseek-v4-flash")


def get_model_pro() -> str:
    """获取推理模型名称"""
    return _get_setting("model_pro", "deepseek-v4-pro")


def chat_stream(system_prompt: str, user_message: str = "", model: str = "", messages: list = None):
    """流式对话，逐段 yield 文本。支持单条消息或多轮对话（传入 messages 列表）。"""
    if not model:
        model = get_model_fast()
    client = get_client()
    if not client:
        yield "❌ 未配置 API Key，请在设置页面输入 DeepSeek API Key。"
        return
    if messages is None:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]
    else:
        messages = [{"role": "system", "content": system_prompt}] + messages
    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            stream=True,
            max_tokens=4096,
            temperature=0.3,
        )
        for chunk in response:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    except Exception as e:
        yield f"\n\n❌ API 调用失败：{str(e)}"


def chat_vision_stream(system_prompt: str, user_message: str, image_base64: str, model: str = ""):
    """带图片的流式对话（Vision API）"""
    if not model:
        model = get_model_fast()
    client = get_client()
    if not client:
        yield "❌ 未配置 API Key，请在设置页面输入 DeepSeek API Key。"
        return
    content = [
        {"type": "text", "text": user_message},
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}},
    ]
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": content},
            ],
            stream=True,
            max_tokens=4096,
            temperature=0.3,
        )
        for chunk in response:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    except Exception as e:
        yield f"\n\n❌ API 调用失败：{str(e)}"


def chat_sync(system_prompt: str, user_message: str, model: str = "") -> str:
    """非流式对话，返回完整响应"""
    if not model:
        model = get_model_pro()
    client = get_client()
    if not client:
        return "❌ 未配置 API Key。"
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            max_tokens=4096,
            temperature=0.3,
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"❌ API 调用失败：{str(e)}"
