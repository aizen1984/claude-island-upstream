#!/usr/bin/env node
/**
 * Skill IO Tracker -- PostToolUse Hook for Read|Skill|Agent
 *
 * Silently tracks Skill execution IO (calls, reads, agent dispatches) into a
 * per-session /tmp JSON file. No stderr output during normal operation.
 *
 * Tracked data:
 * - Skill activations (name, args, timestamp)
 * - Resource reads: skill files / shared-rules / vault (path, range, lines)
 * - Agent dispatches (type, description, timestamp)
 * - Per-skill line counts with threshold warnings (stored as data, not output)
 *
 * Hook interface:
 * - stdin: JSON with tool_name, tool_input
 * - stdout: unused
 * - stderr: silent (no output during normal operation)
 * - exit: always 0 (PostToolUse cannot block)
 *
 * @assumption Needs external tracking to detect IO bloat (model has no self-awareness of it)
 */

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { readStdin } = require('../scripts/lib/utils');

// ============================================================================
// Configuration
// ============================================================================

const SKILL_DIR_MARKER = '.claude/skills/';
const AGENT_DIR_MARKER = '.claude/agents/';
const VAULT_DIR = '/Users/caochen/tools/shuhe-kb/';

const THRESHOLDS = {
  perSkill: [500, 1000],
  session: [3000],
};

// ============================================================================
// Persistence
// ============================================================================

function getObservatoryDir() {
  const projectDir = process.env.CLAUDE_PROJECT_DIR || process.cwd();
  const obsDir = path.join(projectDir, '.claude', 'observatory', 'sessions');
  try {
    fs.mkdirSync(obsDir, { recursive: true });
  } catch { /* ignore */ }
  return obsDir;
}

function getTrackerPath() {
  const sessionId = process.env.CLAUDE_SESSION_ID
    || extractSessionIdFromWorkspace()
    || 'default';
  const obsDir = getObservatoryDir();
  return path.join(obsDir, `${sessionId}.json`);
}

function extractSessionIdFromWorkspace() {
  const wsDir = process.env.STARK_SESSION_DIR || '';
  const match = wsDir.match(/sessions\/([^/]+)$/);
  return match ? match[1] : null;
}

function loadTracker(filePath) {
  const defaults = {
    skills: [],       // [{ name, args, ts }]
    reads: [],        // [{ path, range, lines, category, ts }]
    agents: [],       // [{ type, description, ts }]
    totalLines: 0,
    eventCount: 0,
    perSkill: {},     // { skillName: totalLines }
    skillSubfiles: {}, // { skillName: [list of sub-files read] } — 资源加载可观测
    lastActiveSkill: null,  // 最近激活的 skill 名称
    alertsFired: {},  // { "skill:skillName:500": true, "session:3000": true }
    warnings: [],     // [{ type, key, skill?, lines, threshold, ts }]
  };
  try {
    const data = JSON.parse(fs.readFileSync(filePath, 'utf8'));
    return { ...defaults, ...data };
  } catch {
    return defaults;
  }
}

function saveTracker(filePath, data) {
  fs.writeFileSync(filePath, JSON.stringify(data));
}

// ============================================================================
// File classification
// ============================================================================

/**
 * Classify a file path as skill-system resource, or null if unrelated.
 * @returns {{ category: string, shortPath: string } | null}
 */
function classifyRead(filePath) {
  const normalized = filePath.replace(/\\/g, '/');

  if (normalized.includes(SKILL_DIR_MARKER)) {
    const shortPath = normalized.substring(
      normalized.indexOf(SKILL_DIR_MARKER) + SKILL_DIR_MARKER.length
    );
    if (shortPath.startsWith('shared-rules/')) {
      return { category: 'shared-rule', shortPath };
    }
    return { category: 'skill', shortPath };
  }

  if (normalized.includes(AGENT_DIR_MARKER)) {
    const shortPath = normalized.substring(
      normalized.indexOf(AGENT_DIR_MARKER) + AGENT_DIR_MARKER.length
    );
    return { category: 'agent-def', shortPath };
  }

  if (normalized.startsWith(VAULT_DIR) || normalized.includes('/shuhe-kb/')) {
    const shortPath = normalized.startsWith(VAULT_DIR)
      ? normalized.substring(VAULT_DIR.length)
      : normalized.substring(normalized.indexOf('/shuhe-kb/') + '/shuhe-kb/'.length);
    return { category: 'vault', shortPath };
  }

  return null;
}

function formatRange(offset, limit) {
  if (!offset && !limit) return 'full';
  if (offset && limit) return `${offset}-${offset + limit}`;
  if (limit) return `first${limit}`;
  return `from${offset}`;
}

// ============================================================================
// Threshold detection (data-only, no output)
// ============================================================================

/**
 * Check line thresholds and append to tracker.warnings if newly crossed.
 * Each threshold fires at most once (tracked via alertsFired).
 */
function checkThresholds(tracker, skillName) {
  const ts = new Date().toISOString();

  // Per-skill thresholds
  const skillLines = tracker.perSkill[skillName] || 0;
  for (const threshold of THRESHOLDS.perSkill) {
    const key = `skill:${skillName}:${threshold}`;
    if (skillLines > threshold && !tracker.alertsFired[key]) {
      tracker.alertsFired[key] = true;
      tracker.warnings.push({
        type: 'perSkill',
        key,
        skill: skillName,
        lines: skillLines,
        threshold,
        ts,
      });
    }
  }

  // Session-total thresholds
  for (const threshold of THRESHOLDS.session) {
    const key = `session:${threshold}`;
    if (tracker.totalLines > threshold && !tracker.alertsFired[key]) {
      tracker.alertsFired[key] = true;
      tracker.warnings.push({
        type: 'session',
        key,
        lines: tracker.totalLines,
        threshold,
        ts,
      });
    }
  }
}

// ============================================================================
// Main
// ============================================================================

async function main() {
  const input = await readStdin();
  const toolName = input.tool_name;
  const toolInput = input.tool_input || {};

  const trackerPath = getTrackerPath();
  const tracker = loadTracker(trackerPath);
  const ts = new Date().toISOString().substring(11, 19);

  // --- Skill activation ---
  if (toolName === 'Skill') {
    const skillName = toolInput.skill || 'unknown';
    const args = toolInput.args || '';
    tracker.skills.push({ name: skillName, args, ts });
    tracker.lastActiveSkill = skillName;
    tracker.eventCount++;
    saveTracker(trackerPath, tracker);
    process.exit(0);
  }

  // --- Agent dispatch ---
  if (toolName === 'Agent') {
    const agentType = toolInput.subagent_type || 'general-purpose';
    const desc = toolInput.description || '';
    tracker.agents.push({ type: agentType, description: desc, ts });
    tracker.eventCount++;
    saveTracker(trackerPath, tracker);
    process.exit(0);
  }

  // --- Read tracking (skill-related files only) ---
  if (toolName === 'Read') {
    const filePath = toolInput.file_path || '';
    const classified = classifyRead(filePath);

    if (!classified) {
      process.exit(0);
    }

    const offset = toolInput.offset || 0;
    const limit = toolInput.limit || 0;
    const estimatedLines = limit || 200;

    tracker.reads.push({
      path: classified.shortPath,
      range: formatRange(offset, limit),
      lines: estimatedLines,
      category: classified.category,
      ts,
    });
    tracker.totalLines += estimatedLines;
    tracker.eventCount++;

    // Per-skill line aggregation + threshold check (skill category only)
    if (classified.category === 'skill') {
      const skillName = classified.shortPath.split('/')[0];
      tracker.perSkill[skillName] = (tracker.perSkill[skillName] || 0) + estimatedLines;
      checkThresholds(tracker, skillName);

      // 资源加载可观测：记录每个 skill 读了哪些子文件
      const subFile = classified.shortPath.substring(skillName.length + 1); // e.g. "patterns-async.md"
      if (subFile && subFile !== 'SKILL.md') {
        if (!tracker.skillSubfiles[skillName]) {
          tracker.skillSubfiles[skillName] = [];
        }
        if (!tracker.skillSubfiles[skillName].includes(subFile)) {
          tracker.skillSubfiles[skillName].push(subFile);
        }
      }
    }

    saveTracker(trackerPath, tracker);
    process.exit(0);
  }

  process.exit(0);
}

main().catch(() => {
  process.exit(0);
});
