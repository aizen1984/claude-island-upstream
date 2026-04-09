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
    static func enumerateTerminals() -> [TerminalInfo] {
        guard isRunning else { return [] }

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

        return raw
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

        // Escape any stray quotes in the UUID string literal.
        let escaped = id.replacingOccurrences(of: "\"", with: "\\\"")
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

        // Normalize session title (summary/firstUserMessage) to a decoration-free form.
        // Claude Island's summary may prefix the title with "#", Ghostty's terminal
        // name is prefixed with a spinner char (✳/⠂/⠐) + space. After stripping both
        // we compare by longest common prefix (LCP): humans/LLMs naming the same task
        // tend to share front-loaded distinctive chars (e.g. "T0扣款成功率...").
        let normSessionTitle = normalizeTitle(bestTitleFragment(for: session))
        let targetCwd = session.cwd

        var bestScore = 0
        var winner: TerminalInfo?

        for term in terms {
            let normTermName = normalizeTitle(term.name)
            let cwdMatch = term.cwd == targetCwd
            let lcp = commonPrefixLength(normSessionTitle, normTermName)
            // Require >= 3 chars common prefix to count as a title signal.
            // 3 chars filters out accidental "T0..." collisions but is loose
            // enough to survive different tail wording ("T0扣款" → "T0扣款成功率").
            let titleMatch = !normSessionTitle.isEmpty && lcp >= 3

            var score = 0
            if cwdMatch && titleMatch {
                // Stronger signal when BOTH cwd and title agree. Bump by LCP
                // length so a 10-char prefix match outranks a 3-char one when
                // multiple terminals share the same cwd.
                score = 100 + lcp
            } else if titleMatch {
                score = 60 + lcp
            } else if cwdMatch {
                score = 50
            } else if term.cwd.hasPrefix(targetCwd + "/") || targetCwd.hasPrefix(term.cwd + "/") {
                score = 10
            }

            if score > bestScore {
                bestScore = score
                winner = term
            }
        }

        guard let winner = winner else { return .noMatch }
        return focusTerminal(id: winner.id)
    }

    /// Normalize a title string for matching: strip leading non-letter/digit
    /// decoration chars (spinner, #, ✳, emoji, whitespace), lowercase it.
    /// Han characters are preserved (Character.isLetter returns true for them).
    private static func normalizeTitle(_ s: String) -> String {
        let chars = Array(s)
        var start = 0
        while start < chars.count {
            let c = chars[start]
            if c.isLetter || c.isNumber { break }
            start += 1
        }
        return String(chars[start...]).lowercased()
    }

    /// Longest common prefix length (in characters, not bytes) of two strings.
    private static func commonPrefixLength(_ a: String, _ b: String) -> Int {
        var count = 0
        var ai = a.startIndex
        var bi = b.startIndex
        while ai < a.endIndex && bi < b.endIndex && a[ai] == b[bi] {
            count += 1
            ai = a.index(after: ai)
            bi = b.index(after: bi)
        }
        return count
    }

    // MARK: - Private

    /// Pick the most distinctive, stable text fragment from a SessionState
    /// to match against Ghostty tab titles. Ghostty tabs look like
    /// "⠂ Review cc-tdd skill quality" — a spinner char + space + Claude's
    /// session summary. We take the first ~20 chars of the summary because:
    ///   - Ghostty may truncate long titles with an ellipsis
    ///   - Summaries tend to be front-loaded with distinctive words
    private static func bestTitleFragment(for session: SessionState) -> String {
        let candidates: [String?] = [
            session.conversationInfo.summary,
            session.conversationInfo.firstUserMessage,
            session.displayTitle
        ]
        for candidate in candidates {
            if let s = candidate?.trimmingCharacters(in: .whitespacesAndNewlines),
               !s.isEmpty {
                return String(s.prefix(20))
            }
        }
        return ""
    }

    /// Run an AppleScript source and return its string result, or nil on error.
    /// Runs synchronously on the calling thread — NSAppleScript is not thread-safe
    /// so callers must invoke from the main thread. Typical execution time for
    /// enumerate-5-tabs on current hardware: ~400ms.
    private static func runAppleScriptForString(_ source: String) -> String? {
        var errorDict: NSDictionary?
        guard let script = NSAppleScript(source: source) else { return nil }
        let descriptor = script.executeAndReturnError(&errorDict)
        if let errorDict = errorDict {
            NSLog("[GhosttyController] enumerate error: \(errorDict)")
            return nil
        }
        return descriptor.stringValue
    }

    /// Run an AppleScript source and return any error message, or nil on success.
    private static func runAppleScriptForError(_ source: String) -> String? {
        var errorDict: NSDictionary?
        guard let script = NSAppleScript(source: source) else {
            return "failed to create NSAppleScript"
        }
        _ = script.executeAndReturnError(&errorDict)
        if let errorDict = errorDict {
            return "\(errorDict)"
        }
        return nil
    }
}
