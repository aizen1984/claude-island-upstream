//
//  NotchView.swift
//  ClaudeIsland
//
//  The main dynamic island SwiftUI view with accurate notch shape
//

import AppKit
import Combine
import CoreGraphics
import SwiftUI

// Corner radius constants
private let cornerRadiusInsets = (
    opened: (top: CGFloat(19), bottom: CGFloat(24)),
    closed: (top: CGFloat(6), bottom: CGFloat(14))
)

struct NotchView: View {
    @ObservedObject var viewModel: NotchViewModel
    @StateObject private var sessionMonitor = ClaudeSessionMonitor()
    @StateObject private var activityCoordinator = NotchActivityCoordinator.shared
    @ObservedObject private var updateManager = UpdateManager.shared
    @ObservedObject private var ackTracker = AcknowledgmentTracker.shared
    @ObservedObject private var pauseController = AnimationPauseController.shared
    @State private var previousWaitingForInputIds: Set<String> = []
    @State private var isVisible: Bool = false
    @State private var isHovering: Bool = false
    @State private var statusPhrase: String = ""
    @State private var dotCount: Int = 0
    @State private var wasProcessing: Bool = false
    @State private var textCelebrationUntil: Date? = nil
    @AppStorage("status.text.preset") private var statusTextPreset: String = "搬砖中"
    @AppStorage("notch.displayMode") private var displayModeRaw: String = NotchDisplayMode.animated.rawValue

    private var displayMode: NotchDisplayMode {
        NotchDisplayMode(rawValue: displayModeRaw) ?? .animated
    }

    /// Primary session phase used to color the status text. Priority:
    /// attention > compacting > processing > idle.
    private var primaryStatusPhase: SessionPhase {
        let instances = sessionMonitor.instances
        if instances.contains(where: { $0.needsAttention && !ackTracker.isAcknowledged($0.sessionId) }) {
            return .waitingForInput
        }
        if instances.contains(where: { $0.phase == .compacting }) {
            return .compacting
        }
        if instances.contains(where: { $0.phase == .processing }) {
            return .processing
        }
        return .idle
    }

    private var statusTextColor: Color {
        switch primaryStatusPhase {
        case .waitingForInput, .waitingForApproval: return TerminalColors.green
        case .compacting:                            return TerminalColors.magenta
        case .processing:                            return TerminalColors.prompt
        case .idle, .ended:                          return Color.white.opacity(0.6)
        }
    }

    /// Whether any Claude session is currently processing or compacting
    private var isAnyProcessing: Bool {
        sessionMonitor.instances.contains { $0.phase == .processing || $0.phase == .compacting }
    }

    /// Sessions that need user attention — completion (.waitingForInput) or
    /// permission ask (.waitingForApproval) — that have NOT yet been
    /// acknowledged by the user (via ⌘⇧U focus or clicking ✅).
    /// Each one renders as its own checkmark in the compact header.
    ///
    /// Customization: unified "completion" and "ask" events into a single
    /// checkmark indicator per user request — the island never auto-expands;
    /// it only shows N checkmarks = N unseen sessions. Acknowledging a
    /// session removes its checkmark until the next fresh completion.
    private var attentionSessions: [SessionState] {
        sessionMonitor.pendingInstances.filter {
            !ackTracker.isAcknowledged($0.sessionId)
        }
    }

    private var hasAttention: Bool {
        !attentionSessions.isEmpty
    }

    private var hasAnySessions: Bool {
        !sessionMonitor.instances.isEmpty
    }

    // MARK: - Morphing Shape

    private enum MorphingShape: Equatable {
        case rest      // idle or no sessions
        case runway    // processing — wider
        case bubble    // waitingForApproval — wider + taller
    }

    private var morphingShape: MorphingShape {
        let sessions = sessionMonitor.instances
        if sessions.contains(where: { $0.phase.isWaitingForApproval }) { return .bubble }
        if sessions.contains(where: { $0.phase.isActive }) { return .runway }
        return .rest
    }

    // MARK: - Sizing

    private var closedNotchSize: CGSize {
        let base = viewModel.deviceNotchRect
        switch morphingShape {
        case .rest:
            return CGSize(width: base.width, height: base.height)
        case .runway:
            return CGSize(width: base.width + 12, height: base.height)
        case .bubble:
            return CGSize(width: base.width + 8, height: base.height + 4)
        }
    }

    /// Extra width the compact header needs on top of the physical notch
    /// cutout. Composed of:
    ///   · leftSlot  — status text ("牛马中…") with leading padding
    ///   · rightSlot — SessionConstellationView (✓ / ● / ○ dot row)
    /// Both slots grow/shrink reactively with session count, so the island
    /// only takes the space it actually needs.
    private var statusTextSlotWidth: CGFloat {
        guard hasAnySessions, !statusPhrase.isEmpty else { return 0 }
        // Matches the invisible sizing Text in headerRow — 4 dots, not 3,
        // so the width budget tracks the actual render. See comment on
        // the ZStack sizing trick for why we use 4.
        let fullText = statusPhrase + "...."
        let font = NSFont.systemFont(ofSize: 10, weight: .black)
        let size = (fullText as NSString).size(withAttributes: [.font: font])
        return ceil(size.width)
    }

    private var expansionWidth: CGFloat {
        let leftSlot = statusTextSlotWidth + 12 // +12 for leading padding
        guard leftSlot > 12 else { return 0 }

        let constellation = constellationSlotWidth()
        if constellation > 0 {
            // +12 trailing padding after the dot row
            return leftSlot + constellation + 12
        }
        return leftSlot
    }

    /// Pixel budget for the constellation area. Branches on displayMode
    /// because the static view uses narrower monospace characters vs the
    /// animated Ripple icons. Keep in sync with the view-side layout
    /// constants (`SessionConstellationView.iconSize/spacing/maxVisible`
    /// and `StaticConstellationView.charWidth/spacing/maxVisible`).
    private func constellationSlotWidth() -> CGFloat {
        let instances = sessionMonitor.instances
        let attentionCount = instances.filter {
            $0.needsAttention && !ackTracker.isAcknowledged($0.sessionId)
        }.count
        let runningCount = instances.filter {
            $0.phase == .processing || $0.phase == .compacting
        }.count
        let idleCount = instances.filter { $0.phase == .idle }.count

        let total = attentionCount + runningCount + idleCount
        guard total > 0 else { return 0 }

        switch displayMode {
        case .animated:
            let maxVisible = SessionConstellationView.maxVisible
            let slotCount = min(total, maxVisible)
            let iconSize = SessionConstellationView.iconSize
            var width = CGFloat(slotCount) * iconSize
            if slotCount > 1 {
                width += CGFloat(slotCount - 1) * SessionConstellationView.spacing
            }
            return width

        case .staticText:
            let maxVisible = StaticConstellationView.maxVisible
            let slotCount = min(total, maxVisible)
            let charWidth = StaticConstellationView.charWidth
            var width = CGFloat(slotCount) * charWidth
            if slotCount > 1 {
                width += CGFloat(slotCount - 1) * StaticConstellationView.spacing
            }
            return width
        }
    }

    private var notchSize: CGSize {
        switch viewModel.status {
        case .closed, .popping:
            return closedNotchSize
        case .opened:
            return viewModel.openedSize
        }
    }

    /// Width of the closed content (notch + any expansion)
    private var closedContentWidth: CGFloat {
        closedNotchSize.width + expansionWidth
    }

    // MARK: - Corner Radii

    private var topCornerRadius: CGFloat {
        viewModel.status == .opened
            ? cornerRadiusInsets.opened.top
            : cornerRadiusInsets.closed.top
    }

    private var bottomCornerRadius: CGFloat {
        if viewModel.status == .opened {
            return cornerRadiusInsets.opened.bottom
        }
        switch morphingShape {
        case .rest:    return cornerRadiusInsets.closed.bottom
        case .runway:  return cornerRadiusInsets.closed.bottom + 2
        case .bubble:  return cornerRadiusInsets.closed.bottom + 4
        }
    }

    private var currentNotchShape: NotchShape {
        NotchShape(
            topCornerRadius: topCornerRadius,
            bottomCornerRadius: bottomCornerRadius
        )
    }

    // Animation springs
    private let openAnimation = Animation.spring(response: 0.42, dampingFraction: 0.8, blendDuration: 0)
    private let closeAnimation = Animation.spring(response: 0.45, dampingFraction: 1.0, blendDuration: 0)

    // MARK: - Body

    var body: some View {
        ZStack(alignment: .top) {
            // Outer container does NOT receive hits - only the notch content does
            VStack(spacing: 0) {
                notchLayout
                    .frame(
                        maxWidth: viewModel.status == .opened ? notchSize.width : nil,
                        alignment: .top
                    )
                    .padding(
                        .horizontal,
                        viewModel.status == .opened
                            ? cornerRadiusInsets.opened.top
                            : cornerRadiusInsets.closed.bottom
                    )
                    .padding([.horizontal, .bottom], viewModel.status == .opened ? 12 : 0)
                    .background(.black)
                    .clipShape(currentNotchShape)
                    .overlay(alignment: .top) {
                        Rectangle()
                            .fill(.black)
                            .frame(height: 1)
                            .padding(.horizontal, topCornerRadius)
                    }
                    .shadow(
                        color: (viewModel.status == .opened || isHovering) ? .black.opacity(0.7) : .clear,
                        radius: 6
                    )
                    .overlay(alignment: .bottom) {
                        // Light strip only renders under .animated mode: it's
                        // another repeatForever CA subtree, which the static
                        // mode exists specifically to avoid.
                        if viewModel.status != .opened && hasAnySessions
                           && !pauseController.isPaused && displayMode == .animated {
                            StatusLightStrip(sessions: sessionMonitor.instances)
                                .offset(y: 5)
                                .transition(.opacity)
                        }
                    }
                    .frame(
                        maxWidth: viewModel.status == .opened ? notchSize.width : nil,
                        maxHeight: viewModel.status == .opened ? notchSize.height : nil,
                        alignment: .top
                    )
                    .animation(viewModel.status == .opened ? openAnimation : closeAnimation, value: viewModel.status)
                    .animation(openAnimation, value: notchSize) // Animate container size changes between content types
                    .animation(.smooth, value: activityCoordinator.expandingActivity)
                    .animation(.smooth, value: hasAttention)
                    .animation(.smooth, value: attentionSessions.count)
                    .animation(.smooth(duration: 0.6), value: morphingShape)
                    .contentShape(Rectangle())
                    .onHover { hovering in
                        withAnimation(.spring(response: 0.38, dampingFraction: 0.8)) {
                            isHovering = hovering
                        }
                    }
                    .onTapGesture {
                        if viewModel.status != .opened {
                            viewModel.notchOpen(reason: .click)
                        }
                    }
            }
        }
        .opacity(isVisible ? 1 : 0)
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .top)
        .preferredColorScheme(.dark)
        .onAppear {
            sessionMonitor.startMonitoring()
            // On non-notched devices, keep visible so users have a target to interact with
            if !viewModel.hasPhysicalNotch {
                isVisible = true
            }
        }
        .onChange(of: viewModel.status) { oldStatus, newStatus in
            handleStatusChange(from: oldStatus, to: newStatus)
        }
        .onChange(of: sessionMonitor.instances) { _, instances in
            handleProcessingChange()
            handleWaitingForInputChange(instances)
            refreshStatusPhrase()
        }
        .onChange(of: statusTextPreset) { _, newPreset in
            // User changed the Status preset — update the displayed text
            // immediately without waiting for the next session event.
            guard isAnyProcessing else { return }
            if newPreset.isEmpty {
                let hour = Calendar.current.component(.hour, from: Date())
                let count = sessionMonitor.instances.count
                statusPhrase = StatusPhrases.smartWorking(hour: hour, sessionCount: count)
            } else {
                statusPhrase = newPreset
            }
        }
        .onChange(of: primaryStatusPhase) { oldPhase, newPhase in
            if oldPhase == .processing,
               newPhase == .waitingForInput || newPhase == .idle {
                textCelebrationUntil = Date().addingTimeInterval(1.2)
            }
        }
        .onReceive(Timer.publish(every: 0.5, on: .main, in: .common).autoconnect()) { _ in
            // 仅在有会话处于 processing 时滚动 "…" — 没在牛马就别
            // 强制重建父 body 节省 CPU。
            guard isAnyProcessing else { return }
            dotCount = (dotCount + 1) % 4
        }
    }

    private func refreshStatusPhrase() {
        let nowProcessing = isAnyProcessing
        let hour = Calendar.current.component(.hour, from: Date())
        let count = sessionMonitor.instances.count

        // Working phrase respects the user's Status preset:
        //   - empty string → random (StatusPhrases.smartWorking)
        //   - otherwise    → fixed to the preset
        func workingPhrase() -> String {
            statusTextPreset.isEmpty
                ? StatusPhrases.smartWorking(hour: hour, sessionCount: count)
                : statusTextPreset
        }

        if nowProcessing != wasProcessing {
            wasProcessing = nowProcessing
            statusPhrase = nowProcessing
                ? workingPhrase()
                : StatusPhrases.smartIdle(hour: hour)
        } else if statusPhrase.isEmpty && hasAnySessions {
            statusPhrase = nowProcessing
                ? workingPhrase()
                : StatusPhrases.smartIdle(hour: hour)
        }
    }

    // MARK: - Notch Layout

    private var isProcessing: Bool {
        isAnyProcessing
    }

    /// Whether to show the expanded closed state (any sessions exist).
    private var showClosedActivity: Bool {
        isProcessing || hasAttention || hasAnySessions
    }

    @ViewBuilder
    private var notchLayout: some View {
        VStack(alignment: .leading, spacing: 0) {
            // Header row - always present, contains crab and spinner that persist across states
            headerRow
                .frame(height: max(24, closedNotchSize.height))
                .background(viewModel.status == .opened
                    ? Color(white: 0.05) // Subtle layer separation in opened state
                    : Color.clear
                )

            // Main content only when opened
            if viewModel.status == .opened {
                contentView
                    .frame(width: notchSize.width - 24) // Fixed width to prevent reflow
                    .transition(
                        .asymmetric(
                            insertion: .scale(scale: 0.8, anchor: .top)
                                .combined(with: .opacity)
                                .animation(.smooth(duration: 0.35)),
                            removal: .opacity.animation(.easeOut(duration: 0.15))
                        )
                    )
            }
        }
    }

    // MARK: - Header Row (persists across states)

    @ViewBuilder
    private var headerRow: some View {
        HStack(spacing: 0) {
            // Left side - animated status text.
            //
            // Sizing trick: an invisible "statusPhrase + ...." (4 dots, one
            // more than the max visible cycle) forms the width floor via
            // fixedSize, so the visible text can freely animate 0–3 dots
            // without the layout hunting its own width. The extra dot is
            // cheap headroom — it guarantees the 3-dot animation phase
            // renders fully even when font metrics are slightly off.
            if showClosedActivity && viewModel.status != .opened && !pauseController.isPaused {
                ZStack(alignment: .leading) {
                    Text(statusPhrase + "....")
                        .font(.system(size: 10, weight: .black))
                        .opacity(0)
                    switch displayMode {
                    case .animated:
                        AnimatedStatusText(
                            phrase: statusPhrase,
                            dotCount: dotCount,
                            color: statusTextColor,
                            celebrationUntil: textCelebrationUntil
                        )
                    case .staticText:
                        StaticStatusText(phrase: statusPhrase, color: statusTextColor)
                    }
                }
                .lineLimit(1)
                .fixedSize()
                .padding(.leading, 8)
                .padding(.trailing, 6)
            }

            // Center content
            if viewModel.status == .opened {
                // Opened: show header content
                openedHeaderContent
            } else if !showClosedActivity {
                // Closed without activity: empty space
                Rectangle()
                    .fill(.clear)
                    .frame(width: closedNotchSize.width - 20)
            } else {
                // Closed with activity: fixed-width black spacer covering
                // the physical notch cutout. Must be a rigid Rectangle and
                // NOT a Spacer — a Spacer inside an unconstrained HStack
                // greedily grows to fill the full window width, which on
                // a 1500+pt screen means the island eats every running
                // app's tab bar. Been there; don't do it again.
                //
                // The fixed width = physical notch width - top corner
                // radius, which is exactly the interior of the notch shape.
                // Any content on the left (status text) or right (session
                // constellation) extends outside the physical cutout onto
                // the menu bar strip, which is rendered black by the same
                // background modifier.
                Rectangle()
                    .fill(.black)
                    .frame(width: closedNotchSize.width - cornerRadiusInsets.closed.top)
            }

            // Right side — Session Constellation (closed state only).
            //
            // Replaces the old "either N checkmarks OR a progress bar"
            // binary with a unified dot row: ✓ for attention, ● for running
            // (breathing), ○ for idle. Lets the user see the full fleet at
            // a glance, not just "something is happening" vs "someone wants
            // input". See SessionConstellationView for layout details.
            if showClosedActivity && viewModel.status != .opened && !pauseController.isPaused {
                switch displayMode {
                case .animated:
                    SessionConstellationView(
                        sessions: sessionMonitor.instances,
                        unacknowledgedAttentionIds: unacknowledgedAttentionIds
                    )
                    .padding(.trailing, 8)
                case .staticText:
                    StaticConstellationView(
                        sessions: sessionMonitor.instances,
                        unacknowledgedAttentionIds: unacknowledgedAttentionIds
                    )
                    .padding(.trailing, 8)
                }
            }
        }
        .frame(height: closedNotchSize.height)
    }

    /// Set of session IDs in an attention phase that the user has not yet
    /// dismissed via acknowledgment. Computed once so both the expansion
    /// width budget and the SessionConstellationView see a consistent view.
    private var unacknowledgedAttentionIds: Set<String> {
        Set(
            sessionMonitor.instances
                .filter { $0.needsAttention && !ackTracker.isAcknowledged($0.sessionId) }
                .map(\.sessionId)
        )
    }

    // MARK: - Opened Header Content

    @ViewBuilder
    private var openedHeaderContent: some View {
        HStack(spacing: 12) {
            if hasAnySessions, !statusPhrase.isEmpty {
                AnimatedStatusText(
                    phrase: statusPhrase,
                    dotCount: dotCount,
                    color: statusTextColor,
                    celebrationUntil: textCelebrationUntil
                )
                .lineLimit(1)
                .padding(.leading, 8)
            } else {
                ClaudeCrabIcon(size: 14)
                    .padding(.leading, 8)
            }

            Spacer()

            // Menu toggle — shows gearshape when idle, progress bar when processing
            Button {
                withAnimation(.spring(response: 0.3, dampingFraction: 0.8)) {
                    viewModel.toggleMenu()
                    if viewModel.contentType == .menu {
                        updateManager.markUpdateSeen()
                    }
                }
            } label: {
                ZStack(alignment: .topTrailing) {
                    if isProcessing {
                        HeaderProgressBar(tint: TerminalColors.prompt)
                            .frame(width: 16, height: 3)
                            .frame(width: 22, height: 22)
                            .contentShape(Rectangle())
                            .transition(.opacity)
                    } else {
                        Image(systemName: "gearshape")
                            .font(.system(size: 12, weight: .medium))
                            .foregroundColor(.white.opacity(0.5))
                            .frame(width: 22, height: 22)
                            .contentShape(Rectangle())
                            .transition(.opacity)
                    }

                    // Green dot for unseen update
                    if updateManager.hasUnseenUpdate && viewModel.contentType != .menu {
                        Circle()
                            .fill(TerminalColors.green)
                            .frame(width: 6, height: 6)
                            .offset(x: -2, y: 2)
                    }
                }
                .animation(.easeInOut(duration: 0.2), value: isProcessing)
            }
            .buttonStyle(.plain)
        }
    }

    // MARK: - Content View (Opened State)

    @ViewBuilder
    private var contentView: some View {
        Group {
            switch viewModel.contentType {
            case .instances:
                ClaudeInstancesView(
                    sessionMonitor: sessionMonitor,
                    viewModel: viewModel
                )
            case .menu:
                NotchMenuView(viewModel: viewModel)
            case .chat(let session):
                ChatView(
                    sessionId: session.sessionId,
                    initialSession: session,
                    sessionMonitor: sessionMonitor,
                    viewModel: viewModel
                )
            }
        }
        .frame(width: notchSize.width - 24) // Fixed width to prevent text reflow
        // Removed .id() - was causing view recreation and performance issues
    }

    // MARK: - Event Handlers

    private func handleProcessingChange() {
        if hasAttention {
            // Attention (completion or ask) has priority over processing,
            // so checkmarks are visible even if another concurrent session
            // is still running tool calls.
            activityCoordinator.hideActivity()
            isVisible = true
        } else if isAnyProcessing {
            // Show claude activity when processing.
            activityCoordinator.showActivity(type: .claude)
            isVisible = true
        } else {
            // Hide activity when done
            activityCoordinator.hideActivity()

            // Delay hiding the notch until animation completes
            // Don't hide on non-notched devices - users need a visible target
            if viewModel.status == .closed && viewModel.hasPhysicalNotch {
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) {
                    if !isAnyProcessing && !hasAttention && viewModel.status == .closed {
                        isVisible = false
                    }
                }
            }
        }
    }

    private func handleStatusChange(from oldStatus: NotchStatus, to newStatus: NotchStatus) {
        switch newStatus {
        case .opened, .popping:
            isVisible = true
        case .closed:
            // Don't hide on non-notched devices - users need a visible target
            guard viewModel.hasPhysicalNotch else { return }
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.35) {
                if viewModel.status == .closed && !isAnyProcessing && !hasAttention && !activityCoordinator.expandingActivity.show {
                    isVisible = false
                }
            }
        }
    }

    /// Play notification sound when a session newly enters waitingForInput,
    /// and reconcile the acknowledgment tracker so stale acks are cleared.
    /// Sound only — no bounce, no auto-expand. Per the "no self-enlarge"
    /// refactor, visual feedback is limited to the checkmark appearing.
    private func handleWaitingForInputChange(_ instances: [SessionState]) {
        // Reconcile ack tracker: drop dismissed entries whose sessions are
        // no longer in any attention state. When such a session later enters
        // .waitingForInput again, a fresh checkmark appears.
        let attentionIds = Set(instances.filter { $0.needsAttention }.map { $0.sessionId })
        ackTracker.reconcile(keeping: attentionIds)

        let waitingForInputSessions = instances.filter { $0.phase == .waitingForInput }
        let currentIds = Set(waitingForInputSessions.map { $0.stableId })
        let newWaitingIds = currentIds.subtracting(previousWaitingForInputIds)

        if !newWaitingIds.isEmpty,
           let soundName = AppSettings.notificationSound.soundName {
            let newlyWaitingSessions = waitingForInputSessions.filter { newWaitingIds.contains($0.stableId) }
            Task {
                let shouldPlaySound = await shouldPlayNotificationSound(for: newlyWaitingSessions)
                if shouldPlaySound {
                    await MainActor.run {
                        NSSound(named: soundName)?.play()
                    }
                }
            }
        }

        previousWaitingForInputIds = currentIds
    }

    /// Determine if notification sound should play for the given sessions
    /// Returns true if ANY session is not actively focused
    private func shouldPlayNotificationSound(for sessions: [SessionState]) async -> Bool {
        for session in sessions {
            guard let pid = session.pid else {
                // No PID means we can't check focus, assume not focused
                return true
            }

            let isFocused = await TerminalVisibilityDetector.isSessionFocused(sessionPid: pid)
            if !isFocused {
                return true
            }
        }

        return false
    }
}

// MARK: - Static Status Text

/// Zero-animation counterpart to AnimatedStatusText. Plain colored text
/// with a single subtle glow shadow so it stays readable against the
/// black notch; no breath, no dot roll, no celebration pulse.
private struct StaticStatusText: View {
    let phrase: String
    let color: Color

    var body: some View {
        Text(phrase)
            .font(.system(size: 10, weight: .black))
            .foregroundColor(color)
            .shadow(color: color.opacity(0.4), radius: 2)
    }
}

// MARK: - Animated Status Text

/// Status phrase with breath opacity, phase-color tint, soft glow, and
/// a one-shot pulse when long-work completion is celebrated.
private struct AnimatedStatusText: View {
    let phrase: String
    let dotCount: Int
    let color: Color
    let celebrationUntil: Date?

    @State private var breath: Double = 0
    @State private var celebScale: Double = 1.0

    var body: some View {
        Text(phrase + String(repeating: ".", count: dotCount))
            .font(.system(size: 10, weight: .black))
            .foregroundColor(color)
            .shadow(color: color.opacity(0.9), radius: 4)
            .shadow(color: color.opacity(0.5), radius: 8)
            .opacity(0.6 + breath * 0.4)
            .scaleEffect(celebScale)
            .animation(.easeOut(duration: 0.3), value: color)
            .onAppear {
                withAnimation(.easeInOut(duration: 1.0).repeatForever(autoreverses: true)) {
                    breath = 1.0
                }
            }
            .onChange(of: celebrationUntil) { _, newValue in
                guard newValue != nil else { return }
                withAnimation(.spring(response: 0.3, dampingFraction: 0.5)) {
                    celebScale = 1.22
                }
                // .delay 走 SwiftUI/CA 动画链，view 销毁时 CA 自动取消，
                // 比 asyncAfter 的裸闭包更安全
                withAnimation(.easeOut(duration: 0.9).delay(0.3)) {
                    celebScale = 1.0
                }
            }
    }
}
