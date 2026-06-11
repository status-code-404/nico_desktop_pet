import SwiftUI

struct OverlayView: View {
    let mode: OverlayMode
    @StateObject private var vm = OverlayViewModel()
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        ZStack {
            // 磨砂玻璃背景 — 能看到桌面
            Color.black.opacity(0.3)
                .background(.ultraThinMaterial)
                .ignoresSafeArea()
                .onTapGesture { dismiss() }

            VStack(spacing: 24) {
                // 妮可头像区
                Circle()
                    .fill(LinearGradient(colors: [.purple, .blue], startPoint: .topLeading, endPoint: .bottomTrailing))
                    .frame(width: 80, height: 80)
                    .overlay(Text("N").font(.title).foregroundColor(.white))
                    .shadow(radius: 20)

                // 状态文字
                Text(vm.statusText)
                    .font(.title3)
                    .foregroundColor(.white)

                // 语音波形 / 文字输入
                if mode == .voice {
                    voiceWaveView
                } else {
                    textInputView
                }

                // 结果展示
                if !vm.replyText.isEmpty {
                    Text(vm.replyText)
                        .font(.body)
                        .foregroundColor(.white)
                        .padding()
                        .background(.ultraThinMaterial)
                        .cornerRadius(16)
                        .padding(.horizontal, 32)
                }

                // 松手提示
                if vm.isRecording {
                    Text("松手发送")
                        .font(.caption)
                        .foregroundColor(.white.opacity(0.6))
                }
            }
        }
        .onAppear {
            if mode == .voice { vm.startRecording() }
        }
        .onDisappear { vm.cleanup() }
    }

    // 语音波形
    private var voiceWaveView: some View {
        HStack(spacing: 3) {
            ForEach(0..<20, id: \.self) { i in
                RoundedRectangle(cornerRadius: 2)
                    .fill(vm.isRecording ? Color.white : Color.white.opacity(0.4))
                    .frame(width: 3, height: vm.isRecording ? CGFloat.random(in: 10...40) : 10)
                    .animation(vm.isRecording ? .easeInOut(duration: 0.3).repeatForever() : .default, value: vm.isRecording)
            }
        }
        .frame(height: 40)
    }

    // 文字输入
    private var textInputView: some View {
        HStack {
            TextField("跟妮可说话...", text: $vm.inputText)
                .textFieldStyle(.plain)
                .padding()
                .background(.ultraThinMaterial)
                .cornerRadius(12)
                .foregroundColor(.white)

            Button(action: { vm.sendText() }) {
                Image(systemName: "arrow.up.circle.fill")
                    .font(.title)
                    .foregroundColor(.white)
            }
        }
        .padding(.horizontal, 32)
    }
}
