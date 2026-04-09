//
//  SessionFocusService.swift
//  ClaudeIsland
//
//  Shared entry point for focusing a session's owning terminal window/tab.
//
//  Two call sites share this service so behavior stays identical:
//    1. Clicking the ✅ marker on a completed session in the notch UI
//       (ClaudeInstancesView.focusSession)
//    2. Pressing the global Cmd+Shift+U hotkey from anywhere
//       (GlobalHotkeyManager → activateMostRecentCompleted)
//

import AppKit
import Foundation
import os.log

@MainActor
enum SessionFocusService {
    private static let logger = Logger(subsystem: "com.claudeisland", category: "Focus")

    /// Known terminal bundle IDs, in preference order, used as a fallback
    /// when precise Ghostty tab focus isn't possible.
    static let knownTerminalBundleIds = [
        "com.mitchellh.ghostty",
        "com.googlecode.iterm2",
        "com.apple.Terminal",
        "net.kovidgoyal.kitty",
        "com.github.wez.wezterm",
        "io.alacritty"
    ]

    /// Focus the terminal window/tab that owns the given session.
    ///
    /// Primary path: Ghostty sdef AppleScript tab focus (precision).
    /// Fallback: app-level activation of the first running known terminal.
    ///
    /// CRITICAL: `NSApp.deactivate()` releases Claude Island's frontmost
    /// status WITHOUT hiding the notch window (unlike NSApp.hide(nil)).
    /// Without this, `.activateIgnoringOtherApps` on the target terminal
    /// is a no-op on macOS 14+ due to tightened activation semantics.
    static func focus(_ session: SessionState) async {
        // Acknowledge this session — hides its checkmark from the notch
        // and removes it from the Cmd+Shift+U cycle pool. The ack auto-
        // clears via AcknowledgmentTracker.reconcile when the session
        // leaves the attention states, so a future completion re-arms
        // the indicator.
        AcknowledgmentTracker.shared.acknowledge(session.sessionId)

        NSApp.deactivate()

        // Brief delay so WindowServer processes NSApp.deactivate before the
        // target app's activate() runs — otherwise macOS 14+ may downgrade
        // the activation to a dock-icon flash. 10ms is the smallest value
        // that reliably lets the deactivate message propagate on current
        // hardware (see commit 5f1b444 / dc50cbc).
        try? await Task.sleep(nanoseconds: 10_000_000)

        // PRIMARY: Ghostty AppleScript precision tab focus.
        if case .focused = GhosttyController.focusSession(session) {
            return
        }

        // FALLBACK: app-level activation of any running known terminal.
        for bundleId in knownTerminalBundleIds {
            if let app = NSRunningApplication.runningApplications(withBundleIdentifier: bundleId).first {
                if app.activate(options: [.activateIgnoringOtherApps]) { return }
            }
        }
    }

    /// Focus the next unacknowledged completed session.
    ///
    /// "Unacknowledged" = in .waitingForInput AND not in
    /// `AcknowledgmentTracker.dismissed`. Because `focus(_:)` acknowledges
    /// the target, each hotkey press naturally advances: press 1 visits
    /// the newest, press 2 visits the next newest, … until the cycle is
    /// drained and a beep signals "no more pending work".
    ///
    /// Sessions are sorted by `lastActivity` descending so newly completed
    /// work is always visited first, even if it arrives mid-cycle.
    ///
    /// `.waitingForApproval` is intentionally NOT included here — the user
    /// has a separate auto-approval flow for permission prompts.
    static func cycleToNextCompletedSession() async {
        let tracker = AcknowledgmentTracker.shared
        let candidates = SessionStore.shared.currentSessions
            .filter { state in
                if case .waitingForInput = state.phase { return true }
                return false
            }
            .filter { !tracker.isAcknowledged($0.sessionId) }
            .sorted { $0.lastActivity > $1.lastActivity }

        guard let target = candidates.first else {
            Self.logger.info("cycleToNextCompletedSession: no unacknowledged completed sessions, beeping")
            NSSound.beep()
            return
        }

        Self.logger.info("cycleToNextCompletedSession: target=\(target.sessionId, privacy: .public) remaining=\(candidates.count)")
        await focus(target)
    }
}
