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

    @State private var phaseEntryTimes: [String: Date] = [:]
    @State private var lastKnownPhases: [String: SessionPhase] = [:]
    /// Session → when its current celebration animation should end.
    @State private var celebrationDeadlines: [String: Date] = [:]

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
            let prev = lastKnownPhases[session.sessionId]
            guard prev != session.phase else { continue }

            if prev == .processing,
               let entryTime = phaseEntryTimes[session.sessionId],
               now.timeIntervalSince(entryTime) >= Self.celebrationThreshold,
               session.phase == .waitingForInput || session.phase == .idle {
                celebrationDeadlines[session.sessionId] = now.addingTimeInterval(Self.celebrationDuration)
            }

            phaseEntryTimes[session.sessionId] = now
            lastKnownPhases[session.sessionId] = session.phase
        }

        phaseEntryTimes = phaseEntryTimes.filter { currentIds.contains($0.key) }
        lastKnownPhases = lastKnownPhases.filter { currentIds.contains($0.key) }
        celebrationDeadlines = celebrationDeadlines.filter {
            currentIds.contains($0.key) && $0.value > now
        }
    }

    @ViewBuilder
    private func itemView(_ item: Item, runningIndex: Int) -> some View {
        switch item {
        case .attention(let session):
            AttentionRipple(
                celebrationDeadline: celebrationDeadlines[session.sessionId]
            )
        case .compacting:
            CompactingRipple()
        case .running:
            RunningRipple(phaseIndex: runningIndex)
        case .idle(let session):
            IdleRipple(
                celebrationDeadline: celebrationDeadlines[session.sessionId]
            )
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

// MARK: - Running Ripple (工作中)

/// Peach dot with a slow outward ripple and breathing center.
private struct RunningRipple: View {
    let phaseIndex: Int

    @State private var breath: Double = 0
    @State private var ringProgress: Double = 0

    var body: some View {
        let size = SessionConstellationView.iconSize
        let centerSize = size * SessionConstellationView.centerSizeRatio
        let ringMaxScale = SessionConstellationView.ringMaxScale
        ZStack {
            Circle()
                .fill(TerminalColors.prompt)
                .frame(width: centerSize, height: centerSize)
                .opacity(0.78 + breath * 0.22)

            Circle()
                .stroke(TerminalColors.prompt, lineWidth: max(0.6, (1 - ringProgress) * 1.6))
                .frame(width: centerSize, height: centerSize)
                .scaleEffect(1.0 + ringProgress * (ringMaxScale - 1.0))
                .opacity(0.55 * (1 - ringProgress))
        }
        .frame(width: size, height: size)
        .task {
            // .task 随 view 生命周期自动取消，避免 session 短命时
            // 延迟闭包对已销毁视图写 @State
            let phaseDelay = Double(phaseIndex) * 0.25
            if phaseDelay > 0 {
                try? await Task.sleep(nanoseconds: UInt64(phaseDelay * 1_000_000_000))
            }
            withAnimation(.easeInOut(duration: 1.0).repeatForever(autoreverses: true)) {
                breath = 1.0
            }
            withAnimation(.linear(duration: 3.0).repeatForever(autoreverses: false)) {
                ringProgress = 1.0
            }
        }
    }
}

// MARK: - Attention Ripple (喊你)

/// Mint-green dot with fast double-burst ripples — the staggered rings are
/// unique to this state so the user spots it from the corner of their eye.
/// Celebrates briefly when it arrives here after long work.
private struct AttentionRipple: View {
    let celebrationDeadline: Date?

    @State private var centerScale: Double = 1.0
    @State private var r1: Double = 0
    @State private var r2: Double = 0

    var body: some View {
        let size = SessionConstellationView.iconSize
        let centerSize = size * SessionConstellationView.centerSizeRatio
        let ringMaxScale = SessionConstellationView.ringMaxScale
        ZStack {
            Circle()
                .fill(TerminalColors.green)
                .frame(width: centerSize, height: centerSize)
                .scaleEffect(centerScale)

            // 两条独立 ring 展开成兄弟 View（而不是 ForEach），
            // 避免 id:\.self 在 r1==r2 帧发生 ID collision、
            // 也避免数组标识每帧变更导致 CA layer 反复重建。
            Circle()
                .stroke(TerminalColors.green, lineWidth: max(0.6, (1 - r1) * 1.6))
                .frame(width: centerSize, height: centerSize)
                .scaleEffect(1.0 + r1 * (ringMaxScale - 1.0))
                .opacity(0.7 * (1 - r1))
            Circle()
                .stroke(TerminalColors.green, lineWidth: max(0.6, (1 - r2) * 1.6))
                .frame(width: centerSize, height: centerSize)
                .scaleEffect(1.0 + r2 * (ringMaxScale - 1.0))
                .opacity(0.7 * (1 - r2))
        }
        .frame(width: size, height: size)
        .overlay {
            if celebrationDeadline != nil {
                CelebrationOverlay(deadline: celebrationDeadline, size: size)
            }
        }
        .task {
            withAnimation(.easeInOut(duration: 0.3).repeatForever(autoreverses: true)) {
                centerScale = 1.25
            }
            withAnimation(.linear(duration: 0.9).repeatForever(autoreverses: false)) {
                r1 = 1.0
            }
            // 第二条环延迟 0.45s 起跑实现 staggered double-burst
            try? await Task.sleep(nanoseconds: 450_000_000)
            withAnimation(.linear(duration: 0.9).repeatForever(autoreverses: false)) {
                r2 = 1.0
            }
        }
    }
}

// MARK: - Compacting Ripple (被挤)

/// Lilac dot with an asymmetric squeeze + medium ripple — the scale
/// distortion reads as "context is being compressed".
private struct CompactingRipple: View {
    @State private var squeeze: Double = 0  // 0 = wide/short, 1 = narrow/tall
    @State private var ringProgress: Double = 0

    var body: some View {
        let size = SessionConstellationView.iconSize
        let centerSize = size * SessionConstellationView.centerSizeRatio
        let ringMaxScale = SessionConstellationView.ringMaxScale
        let scaleX = 1.0 + (1.0 - squeeze) * 0.18
        let scaleY = 0.75 + squeeze * 0.25
        let centerOpacity = 0.82 + squeeze * 0.18
        ZStack {
            Circle()
                .fill(TerminalColors.magenta)
                .frame(width: centerSize, height: centerSize)
                .opacity(centerOpacity)

            Circle()
                .stroke(TerminalColors.magenta, lineWidth: max(0.6, (1 - ringProgress) * 1.6))
                .frame(width: centerSize, height: centerSize)
                .scaleEffect(1.0 + ringProgress * (ringMaxScale - 1.0))
                .opacity(0.45 * (1 - ringProgress))
        }
        .frame(width: size, height: size)
        .scaleEffect(x: scaleX, y: scaleY)
        .onAppear {
            withAnimation(.easeInOut(duration: 0.4).repeatForever(autoreverses: true)) {
                squeeze = 1.0
            }
            withAnimation(.linear(duration: 1.2).repeatForever(autoreverses: false)) {
                ringProgress = 1.0
            }
        }
    }
}

// MARK: - Idle Ripple (歇了)

/// Dim gray dot, no rings, with a floating Zzz. Celebrates briefly when
/// arriving here after long work.
private struct IdleRipple: View {
    let celebrationDeadline: Date?

    @State private var centerBreath: Double = 0
    @State private var zzzOffsetY: Double = -2
    @State private var zzzOpacity: Double = 0

    var body: some View {
        let size = SessionConstellationView.iconSize
        let centerSize = size * SessionConstellationView.centerSizeRatio
        ZStack {
            Circle()
                .fill(Color.white.opacity(0.7))
                .frame(width: centerSize, height: centerSize)
                .opacity(0.45 + centerBreath * 0.35)

            if celebrationDeadline == nil {
                Text("Z")
                    .font(.system(size: size * 0.42, weight: .black, design: .rounded))
                    .italic()
                    .foregroundColor(Color.white.opacity(zzzOpacity))
                    .offset(x: size * 0.32, y: zzzOffsetY - size * 0.18)
            }
        }
        .frame(width: size, height: size)
        .overlay {
            if celebrationDeadline != nil {
                CelebrationOverlay(deadline: celebrationDeadline, size: size)
            }
        }
        .onAppear {
            withAnimation(.easeInOut(duration: 1.5).repeatForever(autoreverses: true)) {
                centerBreath = 1.0
            }
            withAnimation(.linear(duration: 2.5).repeatForever(autoreverses: false)) {
                zzzOffsetY = -8.0
            }
            // zzzOpacity 与 zzzOffsetY 解耦：上浮线性循环 2.5s，
            // opacity 用 1.25s autoreverse 淡入淡出，两者交错产生飘散感
            withAnimation(.easeInOut(duration: 1.25).repeatForever(autoreverses: true)) {
                zzzOpacity = 0.5
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
