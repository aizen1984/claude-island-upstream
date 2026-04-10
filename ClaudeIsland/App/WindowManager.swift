//
//  WindowManager.swift
//  ClaudeIsland
//
//  Manages the notch window lifecycle
//

import AppKit
import os.log

/// Logger for window management
private let logger = Logger(subsystem: "com.claudeisland", category: "Window")

class WindowManager {
    private(set) var windowControllers: [NotchWindowController] = []

    /// Convenience: the first (or only) window controller
    var windowController: NotchWindowController? {
        windowControllers.first
    }

    /// Set up or recreate notch windows for all target screens
    @discardableResult
    func setupNotchWindow() -> NotchWindowController? {
        let screenSelector = ScreenSelector.shared
        screenSelector.refreshScreens()

        let screens = screenSelector.targetScreens
        guard !screens.isEmpty else {
            logger.warning("No screens found")
            return nil
        }

        // Close all existing windows
        for controller in windowControllers {
            controller.window?.orderOut(nil)
            controller.window?.close()
        }
        windowControllers.removeAll()

        // Create one controller per target screen
        for screen in screens {
            let controller = NotchWindowController(screen: screen)
            controller.showWindow(nil)
            windowControllers.append(controller)
            logger.info("Created island on screen: \(screen.localizedName)")
        }

        return windowControllers.first
    }
}
