import WidgetKit
import SwiftUI
import AppIntents

// MARK: - Timeline Entry

struct NicoleEntry: TimelineEntry {
    let date: Date
    let replyText: String
    let isThinking: Bool
}

// MARK: - Provider

struct NicoleProvider: TimelineProvider {
    func placeholder(in context: Context) -> NicoleEntry {
        NicoleEntry(date: Date(), replyText: "主人，今天想聊什么？", isThinking: false)
    }

    func getSnapshot(in context: Context, completion: @escaping (NicoleEntry) -> Void) {
        completion(NicoleEntry(date: Date(), replyText: "主人，我在呢。", isThinking: false))
    }

    func getTimeline(in context: Context, completion: @escaping (Timeline<NicoleEntry>) -> Void) {
        let entry = NicoleEntry(date: Date(), replyText: lastReply ?? "", isThinking: false)
        let timeline = Timeline(entries: [entry], policy: .never)
        completion(timeline)
    }
}

// 共享状态：Widget 和 App 通过 UserDefaults 通信
private var lastReply: String? {
    UserDefaults(suiteName: "group.nicole")?.string(forKey: "lastReply")
}

// MARK: - Widget View

struct NicoleWidgetEntryView: View {
    var entry: NicoleEntry

    var body: some View {
        VStack(spacing: 8) {
            // 妮可小头像
            Circle()
                .fill(LinearGradient(colors: [.purple, .blue], startPoint: .top, endPoint: .bottom))
                .frame(width: 36, height: 36)
                .overlay(Text("N").font(.caption).foregroundColor(.white))

            // 最后回复
            if !entry.replyText.isEmpty {
                Text(entry.replyText)
                    .font(.caption2)
                    .lineLimit(2)
                    .multilineTextAlignment(.center)
            }

            // 按钮
            HStack(spacing: 12) {
                Button(intent: VoiceIntent()) {
                    Label("🎤", systemImage: "mic.fill")
                        .font(.caption)
                }
                .tint(.purple)

                Button(intent: TextIntent()) {
                    Label("💬", systemImage: "message.fill")
                        .font(.caption)
                }
                .tint(.blue)
            }
            .buttonStyle(.bordered)
        }
        .padding(8)
    }
}

// MARK: - Widget Definition

struct NicoleWidget: Widget {
    let kind = "NicoleWidget"

    var body: some WidgetConfiguration {
        StaticConfiguration(kind: kind, provider: NicoleProvider()) { entry in
            NicoleWidgetEntryView(entry: entry)
        }
        .configurationDisplayName("妮可")
        .description("随时和妮可对话")
        .supportedFamilies([.systemSmall, .systemMedium])
    }
}
