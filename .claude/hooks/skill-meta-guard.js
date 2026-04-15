#!/usr/bin/env node
/**
 * Skill Meta Guard - PreToolUse Hook for Write|Edit
 *
 * 防御 .claude/skills/ 和 shared-rules/ 编辑时的常见错误：
 * 1. 路径必须绝对且基于 $CLAUDE_PROJECT_DIR（禁止编辑 vipship/ skill 快照，放行 plan/session 等运营文件）
 * 2. SKILL.md 写入时 frontmatter 必须含 description（name 由目录名派生，不强制）
 * 3. 禁止引入 version/lastUpdated 字段（项目通过 git 管理版本）
 *
 * 背景: Iter 23/25/28 均因「编辑 vipship 快照而非 my_claude 源」踩坑
 * 参考: memory feedback_my_claude_is_source_of_truth.md
 *
 * 阻断策略: deny（硬阻断）— 路径错误和规范违反均不可放行
 * 挂载点: PreToolUse(Write|Edit)
 */

const { readStdin, log } = require('../scripts/lib/utils');

const PROJECT_DIR = process.env.CLAUDE_PROJECT_DIR || '';

// 需要守护的路径前缀（相对于项目根目录）
const GUARDED_PATHS = ['.claude/skills/', 'shared-rules/'];

// vipship skill 快照路径（只读，禁止编辑）— 只保护 skill 相关目录，放行 plan/session 等运营文件
const BLOCKED_PATHS = ['vipship/.claude/skills/', 'vipship/shared-rules/'];

function deny(reason) {
  process.stderr.write(`[skill-meta-guard] DENY: ${reason}\n`);
  process.stdout.write(JSON.stringify({
    hookSpecificOutput: {
      hookEventName: 'PreToolUse',
      permissionDecision: 'deny',
      permissionDecisionReason: reason,
    },
  }));
}

function allow() {
  // 不输出任何内容 = 不干预决策
}

function isGuardedPath(filePath) {
  if (!PROJECT_DIR) {
    // CLAUDE_PROJECT_DIR 未设置时，用路径子串匹配降级守护（不静默放行）
    return GUARDED_PATHS.some(p => filePath.includes('/' + p) || filePath.includes('\\' + p));
  }
  // 正常路径：基于 PROJECT_DIR 前缀匹配
  if (filePath.startsWith(PROJECT_DIR)) {
    const relative = filePath.slice(PROJECT_DIR.length + 1); // +1 for trailing /
    return GUARDED_PATHS.some(p => relative.startsWith(p));
  }
  // 相对路径或跨项目路径：用子串匹配兜底，让后续的绝对路径/PROJECT_DIR 检查来 deny
  return GUARDED_PATHS.some(p =>
    filePath.includes('/' + p) || filePath.includes('\\' + p) || filePath.startsWith(p)
  );
}

function isBlockedPath(filePath) {
  const lower = filePath.toLowerCase();
  return BLOCKED_PATHS.some(p => lower.includes(`/${p}`) || lower.includes(`\\${p}`));
}

// SKILL.md frontmatter 完整性检查（仅 Write 全量内容时可检查）
// 只检查 description（Claude Code 依赖此字段做 skill 展示），name 由目录名派生不强制
function checkFrontmatter(content) {
  const fmMatch = content.match(/^---\s*\n([\s\S]*?)\n---/);
  if (!fmMatch) return 'SKILL.md 缺少 frontmatter（需要 --- 包裹的 YAML 头）';

  const fm = fmMatch[1];
  if (!/^description\s*:/m.test(fm)) {
    return 'SKILL.md frontmatter 缺少 description 字段';
  }
  return null; // 通过
}

// 检查内容是否引入禁止字段
function checkForbiddenFields(content) {
  // 只检查 frontmatter 区域内的 version/lastUpdated
  const fmMatch = content.match(/^---\s*\n([\s\S]*?)\n---/);
  const textToCheck = fmMatch ? fmMatch[1] : content;

  if (/^version\s*:/m.test(textToCheck)) {
    return 'SKILL.md/skill-rules.json 禁止 version 字段（项目通过 git 管理版本）';
  }
  if (/^lastUpdated\s*:/m.test(textToCheck)) {
    return 'SKILL.md/skill-rules.json 禁止 lastUpdated 字段（项目通过 git 管理版本）';
  }
  return null;
}

async function main() {
  const input = await readStdin();
  const toolName = input.tool_name || '';
  const toolInput = input.tool_input || {};
  const filePath = toolInput.file_path || '';

  if (!filePath) return allow();

  // ━━━ 规则 1: vipship 路径硬阻断 ━━━
  if (isBlockedPath(filePath)) {
    return deny(
      `禁止编辑 vipship/ 快照。vipship/.claude/skills/ 是 Iter 19 快照，` +
      `请编辑 ${PROJECT_DIR}/.claude/skills/ 下的源文件。` +
      `（feedback_my_claude_is_source_of_truth）`
    );
  }

  // 只守护 .claude/skills/ 和 shared-rules/ 下的文件
  if (!isGuardedPath(filePath)) return allow();

  // ━━━ 规则 2: 路径必须绝对且基于 $CLAUDE_PROJECT_DIR ━━━
  if (!filePath.startsWith('/')) {
    return deny(
      `Skill 文件编辑必须使用绝对路径。收到: ${filePath}。` +
      `请使用 ${PROJECT_DIR}/.claude/skills/... 完整路径。`
    );
  }
  if (PROJECT_DIR && !filePath.startsWith(PROJECT_DIR + '/')) {
    return deny(
      `Skill 文件编辑路径必须基于当前项目 ($CLAUDE_PROJECT_DIR=${PROJECT_DIR})。` +
      `收到: ${filePath}。禁止编辑其他项目的 skill 文件。`
    );
  }

  // ━━━ 规则 3: SKILL.md 内容检查 ━━━
  const isSkillMd = filePath.endsWith('/SKILL.md');
  const isSkillRulesJson = filePath.endsWith('/skill-rules.json');

  if (toolName === 'Write' && isSkillMd) {
    // Write = 全量内容，可以检查 frontmatter 完整性
    const content = toolInput.content || '';
    const fmError = checkFrontmatter(content);
    if (fmError) return deny(fmError);

    const fieldError = checkForbiddenFields(content);
    if (fieldError) return deny(fieldError);
  }

  if (toolName === 'Edit') {
    const newString = toolInput.new_string || '';

    // Edit 只能检查 new_string 是否引入禁止字段
    if (isSkillMd || isSkillRulesJson) {
      // 检查 new_string 中是否有 version:/lastUpdated: 行
      if (/^version\s*:/m.test(newString)) {
        return deny('禁止在 SKILL.md/skill-rules.json 中引入 version 字段（项目通过 git 管理版本）');
      }
      if (/^lastUpdated\s*:/m.test(newString)) {
        return deny('禁止在 SKILL.md/skill-rules.json 中引入 lastUpdated 字段（项目通过 git 管理版本）');
      }
    }
  }

  // 通过所有检查
  return allow();
}

main().catch(err => {
  process.stderr.write(`[skill-meta-guard] Error: ${err.message}\n`);
  process.exit(0);
});
