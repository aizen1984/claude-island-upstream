#!/usr/bin/env node
/**
 * Plan Context Inject — PostToolUse Hook for Edit|Write
 *
 * 每 5 次 Edit/Write 后注入 plan 任务提醒 + spec 目标，防止长任务目标漂移。
 * 仅在 Ralph Loop 激活时生效。
 *
 * 设计依据（E1-R，经对抗验证修正）：
 *   - PostToolUse 而非 PreToolUse，避免与 tdd-guard/code-quality-guard 的 decision 冲突
 *   - 每 5 次触发一次，避免上下文膨胀
 *   - 极简一行提醒（~20 tokens），非完整 plan 摘要
 *
 * 挂载点: PostToolUse(Edit|Write)
 * @assumption 模型在长任务中会偏离原始计划目标
 */

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { readStdin, log } = require('../scripts/lib/utils');

const INJECT_INTERVAL = 5;

function getProjectHash() {
  const projectDir = process.env.CLAUDE_PROJECT_DIR || process.cwd();
  return crypto.createHash('md5').update(projectDir).digest('hex').slice(0, 8);
}

function getRalphPrefix() {
  const os = require('os');
  const hash = getProjectHash();
  const sessionId = process.env.CLAUDE_SESSION_ID || '';
  if (!sessionId) return '';
  const anchor = path.join(os.tmpdir(), `stark-ralph-${hash}-${sessionId}-current`);
  try {
    const uuid = fs.readFileSync(anchor, 'utf8').trim();
    return path.join(os.tmpdir(), `stark-ralph-${hash}-${uuid}`);
  } catch {
    return '';
  }
}

function isRalphActive(prefix) {
  if (!prefix) return false;
  try {
    return fs.existsSync(`${prefix}-active`);
  } catch {
    return false;
  }
}

function getPlanPath(prefix) {
  try {
    return fs.readFileSync(`${prefix}-plan`, 'utf8').trim();
  } catch {
    return '';
  }
}

function getCounterPath() {
  const hash = getProjectHash();
  return path.join(require('os').tmpdir(), `stark-plan-inject-${hash}.json`);
}

function loadCounter(filePath) {
  try {
    return JSON.parse(fs.readFileSync(filePath, 'utf8'));
  } catch {
    return { count: 0 };
  }
}

function saveCounter(filePath, data) {
  fs.writeFileSync(filePath, JSON.stringify(data));
}

/**
 * 从 plan.md 提取当前执行中的任务（🔄 标记的行）
 * 如果没有 🔄，提取第一个 ⬜ 任务
 * 返回极简一行文本
 */
function extractCurrentTask(planPath) {
  try {
    const content = fs.readFileSync(planPath, 'utf8');
    const lines = content.split('\n');

    // 统计进度
    const total = lines.filter(l => /[⬜🔄✅]/.test(l)).length;
    const done = lines.filter(l => /✅/.test(l)).length;

    // 找 🔄 或第一个 ⬜
    let currentTask = '';
    for (const line of lines) {
      if (line.includes('🔄')) {
        currentTask = line.replace(/^[\s\-*]*🔄\s*/, '').replace(/T\d+:\s*/, '').trim();
        break;
      }
    }
    if (!currentTask) {
      for (const line of lines) {
        if (line.includes('⬜')) {
          currentTask = line.replace(/^[\s\-*]*⬜\s*/, '').replace(/T\d+:\s*/, '').trim();
          break;
        }
      }
    }

    if (!currentTask) return null;

    // 截断过长的任务名
    if (currentTask.length > 60) {
      currentTask = currentTask.substring(0, 57) + '...';
    }

    // 追加 spec 目标（防漂移增强）
    const specPath = planPath.replace('plan.md', 'spec.md');
    try {
      const specContent = fs.readFileSync(specPath, 'utf8');
      const goalMatch = specContent.match(/\*\*(?:核心目标|目标|Goal)\*\*[:：]\s*(.+)/);
      if (goalMatch) {
        return `📌 当前任务 [${done}/${total}]: ${currentTask} | 🎯 ${goalMatch[1].trim().substring(0, 50)}`;
      }
    } catch {}

    return `📌 当前任务 [${done}/${total}]: ${currentTask}`;
  } catch {
    return null;
  }
}

async function main() {
  await readStdin();

  const ralphPrefix = getRalphPrefix();

  // 仅 Ralph 激活时生效
  if (!isRalphActive(ralphPrefix)) {
    process.exit(0);
  }

  const counterPath = getCounterPath();
  const counter = loadCounter(counterPath);
  counter.count++;
  saveCounter(counterPath, counter);

  // 每 INJECT_INTERVAL 次触发一次
  if (counter.count % INJECT_INTERVAL !== 0) {
    process.exit(0);
  }

  const planPath = getPlanPath(ralphPrefix);
  if (!planPath || !fs.existsSync(planPath)) {
    process.exit(0);
  }

  const taskHint = extractCurrentTask(planPath);
  if (!taskHint) {
    process.exit(0);
  }

  // 输出 additionalContext（PostToolUse 支持）
  const output = {
    hookSpecificOutput: {
      additionalContext: taskHint
    }
  };

  console.log(JSON.stringify(output));
}

main().catch(err => {
  log(`[plan-inject] Error: ${err.message}`);
  process.exit(0);
});
