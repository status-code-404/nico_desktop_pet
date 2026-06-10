"""
Chat service — text conversation with Nicole.
Uses: core.llm.client
"""

from core.llm.client import llm_client


async def send(message: str) -> str:
    return await llm_client.chat(message)


async def stream(message: str):
    async for chunk in llm_client.chat_stream(message):
        yield chunk


def clear_history():
    llm_client.clear_history()
