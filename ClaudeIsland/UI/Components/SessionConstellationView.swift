//
//  SessionConstellationView.swift
//  ClaudeIsland
//
//  The "session constellation" — an ambient visualization of every current
//  Claude session as a row of dots on the right side of the closed notch.
//
//  Replaces the previous swappable indicator picker (BrickWall, DotsWave,
//  EQBars, …) with a single unified view that encodes per-session state via
//  shape + color + motion:
//
//    ✓  attention  (waitingForInput / waitingForApproval)  — green check
//    ●  running    (processing / compacting)               — orange filled, breathing
//    ○  idle                                                 — gray ring, static
//
//  Priority order keeps "what needs me now" on the left, "what's resting"
//  on the right: ✓ → ● → ○. Max 4 slots visible; surplus collapses to
//  `·+N` overflow suffix.
//

import SwiftUI

struct SessionConstellationView: View {
    let sessions: [SessionState]
    /// Session IDs that are in attention state AND have not yet been
    /// acknowledged by the user. Passed in so NotchView's
    /// AcknowledgmentTracker stays the single source of truth.
    let unacknowledgedAttentionIds: Set<String>

    // MARK: - Layout constants
    //
    // The `NotchView.constellationSlotWidth()` pixel-budget calculation must
    // stay in sync with these values. If you change dotSize / checkSize /
    // spacing / maxVisible, update that helper too.

    static let dotSize: CGFloat = 6
    static let checkSize: CGFloat = 11
    static let spacing: CGFloat = 4
    static let maxVisible: Int = 4

    // MARK: - Categorization

    private var attentionSessions: [SessionState] {
        sessions.filter {
            $0.needsAttention && unacknowledgedAttentionIds.contains($0.sessionId)
        }
    }

    private var runningSessions: [SessionState] {
        sessions.filter { $0.phase == .processing || $0.phase == .compacting }
    }

    private var idleSessions: [SessionState] {
        sessions.filter { $0.phase == .idle }
    }

    private var visibleItems: [Item] {
        var items: [Item] = []
        items.append(contentsOf: attentionSessions.map(Item.attention))
        items.append(contentsOf: runningSessions.map(Item.running))
        items.append(contentsOf: idleSessions.map(Item.idle))
        return Array(items.prefix(Self.maxVisible))
    }

    private var overflowCount: Int {
        let total =
            attentionSessions.count + runningSessions.count + idleSessions.count
        return max(0, total - Self.maxVisible)
    }

    // MARK: - Body

    var body: some View {
        let items = visibleItems
        HStack(spacing: Self.spacing) {
            ForEach(Array(items.enumerated()), id: \.element.id) { index, item in
                itemView(item, runningIndex: runningIndex(for: index, in: items))
            }

            if overflowCount > 0 {
                Text("·+\(overflowCount)")
                    .font(.system(size: 9, weight: .black, design: .monospaced))
                    .foregroundColor(.white.opacity(0.45))
                    .padding(.leading, 1)
            }
        }
        .animation(.smooth(duration: 0.25), value: items.map(\.id))
    }

    @ViewBuilder
    private func itemView(_ item: Item, runningIndex: Int) -> some View {
        switch item {
        case .attention:
            // Matches the old multi-checkmark glyph from NotchView — same
            // SF Symbol, same size, same color — so existing muscle memory
            // (green ✓ = "I'm done, look at me") survives the refactor.
            Image(systemName: "checkmark")
                .font(.system(size: Self.checkSize, weight: .semibold))
                .foregroundColor(TerminalColors.green)
                .frame(width: Self.checkSize, height: Self.checkSize)
        case .running(let session):
            BreathingDot(
                phaseIndex: runningIndex,
                fast: session.phase == .compacting
            )
        case .idle:
            // 0.8pt stroke (not 1pt) — a 1pt ring on a 6pt frame visually
            // "blooms" ~12% larger than an equally sized filled circle,
            // which is why running dots looked smaller than idle rings in
            // the first draft. Thinner stroke = less optical weight =
            // better harmony with the filled running dots.
            Circle()
                .stroke(Color.white.opacity(0.5), lineWidth: 0.8)
                .frame(width: Self.dotSize, height: Self.dotSize)
        }
    }

    /// Returns the zero-based index of this running item among ONLY the
    /// visible running items, so adjacent breathing dots can stagger their
    /// phase. Non-running items don't count — a constellation of
    /// `✓ ● ● ○` gives the two running dots indices 0 and 1.
    private func runningIndex(for itemIndex: Int, in items: [Item]) -> Int {
        var runningCounter = 0
        for (idx, it) in items.enumerated() {
            if case .running = it {
                if idx == itemIndex { return runningCounter }
                runningCounter += 1
            }
        }
        return 0
    }

    // MARK: - Item

    private enum Item: Identifiable {
        case attention(SessionState)
        case running(SessionState)
        case idle(SessionState)

        var id: String {
            switch self {
            case .attention(let s): return "a-\(s.stableId)"
            case .running(let s):   return "r-\(s.stableId)"
            case .idle(let s):      return "i-\(s.stableId)"
            }
        }
    }
}

// MARK: - Breathing Dot

/// A single orange "running" dot with an opacity-only pulse.
///
/// Design note on why this is opacity-only, no scale:
///   The first draft used `scaleEffect(0.92…1.0)` to add a subtle "beat"
///   to the breathing, but it made running dots visually shrink below
///   the idle rings during the breath's trough — destroying constellation
///   harmony. Dots must stay at a rock-steady 6pt so filled and outline
///   siblings read as peers; the pulse lives purely in opacity.
///
/// Uses `TimelineView(.animation)` rather than `.repeatForever` + `.delay`
/// because the latter is unreliable for staggered start phases — SwiftUI
/// sometimes drops the delay on the first cycle, making dots fall into
/// lockstep. Driving the phase explicitly from wall-clock time sidesteps
/// that entirely.
///
/// Cost: one sine eval per dot per frame. Negligible for ≤4 dots.
private struct BreathingDot: View {
    let phaseIndex: Int
    let fast: Bool

    var body: some View {
        TimelineView(.animation) { context in
            let elapsed = context.date.timeIntervalSinceReferenceDate
            let period = fast ? 0.9 : 1.5
            let offset = Double(phaseIndex) * 0.25
            // 0..1 sinusoid, staggered per dot
            let t = (sin((elapsed - offset) / period * .pi * 2) + 1) / 2
            // Tighter opacity range (0.6→1.0) so the dot never fades to
            // the point where it "disappears" next to the static idle
            // rings — the pulse should feel like breathing, not blinking.
            let opacity = 0.6 + t * 0.4

            Circle()
                .fill(TerminalColors.prompt)
                .frame(
                    width: SessionConstellationView.dotSize,
                    height: SessionConstellationView.dotSize
                )
                .opacity(opacity)
        }
    }
}
