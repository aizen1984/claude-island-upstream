#!/usr/bin/env node
/**
 * Cross-platform utilities for Claude Code hooks and scripts
 *
 * Adapted from: everything-claude-code/scripts/lib/utils.js
 *
 * Works on Windows, macOS, and Linux
 */

// ============================================================================
// I/O utilities
// ============================================================================

/**
 * Read JSON from stdin (for hook input)
 */
async function readStdin() {
  return new Promise((resolve) => {
    let data = '';
    let resolved = false;

    const done = (result) => {
      if (!resolved) {
        resolved = true;
        resolve(result);
      }
    };

    process.stdin.on('data', chunk => { data += chunk; });
    process.stdin.on('end', () => {
      try {
        done(JSON.parse(data));
      } catch {
        done({ _raw: data });
      }
    });

    // Handle case where stdin is empty/closed
    // If data has been received but end hasn't fired, extend the timeout
    const check = () => {
      if (resolved) return;
      if (data.length > 0) {
        // Data is arriving but end hasn't fired yet — wait longer
        setTimeout(check, 100);
      } else {
        // No data at all — stdin is likely empty/closed
        done({});
      }
    };
    setTimeout(check, 100);
  });
}

/**
 * Log to stderr (visible to user)
 */
function log(message) {
  console.error(message);
}

// ============================================================================
// Exports
// ============================================================================

module.exports = {
  readStdin,
  log
};
