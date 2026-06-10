# Desktop Pet Nicole — 桌面宠物妮可

基于 Python 的全栈桌面宠物，角色为《原神》魔女会成员妮可（Nicole / N）。

> **当前仅支持 macOS**。Windows 版本开发中，敬请期待。

## 功能

- **LLM 对话** — deepseek-v4-flash，妮可角色人设，可配置上下文记忆
- **语音交互** — Whisper 语音识别 + 阿里云 CosyVoice 声音克隆（流式 TTS，3 路并发生成）
- **联网搜索** — Tavily 搜索 API 注入，实时天气/车票/酒店/新闻查询
- **透明桌面动画** — PyQt6 帧动画，四状态（待机/提问/思考/回答），可拖拽
- **打断响应** — 新输入/录音时自动取消当前播放和请求
- **音频清理** — 后台自动清理超过 10 分钟的临时音频

## 项目结构

```
├── server/                # FastAPI 入口
│   ├── main.py            # 启动 + 后台音频清理
│   ├── config.py          # 全局配置 (.env → pydantic)
│   ├── routes.py          # 所有 API 路由
│   └── schemas.py         # Pydantic 数据模型
├── service/               # 业务逻辑层
│   ├── chat.py            # 对话服务
│   ├── voice.py           # 语音服务 (STT + LLM + TTS 分片/并发/流式)
│   ├── face.py            # 人脸服务 (检测/识别/喝水)
│   └── drink_water.py     # 喝水提醒 (TODO)
├── core/                  # 基础模块
│   ├── llm/               # DeepSeek client + Nicole 角色提示词
│   ├── stt/               # Whisper 语音转文字
│   ├── tts/               # 阿里云/本地 TTS
│   └── vision/            # 人脸检测/识别
├── frontend/              # PyQt6 桌面宠物
│   ├── main.py            # 入口 (读取 .env 配置尺寸/FPS)
│   └── pet_window.py      # 透明窗口 + 帧动画 + 输入框 + 对话气泡 + 语音
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

**必须填写的 3 个 Key：**

| Key | 去哪获取 |
|-----|---------|
| `DEEPSEEK_API_KEY` | https://platform.deepseek.com |
| `DASHSCOPE_API_KEY` | https://bailian.console.aliyun.com |
| `TAVILY_API_KEY` | https://tavily.com （免费 1000 次/月） |

### 第四步：启动
```bash
bash start.sh
```

> 首次运行会自动下载 Whisper 模型（~140MB），后续无需重复下载。
> ffmpeg 已内置在 `backend/bin/`，无需额外安装。

## 可选配置

| 变量 | 默认 | 说明 |
|------|------|------|
| `CHAT_MEMORY_ENABLED` | false | 对话上下文 |
| `CHAT_SEARCH_ENABLED` | true | 联网搜索 |
| `TTS_PROVIDER` | aliyun | aliyun / local |
| `TTS_CONCURRENCY` | 3 | TTS 并发数 |
| `DEBUG_VOICE` | false | 打印语音转录 |
| `PET_WIDTH` | 180 | 宠物尺寸 |
| `PET_FPS` | 24 | 动画帧率 |

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
| `POST /api/v1/chat/stream` | 流式对话 |
| `DELETE /api/v1/chat/history` | 清空上下文 |
| `POST /api/v1/voice/transcribe` | 语音转文字 |
| `POST /api/v1/voice/chat` | 语音对话（文字返回） |
| `POST /api/v1/voice/tts` | 文字转语音（流式 NDJSON） |
| `POST /api/v1/voice/chat/audio` | 语音对话（音频返回） |
| `POST /api/v1/face/detect` | 人脸检测 |
| `POST /api/v1/face/register` | 注册人脸 |
| `POST /api/v1/face/recognize` | 识别人脸 |
| `GET /api/v1/health` | 健康检查 |

## 性能 (当前配置)

| 场景 | LLM | TTS | 总 |
|------|-----|-----|-----|
| 打招呼 | 4.0s | 2.0s | 6.0s |
| 搜索查询 | 5.6s | ~3s | ~9s |
| 背诵岳阳楼记 (456字) | 6.5s | 11.9s (18片) | 18.4s |

## 注意事项

- **搜索引擎**：Tavily 免费版可能返回过期/不准确的缓存数据（幻读）。日期/时间类查询默认走本地 `datetime`，不依赖搜索。
- **TTS 限流**：阿里云 CosyVoice 免费版 QPS 约 2-3，已配置 3/秒发送速率 + 不限在线并发。若遇到 `Throttling.RateQuota` 错误，调低 `.env` 中的 `TTS_CONCURRENCY`。
- **语音识别**：需要 macOS 授予终端麦克风权限。测试识别效果：`cd server && python test_voice_whisper.py`。
- **本地 TTS**：将 `TTS_PROVIDER=local` 可切换到本地 CosyVoice2-0.5B（需提前下载模型到 `data/models/cosyvoice/`）。

## License

MIT
