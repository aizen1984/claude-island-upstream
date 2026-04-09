//
//  AcknowledgmentTracker.swift
//  ClaudeIsland
//
//  Tracks which attention-needing Claude sessions the user has explicitly
//  acknowledged by focusing their terminal — either via the Cmd+Shift+U
//  global hotkey or by clicking the ✅ in the expanded notch list.
//
//  Acknowledged sessions are:
//    1. Hidden from the compact notch checkmark indicator
//    2. Skipped by the Cmd+Shift+U cycle (so each press visits a NEW one)
//
//  Acknowledgment auto-clears when the session leaves the attention states
//  (e.g., the user sent a new prompt and the session went back to
//  .processing). The next time it re-enters .waitingForInput a fresh
//  checkmark is shown — acknowledgment is per "completion event", not
//  permanent.
//

import Combine
import Foundation

@MainActor
final class AcknowledgmentTracker: ObservableObject {
    static let shared = AcknowledgmentTracker()

    /// Session IDs the user has explicitly acknowledged.
    @Published private(set) var dismissed: Set<String> = []

    private init() {}

    /// Mark a session as acknowledged — hides its checkmark from the notch
    /// and removes it from the Cmd+Shift+U cycle.
    func acknowledge(_ sessionId: String) {
        dismissed.insert(sessionId)
    }

    /// Check if a session is currently acknowledged.
    func isAcknowledged(_ sessionId: String) -> Bool {
        dismissed.contains(sessionId)
    }

    /// Drop acknowledgment entries whose sessions no longer need attention.
    /// Called from NotchView as sessions change — if a dismissed session
    /// has left the attention set (.waitingForInput / .waitingForApproval),
    /// its ack is stale and should be cleared so a FUTURE completion on the
    /// same session shows a new checkmark.
    ///
    /// - Parameter keeping: sessionIds currently in any attention state.
    func reconcile(keeping currentIds: Set<String>) {
        let next = dismissed.intersection(currentIds)
        if next != dismissed {
            dismissed = next
        }
    }
}
