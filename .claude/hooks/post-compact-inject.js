#!/usr/bin/env node
/**
 * PostCompact Context Restore — 压缩后任务进度恢复
 *
 * 压缩（手动/自动）完成后，自动注入当前任务进度，防止长会话目标漂移。
 *
 * 设计依据（经对抗验证修正）：
 *   - CLAUDE.md 作为 system prompt 保留，无需重复注入核心规则
 *   - 真正丢失的是对话中建立的动态上下文（当前任务、中间结论）
 *   - PostCompact 频率极低（每会话 1-5 次），每次都注入，无需计数器
 *
 * 注入内容：
 *   - 当前执行中的任务（🔄）或下一个待执行任务（⬜）
 *   - 最近 3 个已完成任务（✅），帮助恢复"做到哪了"的上下文
 *   - 总进度统计
 *
 * 挂载点: PostCompact
 * @assumption 压缩后模型丢失关键路径信息（五文件位置等）
 */

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { readStdin, log } = require('../scripts/lib/utils');

function getProjectHash() {
  const projectDir = process.env.CLAUDE_PROJECT_DIR || process.cwd();
  return crypto.createHash('md5').update(projectDir).digest('hex').slice(0, 8);
}

/**
 * 查找 plan.md 路径（两种来源）：
 * 1. Ralph 活跃时从 Ralph 状态文件读取
 * 2. 非 Ralph 时从 STARK_SESSION_DIR 读取
 */
function findPlanPath() {
  const hash = getProjectHash();
  const sessionId = process.env.CLAUDE_SESSION_ID || '';

  // 尝试 Ralph 路径
  if (sessionId) {
    const anchor = path.join(require('os').tmpdir(), `stark-ralph-${hash}-${sessionId}-current`);
    try {
      const uuid = fs.readFileSync(anchor, 'utf8').trim();
      const prefix = path.join(require('os').tmpdir(), `stark-ralph-${hash}-${uuid}`);
      if (fs.existsSync(`${prefix}-active`)) {
        const planPath = fs.readFileSync(`${prefix}-plan`, 'utf8').trim();
        if (planPath && fs.existsSync(planPath)) return planPath;
      }
    } catch { /* ignore */ }
  }

  // 尝试 STARK_SESSION_DIR
  const sessionDir = process.env.STARK_SESSION_DIR;
  if (sessionDir) {
    const planPath = path.join(sessionDir, 'plan.md');
    if (fs.existsSync(planPath)) return planPath;
  }

  return '';
}

/**
 * 从 findings.md 提取最后 3 条发现/决策的首行
 * findings.md 条目以 `- ` 开头，取最后 3 条作为压缩后的决策恢复上下文
 */
function extractRecentFindings(findingsPath) {
  try {
    if (!fs.existsSync(findingsPath)) return [];
    const content = fs.readFileSync(findingsPath, 'utf8');
    const bullets = content.split('\n')
      .filter(l => /^- /.test(l.trim()))
      .map(l => l.trim().replace(/^- /, '').substring(0, 60));
    return bullets.slice(-3);
  } catch {
    return [];
  }
}

/**
 * 从 plan.md 提取任务进度摘要
 * 返回多行文本（当前任务 + 最近完成 + 进度统计 + 关键发现）
 */
function extractProgressSummary(planPath) {
  try {
    const content = fs.readFileSync(planPath, 'utf8');
    const lines = content.split('\n');

    // 收集所有任务行
    const taskLines = lines.filter(l => /[⬜🔄✅]/.test(l));
    const total = taskLines.length;
    const done = taskLines.filter(l => /✅/.test(l)).length;

    if (total === 0) return null;

    const parts = [];

    // 当前/下一个任务
    let current = taskLines.find(l => l.includes('🔄'));
    if (!current) current = taskLines.find(l => l.includes('⬜'));
    if (current) {
      const taskName = current
        .replace(/^[\s#\-*]*(⬜|🔄)\s*/, '')
        .replace(/T\d+:\s*/, '')
        .trim()
        .substring(0, 60);
      const icon = current.includes('🔄') ? '🔄' : '⬜';
      parts.push(`${icon} 当前: ${taskName}`);
    }

    // 最近 3 个已完成任务
    const completed = taskLines
      .filter(l => l.includes('✅'))
      .slice(-3)
      .map(l => l.replace(/^[\s#\-*]*✅\s*/, '').replace(/T\d+:\s*/, '').trim().substring(0, 40));
    if (completed.length > 0) {
      parts.push(`✅ 已完成: ${completed.join(' | ')}`);
    }

    // 进度
    parts.push(`📊 进度: ${done}/${total}`);

    // 关键发现（从 findings.md 提取，恢复"为什么走这条路"的决策上下文）
    const findingsPath = path.join(path.dirname(planPath), 'findings.md');
    const findings = extractRecentFindings(findingsPath);
    if (findings.length > 0) {
      parts.push(`📝 发现: ${findings.join(' | ')}`);
    }

    // 迭代循环模式状态恢复
    const sessionYamlPath = path.join(path.dirname(planPath), 'session.yaml');
    try {
      if (fs.existsSync(sessionYamlPath)) {
        const yamlContent = fs.readFileSync(sessionYamlPath, 'utf8');
        const iterModeMatch = yamlContent.match(/iteration_mode:\s*"?([^"\s]+)"?/);
        if (iterModeMatch && iterModeMatch[1] === 'evaluator-optimizer') {
          const currentMatch = yamlContent.match(/current:\s*(\d+)/);
          const iterNum = currentMatch ? currentMatch[1] : '?';
          // 尝试从 goal.md 读取目标摘要
          const goalPath = path.join(path.dirname(planPath), 'goal.md');
          let goalSummary = '';
          if (fs.existsSync(goalPath)) {
            const goalContent = fs.readFileSync(goalPath, 'utf8');
            const descMatch = goalContent.match(/## 目标描述\s*\n+(.+)/);
            if (descMatch) goalSummary = descMatch[1].substring(0, 80);
            // 最近评估分数
            const scoreMatches = [...goalContent.matchAll(/\*\*加权总分\*\*.*?(\d+\.?\d*)\/5/g)];
            const lastScore = scoreMatches.length > 0 ? scoreMatches[scoreMatches.length - 1][1] : null;
            if (lastScore) goalSummary += ` | 最近评分: ${lastScore}/5`;
          }
          parts.push(`🔄 迭代模式: 第 ${iterNum} 轮${goalSummary ? ' | 目标: ' + goalSummary : ''}`);
        }
      }
    } catch { /* ignore iteration state read errors */ }

    // CLAUDE.md 自维护提醒（Boris Tip: "Update your CLAUDE.md so you don't make that mistake again"）
    parts.push(`💡 如果本次会话中有被纠正的模式，建议更新 CLAUDE.md 或 MEMORY.md`);

    return `⚡ 上下文已压缩 — 任务进度恢复：\n${parts.join('\n')}`;
  } catch {
    return null;
  }
}

async function main() {
  await readStdin();

  const planPath = findPlanPath();
  let context = '';

  if (planPath) {
    const summary = extractProgressSummary(planPath);
    if (summary) {
      context = summary;
    }
  }

  // 无 plan.md 时仅注入自省提醒
  if (!context) {
    context = '⚡ 上下文已压缩。💡 如果本次会话中有被纠正的模式，建议更新 CLAUDE.md 或 MEMORY.md';
  }

  log(`[post-compact] 注入上下文恢复`);

  const output = {
    hookSpecificOutput: {
      additionalContext: context
    }
  };

  console.log(JSON.stringify(output));
}

main().catch(err => {
  log(`[post-compact] Error: ${err.message}`);
  process.exit(0);
});
