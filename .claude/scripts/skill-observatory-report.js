#!/usr/bin/env node
/**
 * Skill Observatory Report — Analyzes skill usage data from .claude/observatory/
 *
 * Usage:
 *   node .claude/scripts/skill-observatory-report.js [--days 14] [--top 10] [--json]
 *
 * Reads:
 *   .claude/observatory/activations/*.jsonl   — skill activation records
 *   .claude/observatory/corrections/*.jsonl   — user correction records
 *   .claude/observatory/sessions/*.json       — per-session IO tracker data
 */

const fs = require('fs');
const path = require('path');

// stdout helper for CLI output
const print = (msg) => process.stdout.write(msg + '\n');

// ============================================================================
// CLI args
// ============================================================================

const args = process.argv.slice(2);
const daysBack = parseInt(getArg('--days', '14'));
const topN = parseInt(getArg('--top', '10'));
const jsonOutput = args.includes('--json');

function getArg(flag, defaultVal) {
  const idx = args.indexOf(flag);
  return idx >= 0 && args[idx + 1] ? args[idx + 1] : defaultVal;
}

// ============================================================================
// Data loading
// ============================================================================

const projectDir = process.env.CLAUDE_PROJECT_DIR || process.cwd();
const obsDir = path.join(projectDir, '.claude', 'observatory');

function dateRange(days) {
  const dates = [];
  for (let i = 0; i < days; i++) {
    const d = new Date();
    d.setDate(d.getDate() - i);
    const pad = (n) => String(n).padStart(2, '0');
    dates.push(`${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`);
  }
  return dates;
}

function loadJsonl(dir, dates) {
  const records = [];
  for (const date of dates) {
    const filePath = path.join(dir, `${date}.jsonl`);
    try {
      const lines = fs.readFileSync(filePath, 'utf8').trim().split('\n');
      for (const line of lines) {
        if (line) {
          try { records.push({ ...JSON.parse(line), _date: date }); } catch { /* skip malformed */ }
        }
      }
    } catch { /* file not found */ }
  }
  return records;
}

function loadSessions(dir) {
  const sessions = [];
  try {
    const files = fs.readdirSync(dir).filter(f => f.endsWith('.json'));
    for (const file of files) {
      try {
        const data = JSON.parse(fs.readFileSync(path.join(dir, file), 'utf8'));
        sessions.push({ ...data, _sessionId: file.replace('.json', '') });
      } catch { /* skip */ }
    }
  } catch { /* dir not found */ }
  return sessions;
}

// ============================================================================
// Analysis
// ============================================================================

function analyze(activations, corrections, sessions) {
  const report = {};

  // 1. Activation frequency
  const skillFreq = {};
  const skillReasons = {};
  let totalActivations = 0;
  let totalSkipped = 0;

  for (const a of activations) {
    const finals = Array.isArray(a.final) ? a.final : (a.final || '').split(' ').filter(Boolean);
    for (const skill of finals) {
      skillFreq[skill] = (skillFreq[skill] || 0) + 1;
      totalActivations++;
    }
    const reasons = a.match_reasons || [];
    const matched = a.matched || [];
    for (let i = 0; i < matched.length; i++) {
      const skill = matched[i];
      const reason = reasons[i] || 'unknown';
      if (!skillReasons[skill]) skillReasons[skill] = {};
      skillReasons[skill][reason] = (skillReasons[skill][reason] || 0) + 1;
    }
    const skipped = a.skipped || [];
    totalSkipped += skipped.length;
  }

  report.activation_frequency = Object.entries(skillFreq)
    .sort((a, b) => b[1] - a[1])
    .slice(0, topN)
    .map(([skill, count]) => ({ skill, count, pct: Math.round(count / totalActivations * 100) }));

  report.total_activations = totalActivations;
  report.total_activation_events = activations.length;
  report.total_skipped = totalSkipped;

  // 2. Trigger reasons per skill
  report.trigger_reasons = Object.entries(skillReasons)
    .sort((a, b) => Object.values(b[1]).reduce((s, v) => s + v, 0) - Object.values(a[1]).reduce((s, v) => s + v, 0))
    .slice(0, topN)
    .map(([skill, reasons]) => ({ skill, reasons }));

  // 3. Correction analysis
  const correctionBySkill = {};
  for (const c of corrections) {
    // Handle both array and space-separated string formats
    const skills = Array.isArray(c.recent_skills)
      ? c.recent_skills
      : (typeof c.recent_skills === 'string' ? c.recent_skills.split(' ').filter(Boolean) : []);
    for (const skill of skills) {
      if (!correctionBySkill[skill]) correctionBySkill[skill] = [];
      correctionBySkill[skill].push(c.correction_keyword);
    }
  }

  report.corrections = {
    total: corrections.length,
    by_skill: Object.entries(correctionBySkill)
      .sort((a, b) => b[1].length - a[1].length)
      .map(([skill, keywords]) => ({
        skill,
        count: keywords.length,
        keywords: [...new Set(keywords)],
      })),
  };

  // 4. IO efficiency from sessions
  const ioBySkill = {};
  for (const sess of sessions) {
    const perSkill = sess.perSkill || {};
    for (const [skill, lines] of Object.entries(perSkill)) {
      if (!ioBySkill[skill]) ioBySkill[skill] = { totalLines: 0, sessionCount: 0 };
      ioBySkill[skill].totalLines += lines;
      ioBySkill[skill].sessionCount++;
    }
  }

  report.io_efficiency = Object.entries(ioBySkill)
    .sort((a, b) => b[1].totalLines - a[1].totalLines)
    .slice(0, topN)
    .map(([skill, data]) => ({
      skill,
      totalLines: data.totalLines,
      avgPerSession: Math.round(data.totalLines / data.sessionCount),
      sessionCount: data.sessionCount,
    }));

  // 5. Co-occurrence (skills used together in same activation event)
  const pairCount = {};
  for (const a of activations) {
    const finals = Array.isArray(a.final) ? a.final : (a.final || '').split(' ').filter(Boolean);
    if (finals.length < 2) continue;
    for (let i = 0; i < finals.length; i++) {
      for (let j = i + 1; j < finals.length; j++) {
        const pair = [finals[i], finals[j]].sort().join(' + ');
        pairCount[pair] = (pairCount[pair] || 0) + 1;
      }
    }
  }

  report.co_occurrence = Object.entries(pairCount)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5)
    .map(([pair, count]) => ({ pair, count }));

  // 6. Daily trend
  const dailyCount = {};
  for (const a of activations) {
    dailyCount[a._date] = (dailyCount[a._date] || 0) + 1;
  }
  report.daily_trend = Object.entries(dailyCount).sort();

  return report;
}

// ============================================================================
// Output formatting
// ============================================================================

function formatMarkdown(report) {
  const lines = [];
  lines.push(`# Skill Observatory Report`);
  lines.push(`> 分析周期: 最近 ${daysBack} 天 | 生成时间: ${new Date().toISOString().substring(0, 19)}`);
  lines.push('');

  lines.push(`## 概览`);
  lines.push(`- 激活事件: ${report.total_activation_events} 次`);
  lines.push(`- 激活 skill 总次数: ${report.total_activations}`);
  lines.push(`- 被跳过/否决: ${report.total_skipped} 次`);
  lines.push(`- 用户纠正: ${report.corrections.total} 次`);
  lines.push('');

  lines.push(`## 激活频率 Top ${topN}`);
  lines.push('| Skill | 次数 | 占比 |');
  lines.push('|-------|------|------|');
  for (const r of report.activation_frequency) {
    lines.push(`| ${r.skill} | ${r.count} | ${r.pct}% |`);
  }
  lines.push('');

  if (report.trigger_reasons.length > 0) {
    lines.push(`## 触发原因`);
    lines.push('| Skill | 触发词/模式 |');
    lines.push('|-------|-----------|');
    for (const r of report.trigger_reasons) {
      const reasonStr = Object.entries(r.reasons).map(([k, v]) => `${k}(${v})`).join(', ');
      lines.push(`| ${r.skill} | ${reasonStr} |`);
    }
    lines.push('');
  }

  if (report.corrections.by_skill.length > 0) {
    lines.push(`## 纠正关联（用户纠正 → 关联 Skill）`);
    lines.push('| Skill | 纠正次数 | 纠正关键词 |');
    lines.push('|-------|---------|-----------|');
    for (const c of report.corrections.by_skill) {
      lines.push(`| ${c.skill} | ${c.count} | ${c.keywords.join(', ')} |`);
    }
    lines.push('');
  }

  if (report.io_efficiency.length > 0) {
    lines.push(`## IO 效率（资源加载量）`);
    lines.push('| Skill | 总行数 | 每会话均值 | 会话数 |');
    lines.push('|-------|--------|-----------|--------|');
    for (const r of report.io_efficiency) {
      lines.push(`| ${r.skill} | ${r.totalLines} | ${r.avgPerSession} | ${r.sessionCount} |`);
    }
    lines.push('');
  }

  if (report.co_occurrence.length > 0) {
    lines.push(`## 协作模式（同次激活共现 Top 5）`);
    lines.push('| Skill 组合 | 共现次数 |');
    lines.push('|-----------|---------|');
    for (const c of report.co_occurrence) {
      lines.push(`| ${c.pair} | ${c.count} |`);
    }
    lines.push('');
  }

  if (report.daily_trend.length > 0) {
    lines.push(`## 日趋势`);
    lines.push('| 日期 | 激活事件数 |');
    lines.push('|------|----------|');
    for (const [date, count] of report.daily_trend) {
      lines.push(`| ${date} | ${count} |`);
    }
    lines.push('');
  }

  return lines.join('\n');
}

// ============================================================================
// Main
// ============================================================================

const dates = dateRange(daysBack);

const activations = loadJsonl(path.join(obsDir, 'activations'), dates);
const corrections = loadJsonl(path.join(obsDir, 'corrections'), dates);
const sessions = loadSessions(path.join(obsDir, 'sessions'));

if (activations.length === 0 && sessions.length === 0) {
  print('No observatory data found. Skill usage data will accumulate after hooks are active.');
  process.exit(0);
}

const report = analyze(activations, corrections, sessions);

if (jsonOutput) {
  print(JSON.stringify(report, null, 2));
} else {
  print(formatMarkdown(report));
}
