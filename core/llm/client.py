"""
LLM client — DeepSeek via OpenAI API, with Tavily search injection.
"""

from __future__ import annotations

from collections import deque
from typing import AsyncIterator

from openai import AsyncOpenAI

from server.config import settings
from core.llm.nicole import NICOLE_SYSTEM_PROMPT

_SEARCH_TRIGGERS = [
    "天气", "气温", "预报", "新闻", "股价", "汇率", "最新", "今天", "实时",
    "怎么样", "多少钱", "几度", "多少度", "搜索", "查到", "查找",
    "谁是", "什么是", "什么时候", "几点", "在哪", "如何", "怎么去",
    "车票", "火车", "高铁", "机票", "航班", "多少", "价格",
    "酒店", "住宿", "旅游", "攻略", "景点", "推荐", "好吃", "美食",
    "餐厅", "游玩", "出行",
    "背诵", "朗读", "念", "全文", "诗词",
    "星期", "几号", "日期", "时间",
]


def _should_search(message: str) -> bool:
    return any(kw in message for kw in _SEARCH_TRIGGERS)


def _local_info(message: str) -> str:
    """Return local info for queries that don't need web search."""
    from datetime import datetime
    weekdays = ["星期一","星期二","星期三","星期四","星期五","星期六","星期日"]
    now = datetime.now()
    lines = [f"今天是{now.year}年{now.month}月{now.day}日，{weekdays[now.weekday()]}。"]
    if "几月" in message or "几号" in message or "日期" in message:
        lines.append(f"当前日期：{now.year}-{now.month:02d}-{now.day:02d}")
    return "\n".join(lines)


def _web_search(query: str) -> str:
    try:
        from tavily import TavilyClient
        from datetime import datetime
        client = TavilyClient(api_key=settings.tavily_api_key)
        # Add current year for freshness
        q = f"{query} {datetime.now().year}"
        result = client.search(q, max_results=3, search_depth="basic")
        if not result.get("results"):
            return ""
        return "搜索结果：\n" + "\n".join(
            f"- {r['title']}: {r['content'][:300]}" for r in result["results"]
        )
    except Exception:
        return ""


class LLMClient:

    def __init__(self) -> None:
        self.client = AsyncOpenAI(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
        )
        self.model = settings.deepseek_model
        self._history: deque[dict] = deque(maxlen=settings.chat_history_limit)

    async def chat(self, message: str, *, context: str = "") -> str:
        user_msg = message
        if settings.chat_search_enabled and _should_search(message):
            li = _local_info(message)
            sr = _web_search(message)
            info = "\n".join(filter(None, [li, sr]))
            if info:
                user_msg = f"{message}\n\n{info}"

        if settings.chat_memory_enabled:
            self._history.append({"role": "user", "content": message})

        resp = await self.client.chat.completions.create(
            model=self.model,
            messages=self._build_messages(user_msg, context=context),
            temperature=0.8,
            max_tokens=settings.chat_max_tokens,
        )
        reply = resp.choices[0].message.content or ""

        if settings.chat_memory_enabled:
            self._history.append({"role": "assistant", "content": reply})
        return reply

    async def chat_stream(self, message: str, *, context: str = "") -> AsyncIterator[str]:
        user_msg = message
        if settings.chat_search_enabled and _should_search(message):
            li = _local_info(message)
            sr = _web_search(message)
            info = "\n".join(filter(None, [li, sr]))
            if info:
                user_msg = f"{message}\n\n{info}"

        if settings.chat_memory_enabled:
            self._history.append({"role": "user", "content": message})

        full = ""
        stream = await self.client.chat.completions.create(
            model=self.model,
            messages=self._build_messages(user_msg, context=context),
            temperature=0.8,
            max_tokens=settings.chat_max_tokens,
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta
            if delta.content:
                full += delta.content
                yield delta.content

        if settings.chat_memory_enabled:
            self._history.append({"role": "assistant", "content": full})

    def _build_messages(self, user_message: str, *, context: str = "") -> list[dict]:
        system = NICOLE_SYSTEM_PROMPT
        if context:
            system += f"\n\n## 主人今日活动摘要\n{context}"
        msgs = [{"role": "system", "content": system}]
        if settings.chat_memory_enabled:
            msgs += list(self._history)
        msgs.append({"role": "user", "content": user_message})
        return msgs

    def clear_history(self):
        self._history.clear()


llm_client = LLMClient()
