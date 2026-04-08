//
//  NotchHeaderView.swift
//  ClaudeIsland
//
//  Header bar for the dynamic island
//

import Combine
import SwiftUI

// MARK: - Claude Sparkle Icon (customization)
//
// Replaced original pixel-art crab with a 6-petal Claude-brand sparkle.
// Each petal is a narrow diamond radiating from center at 60° intervals.
// When `animateLegs == true`, each petal fades opacity independently with
// a 0.5s phase offset, creating a "chasing glow" effect. Pure Core Animation
// (no Canvas redraws, no timers) — static state is ~0% CPU, animated state
// is ~0.1% CPU (opacity is a GPU-accelerated layer property).
//
// Struct name and init signature preserved for binary compatibility with
// NotchView.swift call sites (ClaudeCrabIcon(size:color:animateLegs:)).

private struct ClaudeSparklePetal: Shape {
    let petalIndex: Int

    func path(in rect: CGRect) -> Path {
        var path = Path()
        let center = CGPoint(x: rect.midX, y: rect.midY)
        let radius = min(rect.width, rect.height) / 2
        let angleRad = Double(petalIndex) * .pi / 3.0  // 60° spacing for 6 petals

        let cosA = CGFloat(cos(angleRad))
        let sinA = CGFloat(sin(angleRad))

        // Tip of petal (outer point)
        let tip = CGPoint(
            x: center.x + radius * cosA,
            y: center.y + radius * sinA
        )

        // Base width — narrow diamond shape
        let baseRadius = radius * 0.22
        let perpCos = CGFloat(cos(angleRad + .pi / 2))
        let perpSin = CGFloat(sin(angleRad + .pi / 2))

        let leftBase = CGPoint(
            x: center.x + baseRadius * perpCos,
            y: center.y + baseRadius * perpSin
        )
        let rightBase = CGPoint(
            x: center.x - baseRadius * perpCos,
            y: center.y - baseRadius * perpSin
        )

        // Diamond petal: center -> left base -> tip -> right base -> close
        path.move(to: center)
        path.addLine(to: leftBase)
        path.addLine(to: tip)
        path.addLine(to: rightBase)
        path.closeSubpath()

        return path
    }
}

struct ClaudeCrabIcon: View {
    let size: CGFloat
    let color: Color
    var animateLegs: Bool = false

    @State private var glowing: Bool = false

    init(size: CGFloat = 16, color: Color = Color(red: 0.85, green: 0.47, blue: 0.34), animateLegs: Bool = false) {
        self.size = size
        self.color = color
        self.animateLegs = animateLegs
    }

    var body: some View {
        ZStack {
            ForEach(0..<6, id: \.self) { i in
                ClaudeSparklePetal(petalIndex: i)
                    .fill(color)
                    .opacity(animateLegs && glowing ? 1.0 : (animateLegs ? 0.3 : 0.85))
                    .animation(
                        animateLegs
                            ? .easeInOut(duration: 1.5)
                                .repeatForever(autoreverses: true)
                                .delay(Double(i) * 0.5)
                            : .default,
                        value: glowing
                    )
            }
        }
        .frame(width: size * (66.0 / 52.0), height: size)
        .onAppear {
            if animateLegs {
                glowing = true
            }
        }
        .onChange(of: animateLegs) { _, newValue in
            glowing = newValue
        }
    }
}

// MARK: - Loading Ring Icon (replaces pixel-art question mark)
//
// Customization: replaced PermissionIndicatorIcon's pixel-art question mark
// with a classic rotating loading ring (3/4 arc). Drawn once as a Circle
// shape with trim + stroke, animated via rotationEffect. Pure GPU transform.
//
// Appears in the header only when `hasPendingPermission == true`. With the
// auto-allow hook patch, this should be extremely rare — but when it briefly
// flashes during PreToolUse -> auto-allow, users see a smooth spinner instead
// of an ugly pixel question mark.

struct PermissionIndicatorIcon: View {
    let size: CGFloat
    let color: Color

    @State private var rotation: Double = 0

    init(size: CGFloat = 14, color: Color = Color(red: 0.85, green: 0.47, blue: 0.34)) {
        self.size = size
        self.color = color
    }

    var body: some View {
        Circle()
            .trim(from: 0, to: 0.75)  // 3/4 arc leaves a visible gap
            .stroke(
                color,
                style: StrokeStyle(lineWidth: 1.8, lineCap: .round)
            )
            .frame(width: size, height: size)
            .rotationEffect(.degrees(rotation))
            .onAppear {
                withAnimation(
                    .linear(duration: 1.2).repeatForever(autoreverses: false)
                ) {
                    rotation = 360
                }
            }
    }
}

// MARK: - Ready For Input Icon (unchanged)
//
// Pixel art checkmark shown on the right side of the header when a session
// is waiting for user input. Kept as original — no ugly-factor complaint.

struct ReadyForInputIndicatorIcon: View {
    let size: CGFloat
    let color: Color

    init(size: CGFloat = 14, color: Color = TerminalColors.green) {
        self.size = size
        self.color = color
    }

    // Checkmark shape pixel positions (at 30x30 scale)
    private let pixels: [(CGFloat, CGFloat)] = [
        (5, 15),                    // Start of checkmark
        (9, 19),                    // Down stroke
        (13, 23),                   // Bottom of checkmark
        (17, 19),                   // Up stroke begins
        (21, 15),                   // Up stroke
        (25, 11),                   // Up stroke
        (29, 7)                     // End of checkmark
    ]

    var body: some View {
        Canvas { context, canvasSize in
            let scale = size / 30.0
            let pixelSize: CGFloat = 4 * scale

            for (x, y) in pixels {
                let rect = CGRect(
                    x: x * scale - pixelSize / 2,
                    y: y * scale - pixelSize / 2,
                    width: pixelSize,
                    height: pixelSize
                )
                context.fill(Path(rect), with: .color(color))
            }
        }
        .frame(width: size, height: size)
    }
}
