//
//  EventMonitors.swift
//  ClaudeIsland
//
//  Singleton that aggregates all event monitors
//

import AppKit
import Combine

class EventMonitors {
    static let shared = EventMonitors()

    // 只保留 mouseDown —— 用于 click outside 关闭展开的 notch。
    // 历史上这里还订阅了 .mouseMoved / .mouseDragged 用于 hover 检测，
    // 但 hover 视觉反馈实际由 SwiftUI `.onHover`（内部 NSTrackingArea）处理，
    // 全局 mouseMoved 事件流每次都穿过 WindowServer → app，在 sample 中
    // 占 14% 主线程 CPU。删除后节省显著 CPU。
    let mouseDown = PassthroughSubject<NSEvent, Never>()

    private var mouseDownMonitor: EventMonitor?

    private init() {
        setupMonitors()
    }

    private func setupMonitors() {
        mouseDownMonitor = EventMonitor(mask: .leftMouseDown) { [weak self] event in
            self?.mouseDown.send(event)
        }
        mouseDownMonitor?.start()
    }

    deinit {
        mouseDownMonitor?.stop()
    }
}
