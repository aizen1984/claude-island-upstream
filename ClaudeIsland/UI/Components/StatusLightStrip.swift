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
            PulsingLED(color: TerminalColors.prompt, period: 2.0, phaseOffset: Double(index) * 0.2)
        case .waitingForInput:
            Circle()
                .fill(TerminalColors.green)
                .frame(width: Self.dotSize, height: Self.dotSize)
        case .waitingForApproval:
            Circle()
                .fill(TerminalColors.red)
                .frame(width: Self.dotSize, height: Self.dotSize)
        case .compacting:
            PulsingLED(color: TerminalColors.magenta, period: 0.8, phaseOffset: 0)
        default:
            Circle()
                .fill(Color.white.opacity(0.15))
                .frame(width: Self.dotSize, height: Self.dotSize)
        }
    }
}

/// CA 驱动的呼吸点 —— onAppear 启动 repeatForever easeInOut，无 TimelineView、
/// 无 layout pass。period 是 autoreverse 的总周期（半周 = period/2）。
private struct PulsingLED: View {
    let color: Color
    let period: Double
    let phaseOffset: Double

    @State private var breath: Double = 0
    private static let dotSize: CGFloat = 3

    var body: some View {
        Circle()
            .fill(color)
            .frame(width: Self.dotSize, height: Self.dotSize)
            .opacity(0.5 + breath * 0.5)
            .task {
                if phaseOffset > 0 {
                    try? await Task.sleep(nanoseconds: UInt64(phaseOffset * 1_000_000_000))
                }
                withAnimation(.easeInOut(duration: period / 2).repeatForever(autoreverses: true)) {
                    breath = 1.0
                }
            }
    }
}
