# 妮可 iOS 版 (iOS 18+)

Siri 式悬浮桌面宠物。Widget + AppIntents 交互，不跳主界面。

## 结构

```
Nicole/
├── App/NicoleApp.swift         # 入口 + URL scheme
├── Overlay/
│   ├── OverlayView.swift        # Siri 式磨砂悬浮界面
│   └── OverlayViewModel.swift   # 录音/文字/LLM 状态
├── Core/ChatService.swift       # DeepSeek API
├── Intents/NicoleIntents.swift  # AppIntents (Widget 按钮/Siri)
├── Widget/NicoleWidget.swift    # 桌面小组件
└── Resources/                   # Lottie 动画等
```

## 运行

1. Xcode → New Project → iOS → App → Nicole
2. Add Widget Extension target → NicoleWidget
3. 拖入所有 .swift 文件
4. Info.plist 加 `DEEPSEEK_API_KEY`
5. Cmd+R

## URL Scheme

- `nicole://voice` — 打开语音 overlay
- `nicole://text` — 打开文字 overlay

## Widget

- 桌面小组件显示妮可头像 + 最后回复
- 🎤 按钮 → 打开 App 语音 overlay
- 💬 按钮 → 打开 App 文字 overlay
- iOS 17+ 支持 Button(intent:) 交互
