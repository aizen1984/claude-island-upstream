//
//  AnimationPauseController.swift
//  ClaudeIsland
//
//  Stops Core Animation churn when the display/system is asleep or the
//  screen is locked. `repeatForever` animations are tied to CALayers —
//  the only way to truly pause them is to drop the view from the tree.
//  Consumers should gate their ripple / strip / animated-text subtrees
//  on `isPaused`, not just switch content.
//
//  Notification sources:
//    NSWorkspace.notificationCenter — display/system sleep + wake
//    DistributedNotificationCenter  — screen lock + screensaver (Apple
//                                     does not ship these on NSWorkspace)
//

import AppKit
import Combine
import Foundation

@MainActor
final class AnimationPauseController: ObservableObject {
    static let shared = AnimationPauseController()

    @Published private(set) var isPaused: Bool = false

    private var wsObservers: [NSObjectProtocol] = []
    private var dnObservers: [NSObjectProtocol] = []

    private init() {
        let wc = NSWorkspace.shared.notificationCenter

        let wsPause: [Notification.Name] = [
            NSWorkspace.screensDidSleepNotification,
            NSWorkspace.willSleepNotification
        ]
        let wsResume: [Notification.Name] = [
            NSWorkspace.screensDidWakeNotification,
            NSWorkspace.didWakeNotification
        ]

        for name in wsPause {
            let token = wc.addObserver(forName: name, object: nil, queue: .main) { [weak self] _ in
                MainActor.assumeIsolated { self?.setPaused(true) }
            }
            wsObservers.append(token)
        }
        for name in wsResume {
            let token = wc.addObserver(forName: name, object: nil, queue: .main) { [weak self] _ in
                MainActor.assumeIsolated { self?.setPaused(false) }
            }
            wsObservers.append(token)
        }

        // Screen lock + screensaver come over DistributedNotificationCenter.
        // Names are stable since 10.6.
        let dnc = DistributedNotificationCenter.default()
        let dnPause = ["com.apple.screensaver.didstart", "com.apple.screenIsLocked"]
        let dnResume = ["com.apple.screensaver.didstop", "com.apple.screenIsUnlocked"]

        for name in dnPause {
            let token = dnc.addObserver(forName: Notification.Name(name), object: nil, queue: .main) { [weak self] _ in
                MainActor.assumeIsolated { self?.setPaused(true) }
            }
            dnObservers.append(token)
        }
        for name in dnResume {
            let token = dnc.addObserver(forName: Notification.Name(name), object: nil, queue: .main) { [weak self] _ in
                MainActor.assumeIsolated { self?.setPaused(false) }
            }
            dnObservers.append(token)
        }
    }

    deinit {
        let wc = NSWorkspace.shared.notificationCenter
        for t in wsObservers { wc.removeObserver(t) }
        let dnc = DistributedNotificationCenter.default()
        for t in dnObservers { dnc.removeObserver(t) }
    }

    private func setPaused(_ paused: Bool) {
        guard isPaused != paused else { return }
        isPaused = paused
    }
}
