#!/usr/bin/env python3
"""
Claude Island Hook
- Sends session state to ClaudeIsland.app via Unix socket
- For PermissionRequest: auto-allow (customization for this fork)
- For Stop: emits OSC 777 notification via the controlling TTY so the
  terminal emulator (Ghostty, iTerm2, ...) posts a native macOS
  notification whose click brings the user back to this exact tab.
"""
import json
import os
import socket
import subprocess
import sys

SOCKET_PATH = "/tmp/claude-island.sock"
TIMEOUT_SECONDS = 300  # 5 minutes for permission decisions


def get_tty():
    """Get the TTY of the Claude process (parent).

    Must return gracefully on any failure: Claude Code hooks cannot raise
    exceptions (would break the CLI) and cannot log to stdout (reserved for
    hook JSON protocol). Silent fallback chain is the intentional design.
    """
    # Get parent PID (Claude process)
    ppid = os.getppid()

    # Try to get TTY from ps command for the parent process
    try:
        result = subprocess.run(
            ["ps", "-p", str(ppid), "-o", "tty="],
            capture_output=True,
            text=True,
            timeout=2
        )
        tty = result.stdout.strip()
        if tty and tty != "??" and tty != "-":
            # ps returns just "ttys001", we need "/dev/ttys001"
            if not tty.startswith("/dev/"):
                tty = "/dev/" + tty
            return tty
    except (subprocess.SubprocessError, OSError, ValueError):
        pass

    # Fallback: try current process stdin/stdout
    try:
        return os.ttyname(sys.stdin.fileno())
    except (OSError, AttributeError):
        pass
    try:
        return os.ttyname(sys.stdout.fileno())
    except (OSError, AttributeError):
        pass
    return None


def send_event(state):
    """Send event to app, return response if any"""
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(TIMEOUT_SECONDS)
        sock.connect(SOCKET_PATH)
        sock.sendall(json.dumps(state).encode())

        # For permission requests, wait for response
        if state.get("status") == "waiting_for_approval":
            response = sock.recv(4096)
            sock.close()
            if response:
                return json.loads(response.decode())
        else:
            sock.close()

        return None
    except (socket.error, OSError, json.JSONDecodeError):
        return None


def emit_completion_notification(tty, cwd):
    """Emit OSC 777 notification via the controlling TTY.

    The terminal emulator (Ghostty, iTerm2, etc.) intercepts this escape
    sequence and posts a native macOS notification. Critically, the
    notification is "owned" by the terminal, so clicking it focuses the
    exact tab/window where this sequence was written — which is the
    same Ghostty tab running Claude Code. No extra focus/AX/yabai logic
    needed.

    Silent on any failure (TTY unavailable, write error, encoding issue).
    Never raises; Claude Code hooks must not crash the CLI.
    """
    if not tty:
        return
    try:
        # Derive a friendly session label from the working directory.
        # os.path.basename("/Users/x/IdeaProjects/ai/my_claude") -> "my_claude"
        session_label = os.path.basename(cwd) if cwd else "Claude"
        title = "✅ Claude 完成"
        body = f"{session_label} 等待你的输入"
        # OSC 777 notification format:
        #   ESC ] 777 ; notify ; <title> ; <body> BEL
        # Supported by Ghostty, iTerm2, kitty, xterm-derivatives, and others.
        osc_sequence = f"\033]777;notify;{title};{body}\a"
        with open(tty, "w") as tty_f:
            tty_f.write(osc_sequence)
    except (OSError, PermissionError, UnicodeError):
        pass


def main():
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(1)

    session_id = data.get("session_id", "unknown")
    event = data.get("hook_event_name", "")
    cwd = data.get("cwd", "")
    tool_input = data.get("tool_input", {})

    # Get process info
    claude_pid = os.getppid()
    tty = get_tty()

    # Build state object
    state = {
        "session_id": session_id,
        "cwd": cwd,
        "event": event,
        "pid": claude_pid,
        "tty": tty,
    }

    # Map events to status
    if event == "UserPromptSubmit":
        # User just sent a message - Claude is now processing
        state["status"] = "processing"

    elif event == "PreToolUse":
        state["status"] = "running_tool"
        state["tool"] = data.get("tool_name")
        state["tool_input"] = tool_input
        # Send tool_use_id to Swift for caching
        tool_use_id_from_event = data.get("tool_use_id")
        if tool_use_id_from_event:
            state["tool_use_id"] = tool_use_id_from_event

    elif event == "PostToolUse":
        state["status"] = "processing"
        state["tool"] = data.get("tool_name")
        state["tool_input"] = tool_input
        # Send tool_use_id so Swift can cancel the specific pending permission
        tool_use_id_from_event = data.get("tool_use_id")
        if tool_use_id_from_event:
            state["tool_use_id"] = tool_use_id_from_event

    elif event == "PermissionRequest":
        # Customization: auto-allow all permission requests.
        # Note: print() to stdout is the Claude Code hook protocol contract.
        auto_output = {
            "hookSpecificOutput": {
                "hookEventName": "PermissionRequest",
                "decision": {"behavior": "allow"},
            }
        }
        sys.stdout.write(json.dumps(auto_output) + "\n")
        sys.exit(0)

    elif event == "Notification":
        notification_type = data.get("notification_type")
        # Skip permission_prompt - PermissionRequest hook handles this with better info
        if notification_type == "permission_prompt":
            sys.exit(0)
        elif notification_type == "idle_prompt":
            state["status"] = "waiting_for_input"
        else:
            state["status"] = "notification"
        state["notification_type"] = notification_type
        state["message"] = data.get("message")

    elif event == "Stop":
        state["status"] = "waiting_for_input"
        # Customization: emit native macOS notification via terminal OSC 777.
        # The terminal (Ghostty) catches this and posts a notification that
        # the user can click to return directly to this Ghostty tab.
        emit_completion_notification(tty, cwd)

    elif event == "SubagentStop":
        # SubagentStop fires when a subagent completes - usually means back
        # to waiting. Do NOT emit completion notification here — it would
        # fire multiple times during a single user-facing task.
        state["status"] = "waiting_for_input"

    elif event == "SessionStart":
        # New session starts waiting for user input
        state["status"] = "waiting_for_input"

    elif event == "SessionEnd":
        state["status"] = "ended"

    elif event == "PreCompact":
        # Context is being compacted (manual or auto)
        state["status"] = "compacting"

    else:
        state["status"] = "unknown"

    # Send to socket (fire and forget for non-permission events)
    send_event(state)


if __name__ == "__main__":
    main()
