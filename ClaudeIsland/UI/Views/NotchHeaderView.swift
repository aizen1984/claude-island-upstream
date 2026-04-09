//
//  NotchHeaderView.swift
//  ClaudeIsland
//
//  Header bar for the dynamic island
//

import Combine
import SwiftUI

// MARK: - Four-Leaf Clover Icon (customization)
//
// Replaced earlier 6-petal sparkle (too thin) and 4-circle attempt (not
// petal-like enough) with cubic-bezier teardrop petals — narrow at base,
// widest around the middle, rounded at tip. Four petals at 90° intervals
// radiate from shape center. Color stays Claude orange for brand
// consistency. Rotates once per 10 seconds (nearly imperceptible) —
// adds life without distracting.
//
// Struct name `ClaudeCrabIcon` and init signature preserved for binary
// compatibility with NotchView.swift call sites.

private struct CloverLeaf: Shape {
    let leafIndex: Int  // 0=N, 1=E, 2=S, 3=W

    func path(in rect: CGRect) -> Path {
        let center = CGPoint(x: rect.midX, y: rect.midY)
        let r = min(rect.width, rect.height) / 2
        // Angle for this leaf — index 0 points North (up in screen coords)
        let angleRad = Double(leafIndex) * .pi / 2 - .pi / 2

        // Petal dimensions in local coords (origin = shape center, +x = leaf tip)
        let length = r * 0.95   // leaf length from base to tip
        let width = r * 0.62    // max leaf width (perpendicular)

        var localPath = Path()
        localPath.move(to: .zero)

        // Top half: cubic bezier from base (0,0) to tip (length, 0).
        // Control points create a rapid bulge then smooth taper to rounded tip.
        localPath.addCurve(
            to: CGPoint(x: length, y: 0),
            control1: CGPoint(x: length * 0.10, y: -width * 0.85),
            control2: CGPoint(x: length * 0.90, y: -width * 0.55)
        )
        // Bottom half: mirror — from tip back to base
        localPath.addCurve(
            to: .zero,
            control1: CGPoint(x: length * 0.90, y: width * 0.55),
            control2: CGPoint(x: length * 0.10, y: width * 0.85)
        )

        // Transform: rotate the local leaf to its compass direction, then
        // translate the shape's origin (0,0) to the rect's center.
        let transform = CGAffineTransform.identity
            .translatedBy(x: center.x, y: center.y)
            .rotated(by: CGFloat(angleRad))

        return localPath.applying(transform)
    }
}

struct ClaudeCrabIcon: View {
    let size: CGFloat
    let color: Color
    var animateLegs: Bool = false

    @State private var rotation: Double = 0

    init(size: CGFloat = 16, color: Color = Color(red: 0.85, green: 0.47, blue: 0.34), animateLegs: Bool = false) {
        self.size = size
        self.color = color
        self.animateLegs = animateLegs
    }

    var body: some View {
        ZStack {
            ForEach(0..<4, id: \.self) { i in
                CloverLeaf(leafIndex: i)
                    .fill(color)
            }
        }
        .frame(width: size * (66.0 / 52.0), height: size)
        .rotationEffect(.degrees(rotation))
        .onAppear {
            withAnimation(
                .linear(duration: 10.0).repeatForever(autoreverses: false)
            ) {
                rotation = 360
            }
        }
    }
}

// MARK: - Bouncing Dots Icon (replaces pixel-art question mark)
//
// Three dots with phase-offset bouncing — the classic "thinking/typing/
// working" visual used across modern messaging UIs. Activates only when
// `hasPendingPermission == true`; with the auto-allow hook patch this
// rarely shows, but when it does, users see a familiar "working" animation
// instead of an ugly pixel question mark.

struct PermissionIndicatorIcon: View {
    let size: CGFloat
    let color: Color

    @State private var bouncing: Bool = false

    init(size: CGFloat = 14, color: Color = Color(red: 0.85, green: 0.47, blue: 0.34)) {
        self.size = size
        self.color = color
    }

    var body: some View {
        HStack(spacing: size * 0.12) {
            ForEach(0..<3, id: \.self) { i in
                Circle()
                    .fill(color)
                    .frame(width: size * 0.22, height: size * 0.22)
                    .offset(y: bouncing ? -size * 0.18 : size * 0.18)
                    .animation(
                        .easeInOut(duration: 0.45)
                            .repeatForever(autoreverses: true)
                            .delay(Double(i) * 0.13),
                        value: bouncing
                    )
            }
        }
        .frame(width: size, height: size)
        .onAppear { bouncing = true }
    }
}

// MARK: - Ready For Input Icon (upgraded)
//
// Customization: replaced 7-pixel-dot checkmark with SF Symbol
// `checkmark.circle.fill` — a filled green circle with a white checkmark.
// Much more visible than the original pixel art. Adds a subtle scale pulse
// (1.0 ↔ 1.18, 0.9s period) to draw attention when it first appears.
// Uses Core Animation scale transform = zero CPU cost.

struct ReadyForInputIndicatorIcon: View {
    let size: CGFloat
    let color: Color

    @State private var pulsing: Bool = false

    init(size: CGFloat = 14, color: Color = TerminalColors.green) {
        self.size = size
        self.color = color
    }

    var body: some View {
        Image(systemName: "checkmark.circle.fill")
            .font(.system(size: size * 1.15, weight: .bold))
            .foregroundColor(color)
            .scaleEffect(pulsing ? 1.18 : 1.0)
            .animation(
                .easeInOut(duration: 0.9).repeatForever(autoreverses: true),
                value: pulsing
            )
            .frame(width: size, height: size)
            .onAppear { pulsing = true }
    }
}

// MARK: - Header Progress Bar (customization)
//
// A continuously looping indeterminate progress bar used as the menu
// toggle button's visual. Replaces the original tiny line.3.horizontal
// icon that rendered as an ugly blob at 11px/40% opacity. A bright
// highlight slides left-to-right continuously on a dimmer track, giving
// a sense of "always-active" liveness to the notch header.
//
// Pure SwiftUI Shape + Core Animation offset = GPU-accelerated, zero CPU.

struct HeaderProgressBar: View {
    var tint: Color = .white
    @State private var phase: CGFloat = 0

    var body: some View {
        GeometryReader { geo in
            let trackW = geo.size.width
            let highlightW = trackW * 0.40
            ZStack(alignment: .leading) {
                Capsule()
                    .fill(tint.opacity(0.22))
                Capsule()
                    .fill(tint.opacity(0.90))
                    .frame(width: highlightW)
                    .offset(x: phase * (trackW + highlightW) - highlightW)
            }
            .clipShape(Capsule())
        }
        .onAppear {
            withAnimation(.linear(duration: 1.4).repeatForever(autoreverses: false)) {
                phase = 1
            }
        }
    }
}
