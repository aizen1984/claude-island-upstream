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
//  Focus strategy:
//    1. Detect which terminal hosts this session (process tree)
//    2. For tmux: switch to the correct pane first
//    3. Route to ONLY the detected terminal's controller (no cross-terminal false positives)
//    4. Fallback: if detection fails, try all controllers; last resort app-level activation
//

import AppKit
import Foundation
import os.log

@MainActor
enum SessionFocusService {
    private static let logger = Logger(subsystem: "com.claudeisland", category: "Focus")

    /// Known terminal bundle IDs, in preference order, used as a last-resort
    /// fallback when neither detection nor precision focus succeeds.
    static let knownTerminalBundleIds = [
        "com.mitchellh.ghostty",
        "com.cmuxterm.app",
        "com.googlecode.iterm2",
        "com.apple.Terminal",
        "net.kovidgoyal.kitty",
        "com.github.wez.wezterm",
        "io.alacritty"
    ]

    /// Focus the terminal window/tab/pane that owns the given session.
    ///
    /// Uses process tree detection to route to the EXACT terminal that hosts
    /// this session, avoiding false positives when multiple terminals are open.
    ///
    /// CRITICAL: `NSApp.deactivate()` releases Claude Island's frontmost
    /// status WITHOUT hiding the notch window (unlike NSApp.hide(nil)).
    /// Without this, `.activateIgnoringOtherApps` on the target terminal
    /// is a no-op on macOS 14+ due to tightened activation semantics.
    static func focus(_ session: SessionState) async {
        AcknowledgmentTracker.shared.acknowledge(session.sessionId)

        NSApp.deactivate()

        // Brief delay so WindowServer processes NSApp.deactivate before the
        // target app's activate() runs — otherwise macOS 14+ may downgrade
        // the activation to a dock-icon flash (see commit 5f1b444 / dc50cbc).
        try? await Task.sleep(nanoseconds: 10_000_000)

        // STEP 1: Detect which terminal hosts this session via process tree.
        // For non-tmux: Claude PID → ppid chain → terminal process → bundle ID.
        // For tmux: Claude PID → tmux session → list-clients → client PID → terminal.
        let hostBundle = detectHostTerminal(for: session)
        logger.info("detected host terminal: \(hostBundle ?? "unknown", privacy: .public)")

        // STEP 2: For tmux sessions, switch to the correct pane first.
        if session.isInTmux, let pid = session.pid {
            if let target = await TmuxController.shared.findTmuxTarget(forClaudePid: pid) {
                let switched = await TmuxController.shared.switchToPane(target: target)
                logger.info("tmux pane switch: target=\(target.targetString, privacy: .public) ok=\(switched)")
            }
        }

        // STEP 3: Precision focus — route to ONLY the detected terminal.
        if let bundle = hostBundle {
            if precisionFocus(session: session, bundleId: bundle) {
                logger.info("precision focused via \(bundle, privacy: .public)")
                return
            }
            // Precision controller failed — still activate the correct app.
            if let app = NSRunningApplication.runningApplications(withBundleIdentifier: bundle).first,
               app.activate(options: [.activateIgnoringOtherApps]) {
                logger.info("app-level activated detected host: \(bundle, privacy: .public)")
                return
            }
        }

        // STEP 4: Detection failed — try all controllers as fallback.
        // This handles edge cases like the process exiting before we could walk the tree.
        for attempt in [GhosttyController.bundleId, CmuxController.bundleId, ITerm2Controller.bundleId, WezTermController.bundleId] {
            if precisionFocus(session: session, bundleId: attempt) {
                logger.info("fallback precision focused via \(attempt, privacy: .public)")
                return
            }
        }

        // STEP 5: Last resort — app-level activation.
        for bundleId in knownTerminalBundleIds {
            if let app = NSRunningApplication.runningApplications(withBundleIdentifier: bundleId).first,
               app.activate(options: [.activateIgnoringOtherApps]) {
                logger.info("last-resort activated: \(bundleId, privacy: .public)")
                return
            }
        }

        logger.warning("no terminal found to focus")
    }

    // MARK: - Precision Focus Router

    /// Route to the correct terminal controller based on bundle ID.
    /// Returns true if the controller successfully focused the session.
    private static func precisionFocus(session: SessionState, bundleId: String) -> Bool {
        switch bundleId {
        case GhosttyController.bundleId:
            if case .focused = GhosttyController.focusSession(session) { return true }
        case CmuxController.bundleId:
            if case .focused = CmuxController.focusSession(session) { return true }
        case ITerm2Controller.bundleId:
            if case .focused = ITerm2Controller.focusSession(session) { return true }
        case WezTermController.bundleId:
            if case .focused = WezTermController.focusSession(session) { return true }
        default:
            break
        }
        return false
    }

    // MARK: - Terminal Detection

    /// Detect which terminal bundle ID hosts this session via the process tree.
    ///
    /// Non-tmux: walks up from Claude PID to find the terminal process, then
    /// resolves its bundle ID via NSWorkspace (no command-name guessing).
    ///
    /// Tmux: Claude's parent chain leads to tmux server (ppid=1), not the terminal.
    /// Instead we find the tmux client's terminal PID via shared utility.
    private static func detectHostTerminal(for session: SessionState) -> String? {
        guard let pid = session.pid else { return nil }

        let terminalPid: Int?

        if session.isInTmux {
            terminalPid = TerminalFocusUtilities.findTmuxClientTerminalPid(claudePid: pid)
        } else {
            let tree = ProcessTreeBuilder.shared.buildTree()
            terminalPid = ProcessTreeBuilder.shared.findTerminalPid(forProcess: pid, tree: tree)
        }

        guard let tPid = terminalPid else { return nil }

        return NSWorkspace.shared.runningApplications
            .first { $0.processIdentifier == pid_t(tPid) }?
            .bundleIdentifier
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
