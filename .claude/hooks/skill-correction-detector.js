#!/usr/bin/env node
/**
 * Skill Correction Detector — UserPromptSubmit Hook
 *
 * Detects user correction signals (e.g., "不对", "重来") in prompts
 * and logs them with the most recently activated skills for observatory analysis.
 *
 * Hook interface:
 * - stdin: JSON with prompt, session_id
 * - stdout: unused (no injection into Claude)
 * - stderr: silent
 * - exit: always 0
 */

const fs = require('fs');
const path = require('path');
const { readStdin } = require('../scripts/lib/utils');

// Correction keywords — ordered by specificity (longer phrases first)
const CORRECTION_KEYWORDS = [
  '不是我要的', '不要这样', '换个方式', '不是这个意思',
  '不对', '错了', '重来', '重新来', '搞错了', '弄错了',
  '不行', '不好', '太差', '重做',
];

function getObservatoryDir(subdir) {
  const projectDir = process.env.CLAUDE_PROJECT_DIR || process.cwd();
  const dir = path.join(projectDir, '.claude', 'observatory', subdir);
  try { fs.mkdirSync(dir, { recursive: true }); } catch { /* ignore */ }
  return dir;
}

function getRecentActivations(date) {
  const activationsDir = getObservatoryDir('activations');
  const filePath = path.join(activationsDir, `${date}.jsonl`);
  try {
    const lines = fs.readFileSync(filePath, 'utf8').trim().split('\n');
    if (lines.length === 0) return [];
    const last = JSON.parse(lines[lines.length - 1]);
    const final = last.final || [];
    // final may be space-separated string from activation-prompt.sh
    return Array.isArray(final) ? final : String(final).split(' ').filter(Boolean);
  } catch {
    return [];
  }
}

async function main() {
  const input = await readStdin();
  const prompt = input.prompt || '';

  if (!prompt || prompt.length < 2) {
    process.exit(0);
  }

  // Skip system/task notifications
  if (prompt.includes('<task-notification>')) {
    process.exit(0);
  }

  // Detect correction keywords (check first 50 chars for efficiency)
  const checkRange = prompt.substring(0, 50);
  let matchedKeyword = null;
  for (const kw of CORRECTION_KEYWORDS) {
    if (checkRange.includes(kw)) {
      matchedKeyword = kw;
      break;
    }
  }

  if (!matchedKeyword) {
    process.exit(0);
  }

  const sessionId = input.session_id || process.env.CLAUDE_SESSION_ID || 'unknown';
  const now = new Date();
  // Use local timezone to match shell `date +%Y-%m-%d` in activation-prompt.sh
  const pad = (n) => String(n).padStart(2, '0');
  const date = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
  const ts = `${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`;

  const recentSkills = getRecentActivations(date);

  const record = {
    ts,
    session_id: sessionId,
    correction_keyword: matchedKeyword,
    recent_skills: recentSkills,
    prompt_preview: prompt.substring(0, 30),
  };

  const correctionsDir = getObservatoryDir('corrections');
  const filePath = path.join(correctionsDir, `${date}.jsonl`);

  try {
    fs.appendFileSync(filePath, JSON.stringify(record) + '\n');
  } catch { /* silent */ }

  process.exit(0);
}

main().catch(() => process.exit(0));
