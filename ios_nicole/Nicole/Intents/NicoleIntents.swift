import AppIntents
import WidgetKit

// MARK: - Voice Intent (点 🎤 触发)

struct VoiceIntent: AppIntent {
    static var title: LocalizedStringResource = "语音问妮可"

    func perform() async throws -> some IntentResult {
        // 打开 App 的语音 overlay
        if let url = URL(string: "nicole://voice") {
            await UIApplication.shared.open(url)
        }
        return .result()
    }
}

// MARK: - Text Intent (点 💬 触发)

struct TextIntent: AppIntent {
    static var title: LocalizedStringResource = "打字问妮可"

    func perform() async throws -> some IntentResult {
        if let url = URL(string: "nicole://text") {
            await UIApplication.shared.open(url)
        }
        return .result()
    }
}

// MARK: - Quick Ask Intent (Siri / Shortcuts)

struct QuickAskIntent: AppIntent {
    static var title: LocalizedStringResource = "问妮可"

    @Parameter(title: "问题")
    var question: String

    func perform() async throws -> some IntentResult & ReturnsValue<String> {
        let reply = try await ChatService.shared.send(question)
        // Refresh widget after reply
        WidgetCenter.shared.reloadTimelines(ofKind: "NicoleWidget")
        return .result(value: reply)
    }
}
