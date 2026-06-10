# 开发历程 & 成本分析

## 项目概况

桌面宠物妮可（Nicole），基于《原神》魔女会成员 N 的角色设定，全栈 Python 实现。

- **开发时间**：2026年6月
- **平台**：macOS（Windows 适配中）
- **开源地址**：https://github.com/status-code-404/nico_desktop_pet

---

## 技术架构

```
用户输入（文字/语音）
    │
    ▼
┌─────────────────────────────────────┐
│  前端 (PyQt6)                       │
│  - 透明桌面动画 (170帧×4状态)        │
│  - 语音采集 (PyAudio)               │
│  - 对话气泡 & 音频播放               │
│  - 状态机: 普通→提问→思考→回答       │
└──────────────┬──────────────────────┘
               │ HTTP + SSE/NDJSON
               ▼
┌─────────────────────────────────────┐
│  后端 (FastAPI :8000)               │
│  ┌─────────────────────────────┐    │
│  │ service/chat   → LLM 对话   │    │
│  │ service/voice  → STT+TTS    │    │
│  │ service/face   → 人脸识别   │    │
│  └─────────────────────────────┘    │
└──────────────┬──────────────────────┘
               │
    ┌──────────┼──────────┬──────────┐
    ▼          ▼          ▼          ▼
 DeepSeek   Whisper   CosyVoice   Tavily
 (LLM)     (STT)     (TTS)      (搜索)
```

### 链路延迟（背诵岳阳楼记 456字）

| 阶段 | 耗时 | 说明 |
|------|------|------|
| LLM 推理 | 6.5s | deepseek-v4-flash, 512 tokens |
| TTS 分片 | 11.9s | 14片×40字, 3/秒发送, 不限并发 |
| 首片播放 | 4.5s | 流式播放, 第一片到达即播 |
| 状态切换 | 2s | 思考→回答动画延迟 |

---

## 开发历程

### 第一天：后端骨架 + LLM 对话
- FastAPI 框架搭建，pydantic-settings 配置管理
- DeepSeek API 接入（最初用 deepseek-chat，后切 v4-flash）
- 妮可角色提示词编写（基于原神世界观）

### 第二天：语音管线
- Whisper base 本地语音识别，ffmpeg 音频处理
- 阿里云 CosyVoice TTS —— 从本地 CosyVoice2-0.5B 折腾到云端 API
- 声音克隆：上传 58s 妮可语音 → DashScope VoiceEnrollment → voice_id
- 经历：本地模型太慢(RTF 2.5x) → 切云端 → v3-plus 限流 → 降 v3.5-flash

### 第三天：前端桌面宠物
- PyQt6 透明窗口 + 帧动画（从 ProRes 4444 MOV 提取 536 帧 PNG）
- Seedance1.5 生成四组动画素材（待机/提问/思考/回答）
- 输入框、对话气泡、语音录制
- 状态机反复调试：QThread SIGABRT → threading.Thread + QTimer → pyqtSignal

### 第四天：性能优化 & TTS 并发
- TTS 从单路 13s → 3并发信号量 27s → 速率限制 3/秒 11.9s
- 经历：SpeechSynthesizerObjectPool(20) 限流 → 手动池 → 最终 fresh synth + rate limiter
- WebSocket 复用：服务器60s超时关闭，不可行
- 阿里云 QPS 硬限制 ~3，提客服工单中

### 第五天：搜索 & 细节打磨
- DuckDuckGo → Tavily（更快但免费版有缓存过期问题）
- 日期查询直接走 `datetime`，不依赖搜索
- 分词/重复句 bug 修复，改为硬切+句末调整
- 播放打断、音频清理、对话记忆

---

## 成本分析

### 开发成本（一次性）

| 项目 | 费用 | 说明 |
|------|------|------|
| DeepSeek API | ~15 元 | v4-flash 开发期间调用消耗 |
| 阿里云 CosyVoice | ~20 元 | 百炼全模型包（含 v3-plus/v3.5-flash） |
| Seedance1.5 | 0 元 | 免费额度生成动画素材 |
| Tavily | 0 元 | 免费版 1000次/月 |
| **开发总计** | **~35 元** | |

### 运行成本（月均估算）

| 项目 | 单价 | 月用量估算 | 月费 |
|------|------|------|------|
| DeepSeek v4-flash 输入 | 1元/百万token | ~30万token | ~0.3元 |
| DeepSeek v4-flash 输出 | 2元/百万token | ~15万token | ~0.3元 |
| CosyVoice v3.5-flash | ~0.1元/次 | ~500次 | ~50元 |
| Tavily 搜索 | 免费 1000次 | ~300次 | 0元 |
| Whisper STT | 本地免费 | - | 0元 |
| **月均总计** | | | **~50元** |

> 注：CosyVoice 为主要开销。本地 CosyVoice2-0.5B 可替代但速度慢(RTF 2.5x)。

---

## 技术取舍

| 决策 | 方案A | 方案B | 最终 |
|------|------|------|------|
| LLM API | DeepSeek 官方 | Anthropic 代理 | DeepSeek 官方（快3倍） |
| TTS | 本地 CosyVoice2 | 阿里云 API | 阿里云（快10倍，但需付费） |
| 搜索 | DuckDuckGo | Tavily | Tavily（更快但有幻读） |
| 前端 | Electron | PyQt6 | PyQt6（纯Python，开发快） |
| 连接池 | ObjectPool(20) | 手动管理 | Fresh synth+信号量（防限流） |
| 状态机 | QThread Worker | pyqtSignal | pyqtSignal（跨线程可靠） |

---

## 素材来源

- **妮可语音**：58s 原神游戏内音频（个人提取）
- **动画素材**：Seedance1.5 生成 × 4组（170+122+122+122帧），免费额度
- **角色设定**：原神 3.3/4.0-4.2 剧情文本
