//
//  SessionConstellationView.swift
//  ClaudeIsland
//
//  The "session constellation" — an ambient visualization of every current
//  Claude session as a row of dots on the right side of the closed notch.
//
//  Encodes per-session state via shape + color + motion:
//
//    ✓  attention   (waitingForInput / waitingForApproval) — green check
//    ◉  compacting  (context compression in progress)     — magenta, squeeze pulse
//    ●  running     (processing)                          — orange filled, breathing
//    ○  idle                                               — gray ring, static
//
//  Priority order keeps "what needs me now" on the left, "what's resting"
//  on the right: ✓ → ◉ → ● → ○. Max 4 slots visible; surplus collapses to
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
        items.append(contentsOf: attentionSessions.map(Item.attention))
        items.append(contentsOf: compactingSessions.map(Item.compacting))
        items.append(contentsOf: runningSessions.map(Item.running))
        items.append(contentsOf: idleSessions.map(Item.idle))
        return Array(items.prefix(Self.maxVisible))
    }

    private var overflowCount: Int {
        let total =
            attentionSessions.count + compactingSessions.count
            + runningSessions.count + idleSessions.count
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
            Image(systemName: "checkmark")
                .font(.system(size: Self.checkSize, weight: .semibold))
                .foregroundColor(TerminalColors.green)
                .frame(width: Self.checkSize, height: Self.checkSize)
        case .compacting:
            CompactingDot()
        case .running:
            BreathingDot(phaseIndex: runningIndex)
        case .idle:
            Circle()
                .stroke(Color.white.opacity(0.5), lineWidth: 0.8)
                .frame(width: Self.dotSize, height: Self.dotSize)
        }
    }

    /// Returns the zero-based index of this running item among ONLY the
    /// visible running items, so adjacent breathing dots can stagger their
    /// phase.
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
        case compacting(SessionState)
        case running(SessionState)
        case idle(SessionState)

        var id: String {
            switch self {
            case .attention(let s):  return "a-\(s.stableId)"
            case .compacting(let s): return "c-\(s.stableId)"
            case .running(let s):    return "r-\(s.stableId)"
            case .idle(let s):       return "i-\(s.stableId)"
            }
        }
    }
}

// MARK: - Breathing Dot

/// A single orange "running" dot with an opacity-only pulse.
///
/// Uses `TimelineView(.animation)` rather than `.repeatForever` + `.delay`
/// because the latter is unreliable for staggered start phases — SwiftUI
/// sometimes drops the delay on the first cycle, making dots fall into
/// lockstep.
private struct BreathingDot: View {
    let phaseIndex: Int

    var body: some View {
        TimelineView(.animation) { context in
            let elapsed = context.date.timeIntervalSinceReferenceDate
            let period = 1.5
            let offset = Double(phaseIndex) * 0.25
            let t = (sin((elapsed - offset) / period * .pi * 2) + 1) / 2
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

// MARK: - Compacting Dot

/// A magenta dot with a rhythmic squeeze pulse — shrinks to ~50% then
/// bounces back, visually suggesting "compression".
///
/// The animation uses scale (unlike BreathingDot which is opacity-only)
/// because the squeezing IS the semantic: the context is being squeezed
/// smaller. The trough intentionally goes well below the idle ring size
/// so the user can immediately tell this apart from a normal running dot.
private struct CompactingDot: View {
    var body: some View {
        TimelineView(.animation) { context in
            let elapsed = context.date.timeIntervalSinceReferenceDate
            let period = 0.8
            // Asymmetric wave: fast squeeze, slower expand (eased)
            let raw = (sin(elapsed / period * .pi * 2) + 1) / 2  // 0..1
            let t = raw * raw  // ease-in: spends more time expanded
            // Scale: 0.5 (squeezed) → 1.0 (full size)
            let scale = 0.5 + t * 0.5
            // Opacity: subtle dim at squeeze point
            let opacity = 0.7 + t * 0.3

            Circle()
                .fill(TerminalColors.magenta)
                .frame(
                    width: SessionConstellationView.dotSize,
                    height: SessionConstellationView.dotSize
                )
                .scaleEffect(scale)
                .opacity(opacity)
        }
    }
}
