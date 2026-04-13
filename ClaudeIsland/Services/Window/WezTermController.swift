//
//  WezTermController.swift
//  ClaudeIsland
//
//  Precision pane-level focus for WezTerm via its CLI.
//
//  WezTerm exposes a CLI over Unix socket:
//    - `wezterm cli list --format json` → pane list with tty, cwd, title
//    - `wezterm cli activate-pane --pane-id <id>` → focus a specific pane
//
//  Primary matching strategy: tty (1:1 match for non-tmux sessions).
//  For tmux sessions the caller resolves the tmux client TTY centrally
//  via TerminalFocusUtilities and passes it to focusByTTY().
//

import AppKit
import Foundation

enum WezTermController {
    static let bundleId = "com.github.wez.wezterm"

    enum FocusResult {
        case focused
        case noMatch
        case notRunning
        case cliNotFound
        case error(String)
    }

    struct PaneInfo {
        let paneId: Int
        let ttyName: String
    }

    static var isRunning: Bool {
        !NSRunningApplication.runningApplications(withBundleIdentifier: bundleId).isEmpty
    }

    // MARK: - CLI Path

    private static let cliPath: String? = {
        let candidates = [
            "/Applications/WezTerm.app/Contents/MacOS/wezterm",
            "/opt/homebrew/bin/wezterm",
            "/usr/local/bin/wezterm",
        ]
        if let found = candidates.first(where: { FileManager.default.isExecutableFile(atPath: $0) }) {
            return found
        }
        // Fallback: resolve via PATH
        if let output = ProcessExecutor.shared.runSyncOrNil("/usr/bin/which", arguments: ["wezterm"]),
           !output.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            return output.trimmingCharacters(in: .whitespacesAndNewlines)
        }
        return nil
    }()

    // MARK: - Enumerate Panes

    static func enumeratePanes() -> [PaneInfo] {
        guard isRunning, let cli = cliPath else { return [] }

        guard let output = ProcessExecutor.shared.runSyncOrNil(cli, arguments: [
            "cli", "list", "--format", "json"
        ]) else { return [] }

        guard let data = output.data(using: .utf8),
              let jsonArray = try? JSONSerialization.jsonObject(with: data) as? [[String: Any]] else {
            return []
        }

        return jsonArray.compactMap { obj -> PaneInfo? in
            guard let paneId = obj["pane_id"] as? Int,
                  let ttyName = obj["tty_name"] as? String else { return nil }
            return PaneInfo(paneId: paneId, ttyName: ttyName)
        }
    }

    // MARK: - Focus

    static func focusPane(paneId: Int) -> FocusResult {
        guard isRunning else { return .notRunning }
        guard let cli = cliPath else { return .cliNotFound }

        guard ProcessExecutor.shared.runSyncOrNil(cli, arguments: [
            "cli", "activate-pane", "--pane-id", String(paneId)
        ]) != nil else {
            return .error("activate-pane failed")
        }

        if let app = NSRunningApplication.runningApplications(withBundleIdentifier: bundleId).first {
            app.activate(options: [.activateIgnoringOtherApps])
        }

        return .focused
    }

    static func focusByTTY(_ tty: String) -> FocusResult {
        let panes = enumeratePanes()
        guard !panes.isEmpty else { return .noMatch }

        let normalizedTTY = tty.hasPrefix("/dev/") ? tty : "/dev/\(tty)"
        if let match = panes.first(where: { $0.ttyName == normalizedTTY }) {
            return focusPane(paneId: match.paneId)
        }
        return .noMatch
    }

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
