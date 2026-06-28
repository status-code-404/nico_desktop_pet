# Desktop Pet Nicole — 桌面宠物妮可

基于 Python 的全栈桌面宠物，角色为《原神》魔女会成员妮可（Nicole / N，6.6 版本角色）。

🎬 **视频演示**：https://b23.tv/evQQJIY

> **当前仅支持 macOS**。Windows 版本开发中，敬请期待。

## v2 更新 (2026-06)

- **全双工 LLM+TTS** — LLM 边出字边送 TTS 合成，不等全文，首音延迟 ~1.5s
- **豆包双向流式 TTS** — Volcengine SeedTTS binary framing 协议，单 WS 连接内并发收发
- **豆包流式 ASR** — WebSocket 边录边传，停录即得文本 (~200ms)
- **FIFO 流式播放** — 前端 named pipe → ffmpeg 解码 → pyaudio 即时播放，首块即出声
- **妮可 6.6 完整人设** — 弃声的天使、魔女会 N、六千岁话痨，纯语音风格
- **Whisper 预热** — 启动时预加载模型，首次 STT 不再等待 6s

## 功能

- **LLM 对话** — deepseek-chat，妮可角色人设，流式输出
- **语音交互** — Whisper / 豆包流式 ASR + 豆包双工 TTS（全双工，~1.5s 首音）
- **联网搜索** — Tavily 搜索 API 注入，实时天气/车票/酒店/新闻查询
- **透明桌面动画** — PyQt6 帧动画，四状态（待机/提问/思考/回答），可拖拽
- **打断响应** — 新输入/录音时自动取消当前播放和请求
- **音频清理** — 后台自动清理超过 10 分钟的临时音频

## 项目结构

```
├── server/                # FastAPI 入口
│   ├── main.py            # 启动 + 后台音频清理 + Whisper 预热
│   ├── config.py          # 全局配置 (.env → pydantic)
│   ├── routes.py          # 所有 API + WebSocket 路由
│   └── schemas.py         # Pydantic 数据模型
├── service/               # 业务逻辑层
│   ├── voice.py           # 语音服务 (STT 调度 + LLM + TTS 全双工)
│   ├── chat.py            # 对话服务
│   ├── face.py            # 人脸服务 (检测/识别/喝水)
│   └── drink_water.py     # 喝水提醒 (TODO)
├── core/                  # 基础模块
│   ├── llm/               # DeepSeek client + Nicole 角色提示词
│   ├── stt/               # Whisper / 豆包流式 ASR
│   ├── tts/               # 豆包双工 TTS / 阿里云 TTS
│   └── vision/            # 人脸检测/识别
├── frontend/              # PyQt6 桌面宠物
│   ├── main.py            # 入口 (读取 .env 配置尺寸/FPS)
│   └── pet_window.py      # 透明窗口 + 帧动画 + 输入框 + 对话气泡 + 语音
│       └─ FIFO + ffmpeg + pyaudio 流式播放
├── resources/             # 素材
│   ├── frames/            # 帧动画 (normal/question/thinking/answering)
│   ├── mov/               # 原始 ProRes 4444 MOV
│   └── audio/             # 妮可语音参考
├── data/                  # 模型 + 运行时数据 (gitignored)
├── result/audio/          # 生成的 TTS 音频 (gitignored)
├── .env.example           # 脱敏配置模板
├── requirements.txt       # Python 依赖
├── start.sh               # 一键启动 (前后端 + 退出全杀)
└── README.md
```

## 安装

> 以下步骤在 macOS 上一键完成，Windows 暂不支持。

### 第一步：克隆 + 装依赖
```bash
git clone https://github.com/status-code-404/nico_desktop_pet.git
cd nico_desktop_pet
pip install -r requirements.txt
```

### 第二步：装语音录制依赖
```bash
brew install portaudio
pip install pyaudio
```

### 第三步：配置 API Key
```bash
cp .env.example .env
vim .env
```

**必须填写的 Key：**

| Key | 用途 | 去哪获取 |
|-----|------|---------|
| `DEEPSEEK_API_KEY` | LLM 对话推理 | https://platform.deepseek.com |
| `VOLCENGINE_TTS_API_KEY` | TTS 语音合成（豆包） | https://console.volcengine.com/speech |
| `TAVILY_API_KEY` | 联网搜索 | https://tavily.com |

**可选 Key：**

| Key | 用途 |
|-----|------|
| `VOLCENGINE_ASR_API_KEY` | 豆包流式 ASR（不填则用本地 Whisper） |

### 第四步：启动
```bash
bash start.sh
```

> 首次运行会自动下载 Whisper 模型（~140MB），后续无需重复下载。
> ffmpeg 已内置在 `backend/bin/`，无需额外安装。

## 可选配置

| 变量 | 默认 | 说明 |
|------|------|------|
| `STT_PROVIDER` | whisper | whisper / volcengine |
| `TTS_PROVIDER` | volcengine | volcengine / aliyun / local |
| `CHAT_MEMORY_ENABLED` | false | 对话上下文 |
| `CHAT_SEARCH_ENABLED` | true | 联网搜索 |
| `DEBUG_VOICE` | false | 打印语音转录 |
| `PET_WIDTH` | 180 | 宠物尺寸 |
| `PET_FPS` | 24 | 动画帧率 |
| `DRINK_REMINDER_HOURS` | 1.5 | 喝水提醒间隔 |

## 启动

```bash
bash start.sh                    # 一键启动 (Ctrl+C 关闭全部)
# 或分别启动：
python server/main.py            # 后端 :8000
cd frontend && python main.py    # 前端
```

## API

| 端点 | 说明 |
|------|------|
| `POST /api/v1/chat` | 妮可文字对话 |
| `POST /api/v1/chat/stream` | 流式对话 (SSE) |
| `DELETE /api/v1/chat/history` | 清空上下文 |
| `POST /api/v1/voice/transcribe` | 语音转文字 |
| `POST /api/v1/voice/tts` | TTS（流式 NDJSON） |
| `POST /api/v1/voice/tts/stream` | TTS 全双工流（audio/mpeg） |
| `POST /api/v1/voice/chat/audio` | 语音对话（音频返回） |
| `WS /api/v1/voice/ws/transcribe` | 流式 ASR（WebSocket 边录边传） |
| `POST /api/v1/face/detect` | 人脸检测 |
| `POST /api/v1/face/register` | 注册人脸 |
| `POST /api/v1/face/recognize` | 识别人脸 |
| `GET /api/v1/health` | 健康检查 |

## 性能 (v2)

| 场景 | LLM 首token | TTS 首音 | 总首音 |
|------|-----------|---------|--------|
| 打招呼 (非搜索) | ~700ms | ~800ms | **~1.5s** |
| 搜索查询 | ~700ms + 2s 搜索 | ~800ms | **~3.5s** |
| 语音识别 (豆包 ASR) | — | — | **~200ms** |
| 语音识别 (Whisper) | — | — | **~1.8s** |

## 架构

```
录音 → WebSocket 流式 ASR → 停录即得文本
文字 → POST /voice/tts/stream
         ├─ LLM chat_stream (DeepSeek) ────┐
         └─ TTS duplex_stream (Volcengine) ─┘ 并发双工
              → HTTP audio/mpeg stream
                → 前端 FIFO → ffmpeg 解码 → pyaudio 播放
```

## License

MIT
