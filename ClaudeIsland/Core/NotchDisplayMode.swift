//
//  NotchDisplayMode.swift
//  ClaudeIsland
//
//  Toggle between the animated Ripple constellation (default) and a
//  zero-animation "HTML" view that renders sessions as static colored
//  characters. Persisted via `@AppStorage("notch.displayMode")`.
//

import Foundation

enum NotchDisplayMode: String, CaseIterable {
    case animated
    case staticText

    var label: String {
        switch self {
        case .animated:   return "Animated"
        case .staticText: return "Static"
        }
    }
}
