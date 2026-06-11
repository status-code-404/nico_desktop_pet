import Foundation

actor ChatService {
    static let shared = ChatService()
    private let session = URLSession.shared
    private var history: [(role: String, content: String)] = []
    private let maxHistory = 10

    private let systemPrompt = """
    你是妮可（Nicole／N），提瓦特大陆的天使，魔女会成员代号N。
    心灵感应者，世界线观测者。当前2026年，原神6.7版本。
    回复2-3句话，简洁优雅，称呼用户为"主人"。
    """

    struct Config {
        var deepseekKey: String { Bundle.main.object(forInfoDictionaryKey: "DEEPSEEK_API_KEY") as? String ?? "" }
        var dashscopeKey: String { Bundle.main.object(forInfoDictionaryKey: "DASHSCOPE_API_KEY") as? String ?? "" }
        var tavilyKey: String { Bundle.main.object(forInfoDictionaryKey: "TAVILY_API_KEY") as? String ?? "" }
    }
    private let config = Config()

    func send(_ content: String) async throws -> String {
        history.append((role: "user", content: content))
        let reply = try await callLLM(content)
        history.append((role: "assistant", content: reply))
        if history.count > maxHistory * 2 { history.removeFirst(2) }
        return reply
    }

    private func callLLM(_ message: String) async throws -> String {
        var messages: [[String: String]] = [["role": "system", "content": systemPrompt]]
        for m in history.suffix(maxHistory) {
            messages.append(["role": m.role, "content": m.content])
        }
        messages.append(["role": "user", "content": message])

        var req = URLRequest(url: URL(string: "https://api.deepseek.com/v1/chat/completions")!)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.setValue("Bearer \(config.deepseekKey)", forHTTPHeaderField: "Authorization")
        req.timeoutInterval = 30

        let body: [String: Any] = [
            "model": "deepseek-chat",
            "messages": messages,
            "max_tokens": 512,
            "temperature": 0.8,
        ]
        req.httpBody = try JSONSerialization.data(withJSONObject: body)
        let (data, _) = try await session.data(for: req)
        let json = try JSONSerialization.jsonObject(with: data) as? [String: Any]
        let choices = json?["choices"] as? [[String: Any]]
        let msg = choices?.first?["message"] as? [String: Any]
        return msg?["content"] as? String ?? "唔…信号有点干扰。"
    }

    func clearHistory() { history.removeAll() }
}
