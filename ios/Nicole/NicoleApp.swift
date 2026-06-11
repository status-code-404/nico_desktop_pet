import SwiftUI

@main
struct NicoleApp: App {
    @StateObject private var chatVM = ChatViewModel()

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(chatVM)
        }
    }
}
