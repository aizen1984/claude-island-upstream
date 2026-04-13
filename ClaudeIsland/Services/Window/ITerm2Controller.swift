//
//  ITerm2Controller.swift
//  ClaudeIsland
//
//  Precision tab/session-level focus for iTerm2 via AppleScript.
//
//  Primary matching strategy: tty (1:1 match for non-tmux sessions).
//  For tmux sessions the caller resolves the tmux client TTY centrally
//  via TerminalFocusUtilities and passes it to focusByTTY().
//

import AppKit
import Foundation

enum ITerm2Controller {
    static let bundleId = "com.googlecode.iterm2"

    enum FocusResult {
        case focused
        case noMatch
        case notRunning
        case scriptError(String)
    }

    static var isRunning: Bool {
        !NSRunningApplication.runningApplications(withBundleIdentifier: bundleId).isEmpty
    }

    // MARK: - Focus by TTY

    /// Focus the iTerm2 session whose tty matches the given path.
    /// The tty should include the `/dev/` prefix (e.g. "/dev/ttys006").
    static func focusByTTY(_ tty: String) -> FocusResult {
        guard isRunning else { return .notRunning }

        let escaped = TerminalFocusUtilities.escapeForAppleScript(tty)
        let source = """
        tell application "iTerm2"
            activate
            repeat with w in windows
                repeat with t in tabs of w
                    repeat with s in sessions of t
                        if tty of s is "\(escaped)" then
                            select t
                            select s
                            return "ok"
                        end if
                    end repeat
                end repeat
            end repeat
            return "no_match"
        end tell
        """

        guard let result = TerminalFocusUtilities.runAppleScriptForString(source) else {
            return .scriptError("AppleScript execution failed")
        }
        return result.contains("ok") ? .focused : .noMatch
    }

    // MARK: - Focus Session

    /// Focus the iTerm2 tab/session that owns the given Claude session.
    ///
    /// Non-tmux: match by `session.tty` directly.
    /// Tmux: resolve tmux client TTY via shared utility, then match.
    static func focusSession(_ session: SessionState) -> FocusResult {
        guard isRunning else { return .notRunning }

        let tty: String
        if session.isInTmux {
            guard let pid = session.pid,
                  let clientTTY = TerminalFocusUtilities.findTmuxClientTTY(claudePid: pid) else {
                return .noMatch
            }
            tty = clientTTY
        } else {
            guard let sessionTTY = session.tty else { return .noMatch }
            tty = sessionTTY.hasPrefix("/dev/") ? sessionTTY : "/dev/\(sessionTTY)"
        }

        return focusByTTY(tty)
    }
}
