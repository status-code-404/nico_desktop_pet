import Foundation
import SwiftUI
import AVFoundation

@MainActor
class OverlayViewModel: ObservableObject {
    @Published var statusText = "我在听..."
    @Published var inputText = ""
    @Published var replyText = ""
    @Published var isRecording = false

    private let chatService = ChatService()
    private var audioRecorder: AVAudioRecorder?
    private var recordingURL: URL?

    func startRecording() {
        isRecording = true
        statusText = "我在听..."

        let session = AVAudioSession.sharedInstance()
        try? session.setCategory(.playAndRecord, mode: .default)
        try? session.setActive(true)

        recordingURL = FileManager.default.temporaryDirectory.appendingPathComponent("nicole_input.wav")

        let settings: [String: Any] = [
            AVFormatIDKey: Int(kAudioFormatLinearPCM),
            AVSampleRateKey: 16000,
            AVNumberOfChannelsKey: 1,
            AVLinearPCMBitDepthKey: 16,
        ]

        audioRecorder = try? AVAudioRecorder(url: recordingURL!, settings: settings)
        audioRecorder?.record()
    }

    func stopRecording() {
        isRecording = false
        audioRecorder?.stop()
        guard let url = recordingURL, FileManager.default.fileExists(atPath: url.path) else { return }

        statusText = "妮可思考中..."

        // TODO: transcribe locally → LLM → TTS on device
        // For now: send text "hello" to LLM directly as demo
        Task {
            await processWithLLM("主人对妮可说话了")
        }
    }

    func sendText() {
        guard !inputText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else { return }
        let text = inputText
        inputText = ""
        statusText = "妮可思考中..."
        Task { await processWithLLM(text) }
    }

    private func processWithLLM(_ text: String) async {
        do {
            let reply = try await chatService.send(text)
            replyText = reply
            statusText = ""
            try? await Task.sleep(nanoseconds: 3_000_000_000)
            replyText = ""
        } catch {
            replyText = "唔…信号有点干扰: \(error.localizedDescription)"
        }
    }

    func cleanup() {
        audioRecorder?.stop()
        isRecording = false
    }
}
