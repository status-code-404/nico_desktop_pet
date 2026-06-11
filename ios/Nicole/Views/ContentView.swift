import SwiftUI

struct ContentView: View {
    @EnvironmentObject var chatVM: ChatViewModel
    @State private var inputText = ""
    @FocusState private var focused: Bool

    var body: some View {
        VStack(spacing: 0) {
            // Header
            headerView

            // Chat messages
            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(spacing: 12) {
                        ForEach(chatVM.messages) { msg in
                            MessageBubble(msg: msg)
                        }
                        if chatVM.isThinking {
                            HStack { Spacer(); ThinkingDots(); Spacer() }
                                .id("thinking")
                        }
                    }
                    .padding()
                }
                .onChange(of: chatVM.messages.count) { _, _ in
                    withAnimation { proxy.scrollTo(chatVM.messages.last?.id ?? "thinking", anchor: .bottom) }
                }
                .onChange(of: chatVM.isThinking) { _, _ in
                    withAnimation { proxy.scrollTo("thinking", anchor: .bottom) }
                }
            }
            .background(Color(.systemGroupedBackground))

            // Error banner
            if let err = chatVM.errorMessage {
                Text("❌ \(err)")
                    .font(.caption).foregroundColor(.red)
                    .padding(.horizontal)
            }

            // Input bar
            inputBar
        }
    }

    private var headerView: some View {
        HStack {
            Image(systemName: "sparkles")
                .foregroundColor(.purple)
            Text("妮可 Nicole")
                .font(.headline)
            Spacer()
            Button(action: { chatVM.clearChat() }) {
                Image(systemName: "trash")
            }
            Text("API: \(chatVM.isThinking ? "thinking" : "ready")")
                .font(.caption2).foregroundColor(.secondary)
        }
        .padding(.horizontal)
        .padding(.vertical, 8)
        .background(.thinMaterial)
    }

    private var inputBar: some View {
        HStack(spacing: 8) {
            TextField("跟妮可说话...", text: $inputText)
                .textFieldStyle(.roundedBorder)
                .focused($focused)
                .disabled(chatVM.isThinking)
                .onSubmit { send() }

            Button(action: { send() }) {
                Image(systemName: "arrow.up.circle.fill")
                    .font(.title2)
            }
            .disabled(inputText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || chatVM.isThinking)
        }
        .padding()
        .background(.thinMaterial)
    }

    private func send() {
        chatVM.send(inputText)
        inputText = ""
    }
}

// ── Subviews ──────────────────────────────────────────────

struct MessageBubble: View {
    let msg: ChatMessage
    var body: some View {
        HStack {
            if msg.role == .user { Spacer() }
            Text(msg.content)
                .padding(12)
                .background(msg.role == .user ? Color.blue.opacity(0.8) : Color(.systemGray5))
                .foregroundColor(msg.role == .user ? .white : .primary)
                .cornerRadius(16)
                .contextMenu { Button("复制") { UIPasteboard.general.string = msg.content } }
            if msg.role == .assistant { Spacer() }
        }
    }
}

struct ThinkingDots: View {
    @State private var opacity = 0.3
    var body: some View {
        Text("妮可思考中...")
            .font(.caption).foregroundColor(.secondary)
            .padding(8)
            .background(Color(.systemGray5))
            .cornerRadius(12)
            .opacity(opacity)
            .onAppear {
                withAnimation(.easeInOut(duration: 0.8).repeatForever()) { opacity = 1.0 }
            }
    }
}
