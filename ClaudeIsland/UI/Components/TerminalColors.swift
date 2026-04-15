//
//  TerminalColors.swift
//  ClaudeIsland
//
//  Color palette for terminal-style UI
//

import SwiftUI

struct TerminalColors {
    static let green = Color(red: 0.55, green: 0.85, blue: 0.65)    // 薄荷绿
    static let amber = Color(red: 1.0, green: 0.78, blue: 0.36)    // 蜜桃黄
    static let red = Color(red: 0.95, green: 0.5, blue: 0.5)       // 珊瑚粉
    static let cyan = Color(red: 0.45, green: 0.82, blue: 0.88)    // 天空蓝
    static let blue = Color(red: 0.55, green: 0.7, blue: 0.95)     // 薰衣草蓝
    static let magenta = Color(red: 0.82, green: 0.55, blue: 0.82) // 丁香紫
    static let dim = Color.white.opacity(0.35)
    static let dimmer = Color.white.opacity(0.2)
    static let prompt = Color(red: 0.9, green: 0.6, blue: 0.5)     // 蜜桃橙
    static let background = Color.white.opacity(0.05)
    static let backgroundHover = Color.white.opacity(0.1)
}
