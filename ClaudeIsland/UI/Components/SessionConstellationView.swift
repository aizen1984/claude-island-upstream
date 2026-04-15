//
//  SessionConstellationView.swift
//  ClaudeIsland
//
//  Every Claude session shows as a tiny concentric ripple — a center dot
//  plus optional expanding ring(s). Color + ring rhythm encode the state:
//
//    ●        running     — peach dot, slow outward ripple + firefly-synced breathing
//    ●))      attention   — green dot with fast double-burst rings
//    ◉        compacting  — lilac dot, asymmetric squeeze + medium ripple
//    ·        idle        — dim gray dot, no ripple, slow pulse + Zzz
//
//  Priority keeps "what needs me now" on the left, "what's resting" on the
//  right. Max 4 slots visible; surplus collapses to a "+N" overflow ripple.
//

import SwiftUI

struct SessionConstellationView: View {
    let sessions: [SessionState]
    /// Session IDs that are in attention state AND have not yet been
    /// acknowledged by the user. Passed in so NotchView's
    /// AcknowledgmentTracker stays the single source of truth.
    let unacknowledgedAttentionIds: Set<String>

    // MARK: - Phase-entry tracking
    //
    // Kept UI-local (not in SessionState) so the core state model stays
    // small. Updated on every sessions change via `onChange`.
    //
    // One Dict (was three) — a single filter pass in syncPhaseTracking
    // can't leak. Prior design had three parallel Dicts that had to be
    // filtered in lockstep, easy to miss one and grow memory.

    private struct PhaseTracking {
        let phase: SessionPhase
        let enteredAt: Date
        var celebrationDeadline: Date?
    }

    @State private var phaseTracking: [String: PhaseTracking] = [:]

    /// Only suns that were processing for at least this long get a
    /// celebration animation when they transition to a done state.
    private static let celebrationThreshold: TimeInterval = 60
    private static let celebrationDuration: TimeInterval = 1.5

    // MARK: - Layout constants
    //
    // The `NotchView.constellationSlotWidth()` pixel-budget calculation must
    // stay in sync with these values. If you change iconSize / spacing /
    // maxVisible, update that helper too.

    static let iconSize: CGFloat = 15
    static let spacing: CGFloat = 1
    static let maxVisible: Int = 4

    // 涟漪几何常量：baseR=4, maxR=7.5 在 16×16 参考帧下，
    // → center 直径 = size × 0.5，ring 最大 scale = 7.5 / 4.0。
    static let centerSizeRatio: CGFloat = 0.5
    static let ringMaxScale: CGFloat = 7.5 / 4.0

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

        guard items.count > Self.maxVisible else { return items }
        let keepCount = Self.maxVisible - 1
        let hidden = items.count - keepCount
        return Array(items.prefix(keepCount)) + [.overflow(hidden)]
    }

    // MARK: - Body

    var body: some View {
        let items = visibleItems
        HStack(spacing: Self.spacing) {
            ForEach(Array(items.enumerated()), id: \.element.id) { index, item in
                itemView(item, runningIndex: runningIndex(for: index, in: items))
            }
        }
        .animation(.smooth(duration: 0.25), value: items.map(\.id))
        .onAppear { syncPhaseTracking() }
        .onChange(of: sessions) { _, _ in syncPhaseTracking() }
    }

    /// Updates per-session phase-entry timestamps and schedules celebrations
    /// when a session transitions out of `.processing` after enough work.
    private func syncPhaseTracking() {
        let now = Date()
        let currentIds = Set(sessions.map(\.sessionId))

        for session in sessions {
            let prev = phaseTracking[session.sessionId]
            guard prev?.phase != session.phase else { continue }

            var celebrationDeadline = prev?.celebrationDeadline
            if prev?.phase == .processing,
               let entryTime = prev?.enteredAt,
               now.timeIntervalSince(entryTime) >= Self.celebrationThreshold,
               session.phase == .waitingForInput || session.phase == .idle {
                celebrationDeadline = now.addingTimeInterval(Self.celebrationDuration)
            }

            phaseTracking[session.sessionId] = PhaseTracking(
                phase: session.phase,
                enteredAt: now,
                celebrationDeadline: celebrationDeadline
            )
        }

        // Single filter pass: drop dead sessions + expire stale celebrations.
        phaseTracking = phaseTracking.reduce(into: [:]) { acc, entry in
            guard currentIds.contains(entry.key) else { return }
            var track = entry.value
            if let deadline = track.celebrationDeadline, deadline <= now {
                track.celebrationDeadline = nil
            }
            acc[entry.key] = track
        }
    }

    /// Celebration deadline lookup — replaces the old `celebrationDeadlines`
    /// Dict call sites. Returns nil if no active celebration for session.
    private func celebrationDeadline(for sessionId: String) -> Date? {
        phaseTracking[sessionId]?.celebrationDeadline
    }

    @ViewBuilder
    private func itemView(_ item: Item, runningIndex: Int) -> some View {
        let size = Self.iconSize
        switch item {
        case .attention(let session):
            let deadline = celebrationDeadline(for: session.sessionId)
            RippleIndicator(config: .attention)
                .overlay {
                    if deadline != nil {
                        CelebrationOverlay(deadline: deadline, size: size)
                    }
                }
        case .compacting:
            RippleIndicator(config: .compacting)
        case .running:
            RippleIndicator(config: .running(phaseIndex: runningIndex))
        case .idle(let session):
            let deadline = celebrationDeadline(for: session.sessionId)
            RippleIndicator(config: .idle)
                .overlay {
                    if deadline != nil {
                        CelebrationOverlay(deadline: deadline, size: size)
                    } else {
                        ZzzMark(size: size)
                    }
                }
        case .overflow(let count):
            OverflowRipple(count: count)
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
        case overflow(Int)

        var id: String {
            switch self {
            case .attention(let s):  return "a-\(s.stableId)"
            case .compacting(let s): return "c-\(s.stableId)"
            case .running(let s):    return "r-\(s.stableId)"
            case .idle(let s):       return "i-\(s.stableId)"
            case .overflow(let n):   return "o-\(n)"
            }
        }
    }
}

// MARK: - Celebration

/// Derived animation state for the post-long-work celebration burst.
private struct CelebrationState {
    let isActive: Bool
    let progress: Double   // 0…1 through celebrationDuration
    let scaleBoost: Double // additive to 1.0 base scale

    static let duration: TimeInterval = 1.5

    static func compute(deadline: Date?, now: Date) -> CelebrationState {
        guard let deadline, now < deadline else {
            return CelebrationState(isActive: false, progress: 0, scaleBoost: 0)
        }
        let elapsedInCelebration = duration - deadline.timeIntervalSince(now)
        let progress = min(1.0, max(0, elapsedInCelebration / duration))
        // Scale pop in the first 40% of the celebration, then settle.
        let scaleBoost = progress < 0.4
            ? 0.3 * sin(progress / 0.4 * .pi)
            : 0
        return CelebrationState(isActive: true, progress: progress, scaleBoost: scaleBoost)
    }
}

/// 5 little confetti circles in brand colors flying outward from the ghost's
/// center, fading as they travel.
private func drawCelebrationParticles(
    in context: GraphicsContext,
    size s: CGFloat,
    progress: Double
) {
    let u = s / 100.0
    let cx = 50 * u
    let cy = 50 * u
    let particles: [(angleDeg: Double, color: Color)] = [
        (-90,  TerminalColors.amber),
        (-30,  TerminalColors.green),
        ( 30,  TerminalColors.magenta),
        ( 150, TerminalColors.prompt),
        ( 210, TerminalColors.cyan)
    ]
    let maxDistance = 42.0 * u
    let particleR = 2.6 * u
    let opacity = max(0, sin(progress * .pi) * 1.1)
    let distance = maxDistance * progress

    for p in particles {
        let radians = p.angleDeg * .pi / 180
        let px = cx + CGFloat(cos(radians)) * distance
        let py = cy + CGFloat(sin(radians)) * distance
        let rect = CGRect(
            x: px - particleR,
            y: py - particleR,
            width: particleR * 2,
            height: particleR * 2
        )
        context.fill(Circle().path(in: rect), with: .color(p.color.opacity(opacity)))
    }
}

/// 庆祝覆盖层：仅在有 deadline 且未过期时渲染 TimelineView 驱动的五彩粒子。
/// 这是整个 notch 唯一仍使用 TimelineView 的地方，因其运行时间极短（1.5s），
/// 频率低（需从 processing 进入 idle/waitingForInput 才触发），CPU 影响可忽略。
/// 过期后 `isExpired` 被 `.task` 置 true，外层 `if !isExpired` 直接卸载 TimelineView
/// 而不是靠 TimelineView 内部 isActive 判断——后者仍会按 30Hz 轮询造成 CPU 浪费。
private struct CelebrationOverlay: View {
    let deadline: Date?
    let size: CGFloat

    @State private var isExpired: Bool = false

    var body: some View {
        if let deadline, !isExpired {
            TimelineView(.periodic(from: .now, by: 1.0 / 30.0)) { context in
                let celebration = CelebrationState.compute(deadline: deadline, now: context.date)
                if celebration.isActive {
                    Canvas { ctx, canvasSize in
                        drawCelebrationParticles(
                            in: ctx,
                            size: canvasSize.width,
                            progress: celebration.progress
                        )
                    }
                    .frame(width: size, height: size)
                    .scaleEffect(1.0 + celebration.scaleBoost)
                }
            }
            .task(id: deadline) {
                // deadline 变化 (新一轮庆祝) 时 task 重启，先复位 isExpired 再等待
                isExpired = false
                let wait = deadline.timeIntervalSinceNow
                if wait > 0 {
                    try? await Task.sleep(nanoseconds: UInt64(wait * 1_000_000_000))
                }
                isExpired = true
            }
        }
    }
}

// MARK: - Overflow Ripple (+N)

/// Neutral gray disc with a "+N" label — distinctly larger than the regular
/// dots so the eye instantly reads "and N more sessions".
private struct OverflowRipple: View {
    let count: Int

    var body: some View {
        let size = SessionConstellationView.iconSize
        ZStack {
            Canvas { ctx, canvasSize in
                let u = canvasSize.width / 16.0
                let cx = 8 * u, cy = 8 * u
                let r = 7.0 * u
                let rect = CGRect(x: cx - r, y: cy - r, width: r * 2, height: r * 2)
                ctx.fill(Circle().path(in: rect), with: .color(Color.white.opacity(0.32)))
            }
            .frame(width: size, height: size)

            Text("+\(count)")
                .font(.system(size: size * 0.45, weight: .bold, design: .rounded))
                .foregroundColor(.white.opacity(0.95))
        }
        .frame(width: size, height: size)
    }
}
