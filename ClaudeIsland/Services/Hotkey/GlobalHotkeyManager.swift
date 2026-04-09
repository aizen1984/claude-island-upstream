//
//  GlobalHotkeyManager.swift
//  ClaudeIsland
//
//  System-wide hotkey registration via the Carbon Hot Keys API, wrapped
//  by the soffes/HotKey Swift package.
//
//  Why HotKey (Carbon) and not NSEvent.addGlobalMonitorForEvents?
//    - Carbon RegisterEventHotKey CONSUMES the event: the focused app
//      (e.g. Ghostty) never sees Cmd+Shift+U, so the user doesn't get
//      a stray capital "U" typed into their terminal.
//    - No Accessibility permission prompt required.
//    - Works regardless of whether Claude Island is frontmost.
//
//  NSEvent.addGlobalMonitorForEvents would require Accessibility and
//  would not swallow the keypress — both are regressions for this UX.
//

import AppKit
import HotKey
import os.log

@MainActor
final class GlobalHotkeyManager {
    private static let logger = Logger(subsystem: "com.claudeisland", category: "Hotkey")

    /// Retained so Carbon keeps the hotkey registration alive.
    /// Releasing the `HotKey` instance auto-unregisters with Carbon.
    private var activateCompletedHotkey: HotKey?

    /// Register `Cmd+Shift+U` → activate the most recently completed session.
    /// Safe to call multiple times; re-registering replaces the handler.
    func registerActivateCompletedSession() {
        // Drop any previous registration first so Carbon doesn't hold
        // a stale handler if this is called twice during app lifetime.
        activateCompletedHotkey = nil

        let hotkey = HotKey(key: .u, modifiers: [.command, .shift])
        hotkey.keyDownHandler = {
            Self.logger.info("Hotkey fired: Cmd+Shift+U")
            Task { @MainActor in
                await SessionFocusService.activateMostRecentCompleted()
            }
        }
        activateCompletedHotkey = hotkey
        Self.logger.info("Hotkey registered: Cmd+Shift+U → activateMostRecentCompleted")
    }

    /// Release all hotkey registrations.
    func unregisterAll() {
        activateCompletedHotkey = nil
    }
}
