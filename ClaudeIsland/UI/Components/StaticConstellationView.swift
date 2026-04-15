//
//  StaticConstellationView.swift
//  ClaudeIsland
//
//  Non-animated counterpart to SessionConstellationView. Renders each
//  session as a single colored monospace character — zero
//  repeatForever, zero TimelineView, zero .task loops. Categorization
//  logic mirrors SessionConstellationView (attention > compacting >
//  running > idle, max 4 visible + "+N" overflow).
//

import SwiftUI

struct StaticConstellationView: View {
    let sessions: [SessionState]
    let unacknowledgedAttentionIds: Set<String>

    // MARK: - Layout constants
    //
    // NotchView.constellationSlotWidth() branches on displayMode and
    // references these. Keep both in sync.

    static let charWidth: CGFloat = 10   // measured for bold monospaced 13pt ✓/●/◉/·
    static let spacing: CGFloat = 3
    static let maxVisible: Int = 4

    // MARK: - Categorization (mirrors SessionConstellationView)

    private var attentionSessions: [SessionState] {
        sessions.filter {
            $0.needsAttention && unacknowledgedAttentionIds.contains($0.sessionId)
        }
    }

    private var compactingSessions: [SessionState] {
        sessions.filter { $0.phase == .compacting }
    }

    private var runningSessions: [SessionState] {
        sessions.filter { $0.phase == .processing }
    }

    private var idleSessions: [SessionState] {
        sessions.filter { $0.isEffectivelyIdle }
    }

    private var visibleItems: [Item] {
        var items: [Item] = []
        items.append(contentsOf: attentionSessions.map { _ in Item.attention })
        items.append(contentsOf: compactingSessions.map { _ in Item.compacting })
        items.append(contentsOf: runningSessions.map { _ in Item.running })
        items.append(contentsOf: idleSessions.map { _ in Item.idle })

        guard items.count > Self.maxVisible else { return items }
        let keepCount = Self.maxVisible - 1
        let hidden = items.count - keepCount
        return Array(items.prefix(keepCount)) + [.overflow(hidden)]
    }

    // MARK: - Body

    var body: some View {
        HStack(spacing: Self.spacing) {
            ForEach(Array(visibleItems.enumerated()), id: \.offset) { _, item in
                Text(item.char)
                    .font(.system(size: 13, weight: .bold, design: .monospaced))
                    .foregroundColor(item.color)
                    .frame(minWidth: Self.charWidth)
            }
        }
    }

    // MARK: - Item

    private enum Item {
        case attention
        case compacting
        case running
        case idle
        case overflow(Int)

        var char: String {
            switch self {
            case .attention:  return "✓"
            case .compacting: return "◉"
            case .running:    return "●"
            case .idle:       return "·"
            case .overflow(let n): return "+\(n)"
            }
        }

        var color: Color {
            switch self {
            case .attention:  return TerminalColors.green
            case .compacting: return TerminalColors.magenta
            case .running:    return TerminalColors.prompt
            case .idle:       return Color.white.opacity(0.42)
            case .overflow:   return Color.white.opacity(0.5)
            }
        }
    }
}
