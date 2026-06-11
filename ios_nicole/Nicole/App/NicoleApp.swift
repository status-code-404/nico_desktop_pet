import SwiftUI

@main
struct NicoleApp: App {
    @State private var showOverlay = false
    @State private var overlayMode: OverlayMode = .voice

    var body: some Scene {
        WindowGroup {
            // 主界面：完全透明，只在打开时弹出 Siri 式 overlay
            Color.clear
                .ignoresSafeArea()
                .onOpenURL { url in
                    if url.host == "voice" {
                        overlayMode = .voice
                        showOverlay = true
                    } else if url.host == "text" {
                        overlayMode = .text
                        showOverlay = true
                    }
                }
                .sheet(isPresented: $showOverlay) {
                    OverlayView(mode: overlayMode)
                }
        }
    }
}

enum OverlayMode { case voice, text }
