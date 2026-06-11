// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "Nicole",
    platforms: [.iOS(.v17)],
    dependencies: [
        .package(url: "https://github.com/airbnb/lottie-ios.git", from: "4.5.0"),
    ],
    targets: [
        .executableTarget(
            name: "Nicole",
            path: "Nicole",
            resources: [.process("Resources")],
            linkerSettings: [
                .unsafeFlags(["-Xlinker", "-no_application_extension"])
            ]
        ),
    ]
)
