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
    @State private var previousWaitingForInputIds: Set<String> = []
    @State private var isVisible: Bool = false
    @State private var isHovering: Bool = false
    @State private var statusPhrase: String = ""
    @State private var dotCount: Int = 0
    @State private var wasProcessing: Bool = false

    @Namespace private var activityNamespace

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

    // MARK: - Sizing

    private var closedNotchSize: CGSize {
        CGSize(
            width: viewModel.deviceNotchRect.width,
            height: viewModel.deviceNotchRect.height
        )
    }

    /// Extra width for the compact header's right-side indicators.
    ///
    /// Layout: base slot for the crab (left) + dynamic slot for N checkmarks
    /// (right). Each checkmark is `checkmarkIconSize` wide with
    /// `checkmarkSpacing` between; the block also has its own side padding.
    /// When there are no attention sessions we fall back to a fixed-width
    /// slot for the processing progress bar (if processing).
    /// Measured width for the current status phrase + "..." (max dots).
    private var statusTextSlotWidth: CGFloat {
        guard hasAnySessions, !statusPhrase.isEmpty else { return 0 }
        let fullText = statusPhrase + "..."
        let font = NSFont.systemFont(ofSize: 9, weight: .semibold)
        let size = (fullText as NSString).size(withAttributes: [.font: font])
        return ceil(size.width)
    }

    private var expansionWidth: CGFloat {
        let leftSlot = statusTextSlotWidth + 12 // +12 for leading padding
        guard leftSlot > 12 else { return 0 }

        if hasAttention {
            let count = CGFloat(attentionSessions.count)
            let checkmarksWidth = count * Self.checkmarkIconSize
                + max(0, count - 1) * Self.checkmarkSpacing
                + Self.checkmarkBlockPadding
            return leftSlot + checkmarksWidth
        }

        if isProcessing {
            let rightSlot = max(0, closedNotchSize.height - 12) + 10
            return leftSlot + rightSlot
        }

        return leftSlot
    }

    /// Layout constants for the multi-checkmark indicator.
    /// Tuned for the Dynamic Island aesthetic: thin SF Symbol checkmark
    /// glyphs (no filled circle background), small size, tight spacing.
    /// The filled-circle variant looked like approval badges — too loud
    /// against the black notch.
    private static let checkmarkIconSize: CGFloat = 11
    private static let checkmarkSpacing: CGFloat = 5
    private static let checkmarkBlockPadding: CGFloat = 10

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
        viewModel.status == .opened
            ? cornerRadiusInsets.opened.bottom
            : cornerRadiusInsets.closed.bottom
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
        .onReceive(Timer.publish(every: 0.5, on: .main, in: .common).autoconnect()) { _ in
            dotCount = (dotCount + 1) % 4
        }
    }

    private func refreshStatusPhrase() {
        let nowProcessing = isAnyProcessing
        let hour = Calendar.current.component(.hour, from: Date())
        let count = sessionMonitor.instances.count

        if nowProcessing != wasProcessing {
            wasProcessing = nowProcessing
            statusPhrase = nowProcessing
                ? StatusPhrases.smartWorking(hour: hour, sessionCount: count)
                : StatusPhrases.smartIdle(hour: hour)
        } else if statusPhrase.isEmpty && hasAnySessions {
            statusPhrase = nowProcessing
                ? StatusPhrases.smartWorking(hour: hour, sessionCount: count)
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
            // ZStack with hidden max-width text locks the width so dot animation
            // doesn't cause jitter, and .fixedSize() prevents truncation.
            if showClosedActivity && viewModel.status != .opened {
                ZStack(alignment: .leading) {
                    Text(statusPhrase + "...")
                        .font(.system(size: 9, weight: .semibold))
                        .opacity(0)
                    Text(statusPhrase + String(repeating: ".", count: dotCount))
                        .font(.system(size: 9, weight: .semibold))
                        .foregroundColor(Color(red: 0.85, green: 0.47, blue: 0.34))
                }
                .lineLimit(1)
                .fixedSize()
                .padding(.leading, 8)
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
                // Closed with activity: black spacer. No bounce — the island
                // never animates its own width beyond what the indicators need.
                Rectangle()
                    .fill(.black)
                    .frame(width: closedNotchSize.width - cornerRadiusInsets.closed.top)
            }

            // Right side - only in closed state.
            if showClosedActivity && viewModel.status != .opened {
                if hasAttention {
                    HStack(spacing: Self.checkmarkSpacing) {
                        ForEach(attentionSessions, id: \.stableId) { _ in
                            Image(systemName: "checkmark")
                                .font(.system(
                                    size: Self.checkmarkIconSize,
                                    weight: .semibold
                                ))
                                .foregroundColor(TerminalColors.green)
                        }
                    }
                    .padding(.horizontal, Self.checkmarkBlockPadding / 2)
                } else if isProcessing {
                    // Customization: replaced ugly unicode-character spinner
                    // with a looping progress bar (Claude orange).
                    HeaderProgressBar(tint: Color(red: 0.85, green: 0.47, blue: 0.34))
                        .matchedGeometryEffect(id: "spinner", in: activityNamespace, isSource: showClosedActivity)
                        .frame(width: 18, height: 3)
                        .frame(width: viewModel.status == .opened ? 20 : sideWidth)
                }
            }
        }
        .frame(height: closedNotchSize.height)
    }

    private var sideWidth: CGFloat {
        max(0, closedNotchSize.height - 12) + 10
    }

    // MARK: - Opened Header Content

    @ViewBuilder
    private var openedHeaderContent: some View {
        HStack(spacing: 12) {
            if hasAnySessions, !statusPhrase.isEmpty {
                Text(statusPhrase + String(repeating: ".", count: dotCount))
                    .font(.system(size: 9, weight: .semibold))
                    .foregroundColor(Color(red: 0.85, green: 0.47, blue: 0.34))
                    .lineLimit(1)
                    .padding(.leading, 8)
            } else {
                ClaudeCrabIcon(size: 14)
                    .padding(.leading, 8)
            }

            Spacer()

            // Menu toggle
            Button {
                withAnimation(.spring(response: 0.3, dampingFraction: 0.8)) {
                    viewModel.toggleMenu()
                    if viewModel.contentType == .menu {
                        updateManager.markUpdateSeen()
                    }
                }
            } label: {
                ZStack(alignment: .topTrailing) {
                    // Customization: looping progress bar as the menu button's
                    // visual. Click behavior preserved by the outer Button.
                    HeaderProgressBar(
                        tint: isProcessing
                            ? Color(red: 0.85, green: 0.47, blue: 0.34)
                            : .white
                    )
                        .frame(width: 16, height: 3)
                        .frame(width: 22, height: 22)
                        .contentShape(Rectangle())

                    // Green dot for unseen update
                    if updateManager.hasUnseenUpdate && viewModel.contentType != .menu {
                        Circle()
                            .fill(TerminalColors.green)
                            .frame(width: 6, height: 6)
                            .offset(x: -2, y: 2)
                    }
                }
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
