# 妮可 iOS 版 — 开发调试指南

## 环境要求
- macOS 14+ / Xcode 16+
- Swift 6.0
- iOS 17.0+ 模拟器或真机

## 3 步跑起来

### 1. 切换 Xcode
```bash
sudo xcode-select -s /Applications/Xcode.app/Contents/Developer
```

### 2. 创建项目
打开 Xcode → File → New → Project → iOS → App：
- Product Name: `Nicole`
- Interface: SwiftUI
- Language: Swift
- 保存到 `ios/` 目录

### 3. 导入代码
1. 删掉 Xcode 自动生成的 `ContentView.swift` 和 `NicoleApp.swift`
2. 把整个 `Nicole/` 文件夹拖进 Xcode 项目导航栏
3. 在 Build Settings → Info.plist File 指向 `Info.plist`
4. 在 Configurations 导入 `xcconfig/debug.xcconfig`
5. 填入 API Key 到 xcconfig 文件

## 运行
选模拟器 iPhone 15 Pro → Cmd+R

## 调试页说明

打开后看到聊天界面：
- 底部输入框：打字发消息给妮可
- 右上角垃圾桶：清空对话
- 错误提示用红色文字显示
- 思考中显示"妮可思考中..."动画

## 文件说明

| 文件 | 作用 |
|------|------|
| `NicoleApp.swift` | App 入口 |
| `Views/ContentView.swift` | 聊天 UI + 调试界面 |
| `ViewModels/ChatViewModel.swift` | 状态管理 |
| `Services/ChatService.swift` | DeepSeek API 调用 |
| `Models/ChatMessage.swift` | 数据模型 |
| `Models/APIConfig.swift` | API 配置 |
| `Info.plist` | 应用配置 |
| `xcconfig/debug.xcconfig` | API Key（gitigored） |
