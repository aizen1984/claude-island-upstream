//
//  GhosttyController.swift
//  ClaudeIsland
//
//  Precision tab-level focus for Ghostty via its AppleScript dictionary
//  (Ghostty.sdef bundled inside /Applications/Ghostty.app/Contents/Resources/).
//
//  This supersedes the old process-tree + bundleId-activation fallback
//  because Ghostty's sdef exposes:
//    - terminal.id            (stable UUID)
//    - terminal.name          (tab title, e.g. "⠂ Review cc-tdd skill quality")
//    - terminal.working directory
//    - focus <terminal>       (brings window to front AND selects the tab)
//
//  Using this native API path means:
//    - No Accessibility permission prompt (sdef is in-bundle scripting, not AXAPI)
//    - No yabai dependency
//    - No tmux process tree walking (tmux sessions still expose cwd via OSC 7)
//    - Precise tab selection, not just app-level activation
//
//  Failure modes (all non-fatal; caller should fall through to app-level
//  activation via `open -a Ghostty` as a safety net):
//    - Ghostty not running -> .notRunning
//    - sdef absent / old Ghostty build -> .scriptError
//    - No Ghostty terminal matches this session -> .noMatch
//

import AppKit
import Foundation

/// Controller for Ghostty terminal via its AppleScript dictionary.
enum GhosttyController {
    static let bundleId = "com.mitchellh.ghostty"

    /// A single Ghostty terminal surface, flattened across windows/tabs.
    struct TerminalInfo {
        let id: String          // Stable UUID from Ghostty sdef
        let cwd: String         // Working directory (updated via OSC 7)
        let name: String        // Tab title (updated via OSC 0/2)
    }

    // MARK: - Enumerate Cache
    //
    // enumerateTerminals() is dominated by a ~400ms AppleScript round trip
    // on typical hardware. For rapid successive focus calls (e.g. clicking
    // two completed ✅ icons back to back), the Ghostty terminal layout is
    // essentially static between clicks, so we cache the result for a short
    // TTL and skip the AppleScript round trip on cache hits.
    //
    // First click:  ~500ms (cache miss, full AppleScript enumerate)
    // Nth click within 1.5s: ~50ms (cache hit, only the focus call runs)
    //
    // All access to these vars is from MainActor-isolated callers.

    private static var cachedTerminals: [TerminalInfo] = []
    private static var cachedAt: Date = .distantPast
    private static let cacheTTL: TimeInterval = 1.5

    enum FocusResult {
        case focused(tabName: String)
        case noMatch
        case notRunning
        case scriptError(String)
    }

    /// Whether Ghostty is currently running (cheap check, no AppleScript).
    static var isRunning: Bool {
        !NSRunningApplication.runningApplications(withBundleIdentifier: bundleId).isEmpty
    }

    // MARK: - Enumeration

    /// Enumerate every Ghostty terminal surface across all windows and tabs.
    /// Output lines are `<uuid>\t<cwd>\t<name>` joined by linefeed.
    /// Returns an empty array if Ghostty is not running, sdef is missing,
    /// or any script-level error occurs.
    ///
    /// Results are cached for `cacheTTL` seconds. A cache hit returns in
    /// microseconds; a miss incurs the full ~400ms AppleScript round trip.
    static func enumerateTerminals() -> [TerminalInfo] {
        guard isRunning else {
            cachedTerminals = []
            return []
        }

        // Cache hit path — return without hitting AppleScript.
        if !cachedTerminals.isEmpty,
           Date().timeIntervalSince(cachedAt) < cacheTTL {
            return cachedTerminals
        }

        let source = """
        tell application "Ghostty"
            set TAB_CHAR to ASCII character 9
            set out to {}
            repeat with w in windows
                repeat with t in tabs of w
                    repeat with term in terminals of t
                        set end of out to ((id of term as text) & TAB_CHAR & (working directory of term as text) & TAB_CHAR & (name of term as text))
                    end repeat
                end repeat
            end repeat
            set AppleScript's text item delimiters to linefeed
            return out as text
        end tell
        """

        guard let raw = runAppleScriptForString(source), !raw.isEmpty else {
            return []
        }

        let fresh: [TerminalInfo] = raw
            .components(separatedBy: "\n")
            .compactMap { line -> TerminalInfo? in
                guard !line.isEmpty else { return nil }
                let parts = line.components(separatedBy: "\t")
                guard parts.count >= 3 else { return nil }
                // If title itself contains tabs, re-join everything after part[1]
                let id = parts[0]
                let cwd = parts[1]
                let name = parts[2...].joined(separator: "\t")
                return TerminalInfo(id: id, cwd: cwd, name: name)
            }

        cachedTerminals = fresh
        cachedAt = Date()
        return fresh
    }

    /// Explicitly invalidate the enumerate cache. Callers that know the
    /// terminal layout just changed (e.g. a tab was closed) can call this
    /// to force a fresh fetch on the next enumerate.
    static func invalidateEnumerateCache() {
        cachedTerminals = []
        cachedAt = .distantPast
    }

    // MARK: - Focusing

    /// Focus a specific terminal by its stable UUID.
    ///
    /// Ghostty's `focus` command only updates the internal `selectedTab`
    /// state — it does NOT bring the Ghostty app window to front when the
    /// caller is not frontmost. We therefore pair it with `activate` (a
    /// standard AppleScript verb handled by NSApplication automatically)
    /// so the user actually SEES the tab switch happen.
    @discardableResult
    static func focusTerminal(id: String) -> FocusResult {
        guard isRunning else { return .notRunning }

        let escaped = TerminalFocusUtilities.escapeForAppleScript(id)
        let source = """
        tell application "Ghostty"
            activate
            focus terminal id "\(escaped)"
        end tell
        """

        if let err = runAppleScriptForError(source) {
            return .scriptError(err)
        }
        return .focused(tabName: id)
    }

    /// Find and focus the best-matching Ghostty terminal for a given session.
    /// Scoring priorities (descending):
    ///   100 — cwd exact match AND name contains session title fragment
    ///    60 — name contains session title fragment (handles tmux cwd drift)
    ///    50 — cwd exact match only (weakest unambiguous signal)
    ///    10 — cwd is parent/child of session cwd (nested shells)
    ///     0 — no signal → skip
    static func focusSession(_ session: SessionState) -> FocusResult {
        guard isRunning else { return .notRunning }

        let terms = enumerateTerminals()
        guard !terms.isEmpty else { return .noMatch }

        let titleFragment = TerminalFocusUtilities.bestTitleFragment(for: session)

        var bestScore = 0
        var winner: TerminalInfo?

        for term in terms {
            let score = TerminalFocusUtilities.matchScore(
                terminalCwd: term.cwd,
                terminalName: term.name,
                sessionCwd: session.cwd,
                sessionTitle: titleFragment
            )
            if score > bestScore {
                bestScore = score
                winner = term
            }
        }

        guard let winner = winner else { return .noMatch }
        return focusTerminal(id: winner.id)
    }

    // MARK: - Private

    private static func runAppleScriptForString(_ source: String) -> String? {
        TerminalFocusUtilities.runAppleScriptForString(source)
    }

    private static func runAppleScriptForError(_ source: String) -> String? {
        TerminalFocusUtilities.runAppleScriptForError(source)
    }
}
