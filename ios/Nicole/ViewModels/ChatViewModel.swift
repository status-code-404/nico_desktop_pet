import Foundation
import SwiftUI

@MainActor
class ChatViewModel: ObservableObject {
    @Published var messages: [ChatMessage] = []
    @Published var currentReply = ""
    @Published var isThinking = false
    @Published var errorMessage: String?

    private let service = ChatService.shared

    func send(_ text: String) {
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty, !isThinking else { return }

        let userMsg = ChatMessage(role: .user, content: trimmed)
        messages.append(userMsg)
        isThinking = true
        errorMessage = nil

        Task {
            do {
                let reply = try await service.send(trimmed)
                let assistantMsg = ChatMessage(role: .assistant, content: reply)
                messages.append(assistantMsg)
            } catch {
                errorMessage = error.localizedDescription
            }
            isThinking = false
        }
    }

    func clearChat() {
        messages.removeAll()
        Task { await service.clearHistory() }
    }
}
