//
//  TerminalFocusUtilities.swift
//  ClaudeIsland
//
//  Shared utilities for terminal focus controllers (Ghostty, cmux, iTerm2, WezTerm).
//  Eliminates duplication of AppleScript execution, title matching, and tmux
//  client resolution across controllers.
//

import AppKit
import Foundation

enum TerminalFocusUtilities {

    // MARK: - AppleScript Safety

    /// Escape a string for safe interpolation into AppleScript string literals.
    /// Handles quotes, backslashes, and strips control characters (newlines,
    /// tabs) that could break out of a quoted string context.
    static func escapeForAppleScript(_ s: String) -> String {
        var result = ""
        result.reserveCapacity(s.count)
        for c in s {
            if c == "\"" {
                result += "\\\""
            } else if c == "\\" {
                result += "\\\\"
            } else if c.isNewline || (c.asciiValue ?? 32) < 32 {
                // Strip control characters — they could break the string literal.
                continue
            } else {
                result.append(c)
            }
        }
        return result
    }

    // MARK: - AppleScript Execution

    /// Run an AppleScript source and return its string result, or nil on error.
    static func runAppleScriptForString(_ source: String) -> String? {
        var errorDict: NSDictionary?
        guard let script = NSAppleScript(source: source) else { return nil }
        let descriptor = script.executeAndReturnError(&errorDict)
        if let errorDict = errorDict {
            NSLog("[TerminalFocus] AppleScript error: \(errorDict)")
            return nil
        }
        return descriptor.stringValue
    }

    /// Run an AppleScript source and return any error message, or nil on success.
    static func runAppleScriptForError(_ source: String) -> String? {
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

    // MARK: - Title Matching

    /// Normalize a title: strip leading non-alphanumeric decoration (spinners,
    /// emoji, `#`), then lowercase. Han characters are preserved.
    static func normalizeTitle(_ s: String) -> String {
        let chars = Array(s)
        var start = 0
        while start < chars.count {
            let c = chars[start]
            if c.isLetter || c.isNumber { break }
            start += 1
        }
        guard start < chars.count else { return "" }
        return String(chars[start...]).lowercased()
    }

    /// Longest common prefix length in characters (not bytes).
    static func commonPrefixLength(_ a: String, _ b: String) -> Int {
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

    /// Pick the most distinctive, stable text fragment from a session to
    /// match against terminal tab titles. Takes the first ~20 chars of
    /// the summary or first user message.
    static func bestTitleFragment(for session: SessionState) -> String {
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

    /// Score how well a terminal (cwd + name) matches a session.
    /// Returns 0 for no signal.
    ///   100+ — cwd match AND title prefix match (bonus by LCP length)
    ///    60+ — title prefix match only
    ///    50  — cwd exact match only
    ///    10  — cwd parent/child relationship
    static func matchScore(
        terminalCwd: String,
        terminalName: String,
        sessionCwd: String,
        sessionTitle: String
    ) -> Int {
        let normTermName = normalizeTitle(terminalName)
        let normSessionTitle = normalizeTitle(sessionTitle)
        let cwdMatch = terminalCwd == sessionCwd
        let lcp = commonPrefixLength(normSessionTitle, normTermName)
        let titleMatch = !normSessionTitle.isEmpty && lcp >= 3

        if cwdMatch && titleMatch { return 100 + lcp }
        if titleMatch { return 60 + lcp }
        if cwdMatch { return 50 }
        if terminalCwd.hasPrefix(sessionCwd + "/") || sessionCwd.hasPrefix(terminalCwd + "/") {
            return 10
        }
        return 0
    }

    // MARK: - Tmux Client Resolution

    /// Cached tmux path (process-lifetime, computed once).
    static let tmuxPath: String? = {
        ["/opt/homebrew/bin/tmux", "/usr/local/bin/tmux", "/usr/bin/tmux", "/bin/tmux"]
            .first { FileManager.default.isExecutableFile(atPath: $0) }
    }()

    /// Find the tmux client's TTY for a Claude process running inside tmux.
    /// Returns the `/dev/ttysXXX` path of the tmux client's terminal session.
    static func findTmuxClientTTY(claudePid: Int) -> String? {
        guard let tmux = tmuxPath else { return nil }
        let tree = ProcessTreeBuilder.shared.buildTree()

        guard let sessionName = findTmuxSessionName(claudePid: claudePid, tree: tree, tmuxPath: tmux) else {
            return nil
        }

        guard let clientsOutput = ProcessExecutor.shared.runSyncOrNil(tmux, arguments: [
            "list-clients", "-t", sessionName, "-F", "#{client_tty}"
        ]) else { return nil }

        return clientsOutput.components(separatedBy: "\n")
            .map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
            .first { !$0.isEmpty }
    }

    /// Find the terminal PID that hosts the tmux client viewing this session.
    static func findTmuxClientTerminalPid(claudePid: Int) -> Int? {
        guard let tmux = tmuxPath else { return nil }
        let tree = ProcessTreeBuilder.shared.buildTree()

        guard let sessionName = findTmuxSessionName(claudePid: claudePid, tree: tree, tmuxPath: tmux) else {
            return nil
        }

        guard let clientsOutput = ProcessExecutor.shared.runSyncOrNil(tmux, arguments: [
            "list-clients", "-t", sessionName, "-F", "#{client_pid}"
        ]) else { return nil }

        let clientPids = clientsOutput.components(separatedBy: "\n")
            .compactMap { Int($0.trimmingCharacters(in: .whitespaces)) }

        for clientPid in clientPids {
            if let termPid = ProcessTreeBuilder.shared.findTerminalPid(forProcess: clientPid, tree: tree) {
                return termPid
            }
        }

        return nil
    }

    /// Find which tmux session name contains this Claude process.
    private static func findTmuxSessionName(claudePid: Int, tree: [Int: ProcessInfo], tmuxPath: String) -> String? {
        guard let panesOutput = ProcessExecutor.shared.runSyncOrNil(tmuxPath, arguments: [
            "list-panes", "-a", "-F", "#{session_name}:#{window_index}.#{pane_index} #{pane_pid}"
        ]) else { return nil }

        for line in panesOutput.components(separatedBy: "\n") {
            let parts = line.split(separator: " ", maxSplits: 1)
            guard parts.count == 2, let panePid = Int(parts[1]) else { continue }
            if ProcessTreeBuilder.shared.isDescendant(targetPid: claudePid, ofAncestor: panePid, tree: tree) {
                return String(String(parts[0]).split(separator: ":")[0])
            }
        }

        return nil
    }
}
