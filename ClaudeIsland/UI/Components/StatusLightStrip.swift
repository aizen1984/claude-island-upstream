//
//  StatusLightStrip.swift
//  ClaudeIsland
//
//  A row of tiny LED dots shown below the closed notch, one per active
//  session, color-coded by phase. Gives peripheral-vision state feedback
//  without expanding the island.
//

import SwiftUI

struct StatusLightStrip: View {
    let sessions: [SessionState]

    private static let dotSize: CGFloat = 3
    private static let spacing: CGFloat = 3
    private static let maxDots: Int = 6

    var body: some View {
        HStack(spacing: Self.spacing) {
            ForEach(Array(sessions.prefix(Self.maxDots).enumerated()), id: \.element.sessionId) { index, session in
                ledDot(for: session.phase, index: index)
            }
        }
        .frame(height: 6)
        .animation(.smooth(duration: 0.25), value: sessions.map(\.sessionId))
    }

    @ViewBuilder
    private func ledDot(for phase: SessionPhase, index: Int) -> some View {
        switch phase {
        case .processing:
            TimelineView(.animation) { context in
                let elapsed = context.date.timeIntervalSinceReferenceDate
                let offset = Double(index) * 0.2
                let t = (sin((elapsed - offset) / 1.5 * .pi * 2) + 1) / 2
                Circle()
                    .fill(TerminalColors.prompt)
                    .frame(width: Self.dotSize, height: Self.dotSize)
                    .opacity(0.5 + t * 0.5)
            }
        case .waitingForInput:
            Circle()
                .fill(TerminalColors.green)
                .frame(width: Self.dotSize, height: Self.dotSize)
        case .waitingForApproval:
            Circle()
                .fill(TerminalColors.red)
                .frame(width: Self.dotSize, height: Self.dotSize)
        case .compacting:
            TimelineView(.animation) { context in
                let elapsed = context.date.timeIntervalSinceReferenceDate
                let t = (sin(elapsed / 0.8 * .pi * 2) + 1) / 2
                Circle()
                    .fill(TerminalColors.magenta)
                    .frame(width: Self.dotSize, height: Self.dotSize)
                    .opacity(0.5 + t * 0.5)
            }
        default:
            Circle()
                .fill(Color.white.opacity(0.15))
                .frame(width: Self.dotSize, height: Self.dotSize)
        }
    }
}
