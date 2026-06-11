import Foundation

/// Load from Info.plist or hardcode for debug.
enum APIConfig {
    static let deepseekKey = Bundle.main.object(forInfoDictionaryKey: "DEEPSEEK_API_KEY") as? String ?? ""
    static let dashscopeKey = Bundle.main.object(forInfoDictionaryKey: "DASHSCOPE_API_KEY") as? String ?? ""
    static let tavilyKey = Bundle.main.object(forInfoDictionaryKey: "TAVILY_API_KEY") as? String ?? ""

    static let deepseekURL = "https://api.deepseek.com/v1/chat/completions"
    static let cosyvoiceURL = "https://dashscope.aliyuncs.com/api-ws/v1/inference"

    // Nicole voiceId — update to your cloned voice
    static let nicoleVoiceId = Bundle.main.object(forInfoDictionaryKey: "NICOLE_VOICE_ID") as? String ?? ""
    static let cosyvoiceModel = "cosyvoice-v3.5-flash"
}
