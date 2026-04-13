//
//  CmuxController.swift
//  ClaudeIsland
//
//  Precision tab/terminal-level focus for cmux via its AppleScript dictionary.
//
//  cmux is a Ghostty-based terminal with a near-identical sdef:
//    - windows → tabs → terminals
//    - terminal.id, terminal.name, terminal.working directory
//    - focus <terminal> (brings window to front AND selects the terminal)
//
//  Matching strategy: cwd + title prefix (same as GhosttyController).
//

import AppKit
import Foundation

enum CmuxController {
    static let bundleId = "com.cmuxterm.app"

    struct TerminalInfo {
        let id: String
        let cwd: String
        let name: String
    }

    enum FocusResult {
        case focused(tabName: String)
        case noMatch
        case notRunning
        case scriptError(String)
    }

    private static var cachedTerminals: [TerminalInfo] = []
    private static var cachedAt: Date = .distantPast
    private static let cacheTTL: TimeInterval = 1.5

    static var isRunning: Bool {
        !NSRunningApplication.runningApplications(withBundleIdentifier: bundleId).isEmpty
    }

    // MARK: - Enumeration

    static func enumerateTerminals() -> [TerminalInfo] {
        guard isRunning else {
            cachedTerminals = []
            return []
        }

        if !cachedTerminals.isEmpty,
           Date().timeIntervalSince(cachedAt) < cacheTTL {
            return cachedTerminals
        }

        let source = """
        tell application "cmux"
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

        guard let raw = TerminalFocusUtilities.runAppleScriptForString(source), !raw.isEmpty else {
            return []
        }

        let fresh: [TerminalInfo] = raw
            .components(separatedBy: "\n")
            .compactMap { line -> TerminalInfo? in
                guard !line.isEmpty else { return nil }
                let parts = line.components(separatedBy: "\t")
                guard parts.count >= 3 else { return nil }
                return TerminalInfo(id: parts[0], cwd: parts[1], name: parts[2...].joined(separator: "\t"))
            }

        cachedTerminals = fresh
        cachedAt = Date()
        return fresh
    }

    static func invalidateEnumerateCache() {
        cachedTerminals = []
        cachedAt = .distantPast
    }

    // MARK: - Focusing

    @discardableResult
    static func focusTerminal(id: String) -> FocusResult {
        guard isRunning else { return .notRunning }

        let escaped = TerminalFocusUtilities.escapeForAppleScript(id)
        let source = """
        tell application "cmux"
            activate
            focus terminal id "\(escaped)"
        end tell
        """

        if let err = TerminalFocusUtilities.runAppleScriptForError(source) {
            return .scriptError(err)
        }
        return .focused(tabName: id)
    }

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
}
