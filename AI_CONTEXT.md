# AI Context — 给其它大模型看的项目速览

> 本文档写给未来的 AI 助手，帮助你快速理解项目架构、关键决策和踩坑记录。

## 一句话总结

PyQt6 桌面宠物 + FastAPI 后端，角色为原神妮可。LLM 对话 + 语音交互 + Tavily 搜索 + 帧动画。

## 目录结构（只记重点）

```
server/     → FastAPI :8000, 所有路由在 routes.py
service/    → 业务逻辑（chat/voice/face/drink_water）
core/       → 底层能力（llm/stt/tts/vision）
frontend/   → PyQt6 透明窗 + 帧动画
resources/  → frames(537张PNG) + mov + audio
data/       → 模型文件（gitignored，whisper首次自动下载）
.env        → 3个必填Key: DEEPSEEK / DASHSCOPE / TAVILY
start.sh    → 一键启动，Ctrl+C全杀
```

## 数据流

```
用户输入 → PetWindow._on_text()
    → InputBar.lock() + _thinking_done signal
    → threading.Thread → HTTP POST /api/v1/chat
    → service/chat.py → core/llm/client.py (DeepSeek v4-flash + Tavily)
    → 返回文字 → 气泡显示 + HTTP POST /api/v1/voice/tts (stream)
    → NDJSON逐行返前端 → 第一片到达 emit _thinking_done → 切ANSWERING动画
    → 顺序播放 → 播完删临时文件
```

问"背诵岳阳楼记"全链路：LLM 6.5s + TTS 14片×40字 11.9s = 总~18s

## 关键决策

### 前端状态机
- ❌ QThread worker → **SIGABRT OOM**（macOS Qt GC 问题）
- ❌ QTimer.singleShot 跨线程 → **不生效**
- ✅ **pyqtSignal `_thinking_done`** → 主线程 `_think_off` → 可靠

### TTS 并发
- ❌ SpeechSynthesizerObjectPool(20) → 初始化20路WS同时建连 → **Throttling.RateQuota**
- ❌ 复用 Synthesizer → 服务端用完关WS，不可复用
- ✅ **每次新建 SpeechSynthesizer + asyncio.Semaphore(3) + 速率限制3/秒发送**
- 阿里云免费账号 QPS≈3，这是物理上限

### 搜索
- ❌ DuckDuckGo → 太慢
- ✅ Tavily → 免费1000次/月，但有缓存过期（幻读）
- 日期查询直接走 Python `datetime.now()`，不依赖搜索

### LLM
- ❌ Anthropic 代理端点 deepseek-v4-pro → **8.4s** 太慢
- ✅ DeepSeek 原生 API deepseek-v4-flash → **1-4s**
- 记忆可选：`CHAT_MEMORY_ENABLED=true`，滑窗10条

### 音频播放
- `afplay` → `sp.Popen` 异步 → 新输入时 `.kill()`
- 打断：`_cancel_current()` 杀 afplay + close HTTP stream + 设 cancelled flag
- 播完自动 `os.unlink(f)`，另后台线程每2分钟清理超过10分钟的临时文件

### 帧动画
- ProRes 4444 MOV → ffmpeg 提取 RGBA PNG
- 加载时预缩放(180px)，存缩放版，不存原图（OOM 教训）
- 4状态：normal/question/thinking/answering，空文件夹自动退化

## 踩坑清单

| 问题 | 原因 | 解决 |
|------|------|------|
| QThread导致SIGABRT | GC回收运行中的worker | 换threading.Thread |
| 前端无回复 | `_build_messages` 没包含用户消息 | 加 `user_message` 参数 |
| TTS限流 | 并发超QPS | Semaphore(3)+速率限制 |
| 文本分句重复 | `str.index()` 匹配第一处 | 换`enumerate` + 硬切 |
| WS连接复用失败 | 服务端60s关连接 | 放弃复用，每次新建 |
| LLM 不响应搜索 | 触发词里没"星期" | 补充：星期/几号/日期/时间 |
| Tavily返回旧数据 | 免费版缓存 | 日期走datetime，搜索加年份 |

## 配置速查

```bash
DEEPSEEK_API_KEY=sk-xxx      # https://platform.deepseek.com
DASHSCOPE_API_KEY=sk-xxx     # https://bailian.console.aliyun.com
TAVILY_API_KEY=tvly-xxx       # https://tavily.com
TTS_CONCURRENCY=3             # ≤3，阿里云限制
CHAT_SEARCH_ENABLED=true      # 默认开
PET_WIDTH=180                 # 前端尺寸
```

## 启动

```bash
bash start.sh   # 后端:8000 + 前端
```
