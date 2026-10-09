import AppKit
import AVKit
import AVFoundation

final class Introduccion: NSObject, NSApplicationDelegate, NSWindowDelegate {
    let url: URL
    var window: NSWindow!
    var player: AVPlayer!
    var observation: NSKeyValueObservation?
    var opened = false

    init(url: URL) { self.url = url }

    func applicationDidFinishLaunching(_ notification: Notification) {
        let screen = NSScreen.main?.visibleFrame.size ?? NSSize(width: 1280, height: 800)
        let width = min(1060, screen.width - 60)
        let height = min(width * 9 / 16, screen.height - 70)
        window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: width, height: height),
                          styleMask: [.titled, .closable, .miniaturizable, .resizable],
                          backing: .buffered, defer: false)
        window.title = "ConXml — Bienvenido"
        window.minSize = NSSize(width: min(640, width), height: min(430, height))
        window.isReleasedWhenClosed = false
        window.delegate = self
        window.backgroundColor = NSColor(calibratedRed: 0.96, green: 0.965, blue: 0.98, alpha: 1)
        let video = AVPlayerView()
        video.controlsStyle = .none
        video.videoGravity = .resizeAspect
        video.translatesAutoresizingMaskIntoConstraints = false
        let content = window.contentView!
        content.addSubview(video)

        window.appearance = NSAppearance(named: .aqua)
        let skip = NSButton(title: "Saltar", target: self, action: #selector(closeIntro))
        skip.bezelStyle = .rounded
        skip.font = NSFont.systemFont(ofSize: 15, weight: .semibold)
        skip.keyEquivalent = "\u{1b}"
        skip.translatesAutoresizingMaskIntoConstraints = false
        content.addSubview(skip, positioned: .above, relativeTo: video)
        NSLayoutConstraint.activate([
            video.leadingAnchor.constraint(equalTo: content.leadingAnchor),
            video.trailingAnchor.constraint(equalTo: content.trailingAnchor),
            video.topAnchor.constraint(equalTo: content.topAnchor),
            video.bottomAnchor.constraint(equalTo: content.bottomAnchor),
            skip.trailingAnchor.constraint(equalTo: content.trailingAnchor, constant: -22),
            skip.bottomAnchor.constraint(equalTo: content.bottomAnchor, constant: -20),
            skip.widthAnchor.constraint(equalToConstant: 100),
            skip.heightAnchor.constraint(equalToConstant: 36)])

        let item = AVPlayerItem(url: url)
        player = AVPlayer(playerItem: item)
        video.player = player
        observation = item.observe(\.status, options: [.initial, .new]) { [weak self] item, _ in
            DispatchQueue.main.async {
                guard let self = self else { return }
                if item.status == .readyToPlay {
                    self.opened = true
                    self.player.play()
                } else if item.status == .failed { self.fail() }
            }
        }
        NotificationCenter.default.addObserver(self, selector: #selector(ended),
            name: AVPlayerItem.didPlayToEndTimeNotification, object: item)
        NotificationCenter.default.addObserver(self, selector: #selector(fail),
            name: AVPlayerItem.failedToPlayToEndTimeNotification, object: item)
        // No dejar el inicio oculto si el sistema no logra abrir el video.
        DispatchQueue.main.asyncAfter(deadline: .now() + 15) { [weak self] in
            if let self = self, !self.opened { self.fail() }
        }
        window.center()
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
    }

    @objc func ended() { closeIntro() }
    @objc func closeIntro() {
        player.pause()
        NSApp.terminate(nil)
    }
    @objc func fail() {
        player?.pause()
        exit(2)
    }
    func windowWillClose(_ notification: Notification) { player.pause() }
    func applicationWillTerminate(_ notification: Notification) { player?.pause() }
    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }
}

guard CommandLine.arguments.count == 2 else { exit(2) }
let url = URL(fileURLWithPath: CommandLine.arguments[1])
guard FileManager.default.fileExists(atPath: url.path) else { exit(2) }
let delegate = Introduccion(url: url)
let app = NSApplication.shared
app.setActivationPolicy(.regular)
app.delegate = delegate
app.run()
