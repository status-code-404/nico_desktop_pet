#!/bin/bash
# iOS 妮可 — 初始化开发环境
echo ">>> 切换 Xcode CLI..."
sudo xcode-select -s /Applications/Xcode.app/Contents/Developer
xcodebuild -version

echo ""
echo ">>> 准备完成！下一步："
echo "  1. 打开 Xcode，File → New → Project → iOS → App"
echo "  2. Product Name: Nicole"
echo "  3. 把所有 .swift 文件拖进项目"
echo "  4. 在 Build Settings 添加 xcconfig: xcconfig/debug.xcconfig"
echo "  5. Info.plist 加入 NSMicrophoneUsageDescription"
echo "  6. 选模拟器 iPhone 15 Pro, Cmd+R 运行"
echo ""
echo "或直接用命令行创建："
echo "  open Nicole.xcodeproj"
