//
//  StatusTextPresets.swift
//  ClaudeIsland
//
//  User-selectable status text presets shown on the left side of the closed
//  notch while at least one Claude session is active. The preset is persisted
//  via `@AppStorage("status.text.preset")` — an empty string means "random"
//  (delegates to `StatusPhrases.smartWorking`).
//
//  Moved out of the (now-deleted) InProgressIndicators.swift as part of the
//  Session Constellation refactor. That file previously held both the status
//  preset list AND the 9 swappable indicator animations; the latter are gone,
//  the former stays exactly as-is.
//

import Foundation

enum StatusTextPresets {
    /// Empty-string entry means "random". Keep it at index 0.
    static let all: [String] = [
        "",            // random
        "搬砖中",
        "牛马中",
        "打工中",
        "肝中",
        "冲冲冲",
        "在卷了",
        "写bug",
        "debug",
        "coding",
        "赋能中",
        "迭代中",
        "闭环中",
        "对齐中",
        "沉淀中",
        "还活着",
        "白干了",
        "躺平了",
        "摸鱼中",
        "续命中",
    ]

    /// Label shown in the menu value column for a given preset.
    static func label(for preset: String) -> String {
        preset.isEmpty ? "随机" : preset
    }

    /// Cycle to the next preset (wraps around).
    static func next(after current: String) -> String {
        guard let idx = all.firstIndex(of: current) else { return all[0] }
        return all[(idx + 1) % all.count]
    }
}
