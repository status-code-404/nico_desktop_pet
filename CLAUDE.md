# Desktop Pet Nicole

## 架构
```
server/ (FastAPI) → service/ (业务层) → core/ (基础模块)
frontend/ (PyQt6)  ← HTTP + SSE/NDJSON
```

## 关键配置 (.env)
- `DEEPSEEK_API_KEY` — LLM (deepseek-v4-flash)
- `DASHSCOPE_API_KEY` — TTS (cosyvoice-v3.5-flash)
- `TAVILY_API_KEY` — 搜索
- `TTS_CONCURRENCY` — TTS 并发 (当前3)
- `CHAT_SEARCH_ENABLED` — 默认 true
- `PET_WIDTH` / `PET_FPS` — 前端配置

## TTS 机制
- 40字/片，3/秒发送速率控制，不限并发在线
- `core/tts/aliyun.py` — 每片独立 SpeechSynthesizer，用完即弃
- `service/voice.py` — 分句 + create_task 并发 + async generator 流式 yield

## 前端关键
- 信号驱动: `_thinking_done` signal → main thread → `_think_off`
- 打断: `_cancel_current` 杀 afplay + 关 HTTP stream + 设 cancelled flag
- 动画: normal → question → thinking(loop) → answering(loop) → normal

## 启动
```bash
bash start.sh  # 后端:8000 + 前端, Ctrl+C 全杀
```
