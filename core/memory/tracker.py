"""
Memory tracker — decorator for automatic conversation recording.

Usage:
    @track(user_input_key="text")
    async def chat(text: str): ...

    @track(user_input_key="text", output_attr="reply")
    async def tts_stream(text: str):  # async generator
"""

from __future__ import annotations

import asyncio
import functools
import inspect
from typing import Callable, Any

from . import collector as memory_collector


def track(user_input_key: str | None = None,
          collect_input: Callable | None = None,
          source_user: str = "user",
          source_assistant: str = "assistant"):
    """
    Decorator: auto-record user input + assistant output to memory.

    Works with async generators (streaming) — records in background after
    generator completes. Zero overhead on streaming latency.

    For async generators, use `collect_input` to extract reply text from
    the completed generator state (e.g., lambda gen: gen.reply_text[0]).
    """

    def decorator(func: Callable) -> Callable:
        is_async_gen = inspect.isasyncgenfunction(func)

        if is_async_gen:

            @functools.wraps(func)
            async def wrapper(*args, **kwargs):
                user_text = _extract_input(user_input_key, args, kwargs)
                gen = func(*args, **kwargs)
                async for chunk in gen:
                    yield chunk
                # After stream completes, collect text and record
                if collect_input and user_text:
                    try:
                        reply = collect_input(gen)
                        if reply:
                            asyncio.create_task(_record(user_text, str(reply),
                                                        source_user, source_assistant))
                    except Exception:
                        pass

        else:

            @functools.wraps(func)
            async def wrapper(*args, **kwargs):
                user_text = _extract_input(user_input_key, args, kwargs)
                result = await func(*args, **kwargs)
                if user_text and result:
                    asyncio.create_task(_record(user_text, str(result),
                                                source_user, source_assistant))
                return result

        return wrapper

    return decorator


def _extract_input(key: str | None, args: tuple, kwargs: dict) -> str | None:
    if key is None:
        return None
    # Try kwargs first
    if key in kwargs:
        val = kwargs[key]
        return str(val) if val else None
    # Try first positional arg
    if args:
        return str(args[0]) if args[0] else None
    return None


def _extract_output(result: Any, attr: str | None) -> str | None:
    if result is None:
        return None
    if attr and hasattr(result, attr):
        val = getattr(result, attr)
        return str(val) if val else None
    return str(result) if result else None


async def _record(user: str, assistant: str, src_user: str, src_asst: str):
    """Fire-and-forget: record conversation turn."""
    try:
        memory_collector.record(src_user, user)
        memory_collector.record(src_asst, assistant)
    except Exception:
        pass  # never crash the main flow
