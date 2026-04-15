//
//  RippleIndicator.swift
//  ClaudeIsland
//
//  Generic ripple primitive for the session constellation row.
//  Covers Running / Attention / Compacting / Idle by swapping a
//  RippleConfig — all visual variation is declarative. Zzz and
//  Celebration overlays live OUTSIDE the primitive (layered on by
//  call sites via `.overlay{}`), so this view stays pure geometry +
//  rhythm.
//

import SwiftUI

// MARK: - Range01

/// Linear interpolation endpoints. `value(at: 0) = at0`, `value(at: 1) = at1`.
/// Allowed to be inverted (at0 > at1) so configs can express shrinking
/// scales without awkward range mirroring.
struct Range01 {
    let at0: Double
    let at1: Double
    func value(at t: Double) -> Double { at0 + (at1 - at0) * t }
}

// MARK: - RippleConfig

/// Value-typed description of a Ripple's animation rhythm. One center
/// animator (`centerT`, 0→1 ping-pong) drives both center opacity/scale
/// and the container's x/y scale, which keeps the two visually
/// phase-locked (Compacting relies on this). Rings run on their own
/// linear loop independent of the center.
struct RippleConfig {
    let color: Color

    struct Center {
        let period: Double
        let opacity: Range01
        let scale: Range01
    }
    let center: Center

    struct Ring {
        let period: Double
        let peakOpacity: Double
        let phaseDelay: Double
    }
    /// Up to 2 rings. Rendered as sibling views (not ForEach) to avoid the
    /// ID collision bug that bit AttentionRipple in iter1.
    let rings: [Ring]

    struct Container {
        let scaleX: Range01
        let scaleY: Range01
    }
    let container: Container

    /// Stagger this ripple's center animator by N seconds before kicking
    /// off, so adjacent running slots breathe out of phase. Use
    /// `Double(slotIndex) * 0.25` to spread N slots around.
    let centerPhaseOffset: Double
}

// MARK: - Ripple configs (phase → rhythm)

extension RippleConfig {
    /// Peach dot, slow breath + single ripple. Running slot index staggers
    /// the center animator so adjacent dots don't breathe in lockstep.
    static func running(phaseIndex: Int) -> RippleConfig {
        RippleConfig(
            color: TerminalColors.prompt,
            center: .init(period: 1.0, opacity: .init(at0: 0.78, at1: 1.0), scale: .init(at0: 1.0, at1: 1.0)),
            rings: [.init(period: 3.0, peakOpacity: 0.55, phaseDelay: 0)],
            container: .init(scaleX: .init(at0: 1.0, at1: 1.0), scaleY: .init(at0: 1.0, at1: 1.0)),
            centerPhaseOffset: Double(phaseIndex) * 0.25
        )
    }

    /// Mint-green pulse + staggered double-burst rings. Eye-catching.
    static let attention = RippleConfig(
        color: TerminalColors.green,
        center: .init(period: 0.3, opacity: .init(at0: 1.0, at1: 1.0), scale: .init(at0: 1.0, at1: 1.25)),
        rings: [
            .init(period: 0.9, peakOpacity: 0.7, phaseDelay: 0),
            .init(period: 0.9, peakOpacity: 0.7, phaseDelay: 0.45)
        ],
        container: .init(scaleX: .init(at0: 1.0, at1: 1.0), scaleY: .init(at0: 1.0, at1: 1.0)),
        centerPhaseOffset: 0
    )

    /// Lilac asymmetric squeeze + medium ripple. Center opacity and
    /// container scale ride the SAME animator (same period), which reads
    /// as "the dot is being compressed".
    static let compacting = RippleConfig(
        color: TerminalColors.magenta,
        center: .init(period: 0.4, opacity: .init(at0: 0.82, at1: 1.0), scale: .init(at0: 1.0, at1: 1.0)),
        rings: [.init(period: 1.2, peakOpacity: 0.45, phaseDelay: 0)],
        container: .init(scaleX: .init(at0: 1.18, at1: 1.0), scaleY: .init(at0: 0.75, at1: 1.0)),
        centerPhaseOffset: 0
    )

    /// Dim gray breath, no rings. Zzz text + celebration layered on by
    /// the call site as `.overlay{}` — they're not part of the rhythm.
    static let idle = RippleConfig(
        color: Color.white.opacity(0.7),
        center: .init(period: 1.5, opacity: .init(at0: 0.45, at1: 0.80), scale: .init(at0: 1.0, at1: 1.0)),
        rings: [],
        container: .init(scaleX: .init(at0: 1.0, at1: 1.0), scaleY: .init(at0: 1.0, at1: 1.0)),
        centerPhaseOffset: 0
    )
}

// MARK: - RippleIndicator

struct RippleIndicator: View {
    let config: RippleConfig

    @State private var centerT: Double = 0
    @State private var ring1T: Double = 0
    @State private var ring2T: Double = 0

    var body: some View {
        let size = SessionConstellationView.iconSize
        let centerSize = size * SessionConstellationView.centerSizeRatio
        let ringMaxScale = SessionConstellationView.ringMaxScale

        ZStack {
            Circle()
                .fill(config.color)
                .frame(width: centerSize, height: centerSize)
                .opacity(config.center.opacity.value(at: centerT))
                .scaleEffect(config.center.scale.value(at: centerT))

            if config.rings.count >= 1 {
                ringView(progress: ring1T, peakOpacity: config.rings[0].peakOpacity,
                         centerSize: centerSize, maxScale: ringMaxScale)
            }
            if config.rings.count >= 2 {
                ringView(progress: ring2T, peakOpacity: config.rings[1].peakOpacity,
                         centerSize: centerSize, maxScale: ringMaxScale)
            }
        }
        .frame(width: size, height: size)
        .scaleEffect(
            x: config.container.scaleX.value(at: centerT),
            y: config.container.scaleY.value(at: centerT)
        )
        .task {
            if config.centerPhaseOffset > 0 {
                try? await Task.sleep(nanoseconds: UInt64(config.centerPhaseOffset * 1_000_000_000))
            }
            withAnimation(.easeInOut(duration: config.center.period).repeatForever(autoreverses: true)) {
                centerT = 1.0
            }
            if let r1 = config.rings.first {
                if r1.phaseDelay > 0 {
                    try? await Task.sleep(nanoseconds: UInt64(r1.phaseDelay * 1_000_000_000))
                }
                withAnimation(.linear(duration: r1.period).repeatForever(autoreverses: false)) {
                    ring1T = 1.0
                }
            }
            if config.rings.count >= 2 {
                let r2 = config.rings[1]
                if r2.phaseDelay > 0 {
                    try? await Task.sleep(nanoseconds: UInt64(r2.phaseDelay * 1_000_000_000))
                }
                withAnimation(.linear(duration: r2.period).repeatForever(autoreverses: false)) {
                    ring2T = 1.0
                }
            }
        }
    }

    @ViewBuilder
    private func ringView(progress p: Double, peakOpacity: Double,
                          centerSize: CGFloat, maxScale: CGFloat) -> some View {
        Circle()
            .stroke(config.color, lineWidth: max(0.6, (1 - p) * 1.6))
            .frame(width: centerSize, height: centerSize)
            .scaleEffect(1.0 + p * (maxScale - 1.0))
            .opacity(peakOpacity * (1 - p))
    }
}

// MARK: - ZzzMark (idle overlay)

/// Floating "Z" that drifts up and fades. Decoupled from the idle ripple
/// body so the ripple primitive stays pure geometry.
struct ZzzMark: View {
    let size: CGFloat

    @State private var offsetY: Double = -2
    @State private var opacity: Double = 0

    var body: some View {
        Text("Z")
            .font(.system(size: size * 0.42, weight: .black, design: .rounded))
            .italic()
            .foregroundColor(Color.white.opacity(opacity))
            .offset(x: size * 0.32, y: offsetY - size * 0.18)
            .onAppear {
                withAnimation(.linear(duration: 2.5).repeatForever(autoreverses: false)) {
                    offsetY = -8.0
                }
                // offset 线性循环 2.5s，opacity 1.25s autoreverse 淡入淡出，
                // 两者错频产生飘散感。
                withAnimation(.easeInOut(duration: 1.25).repeatForever(autoreverses: true)) {
                    opacity = 0.5
                }
            }
    }
}
