#!/usr/bin/env node
/**
 * TDD 测试：skill-meta-guard.js
 *
 * 验证：
 * 1. vipship 路径 → deny
 * 2. 非绝对路径 → deny
 * 3. 跨项目路径 → deny
 * 4. SKILL.md 缺 frontmatter/description → deny
 * 5. version/lastUpdated 字段 → deny
 * 6. 合法编辑 → allow
 * 7. 异常时不崩溃（.catch 兜底）
 */

const { execSync } = require('child_process');
const path = require('path');
const assert = require('assert');

const HOOK_PATH = path.join(__dirname, '..', 'skill-meta-guard.js');
const PROJECT_DIR = path.resolve(__dirname, '..', '..', '..');

let testCount = 0;
let passCount = 0;
let failCount = 0;

function test(name, fn) {
  testCount++;
  try {
    fn();
    passCount++;
    console.log(`  ✅ ${name}`);
  } catch (err) {
    failCount++;
    console.log(`  ❌ ${name}`);
    console.log(`     ${err.message}`);
  }
}

function runHook(toolName, toolInput, env = {}) {
  const input = JSON.stringify({ tool_name: toolName, tool_input: toolInput });
  const fullEnv = {
    ...process.env,
    CLAUDE_PROJECT_DIR: PROJECT_DIR,
    ...env,
  };
  try {
    const stdout = execSync(
      `printf '%s' '${input.replace(/'/g, "'\\''")}' | node "${HOOK_PATH}"`,
      { env: fullEnv, encoding: 'utf8', timeout: 5000, stdio: ['pipe', 'pipe', 'pipe'] }
    );
    return { stdout: stdout.trim(), exitCode: 0 };
  } catch (err) {
    return { stdout: (err.stdout || '').trim(), stderr: (err.stderr || '').trim(), exitCode: err.status };
  }
}

function isDenied(result) {
  if (!result.stdout) return false;
  try {
    return JSON.parse(result.stdout)?.hookSpecificOutput?.permissionDecision === 'deny';
  } catch {
    return false;
  }
}

function getDenyReason(result) {
  try {
    return JSON.parse(result.stdout)?.hookSpecificOutput?.permissionDecisionReason || '';
  } catch {
    return '';
  }
}

// ============================================================================
// 测试用例
// ============================================================================

console.log('\n🧪 Skill Meta Guard 测试\n');

// --- 规则 1: vipship 路径 → deny ---
console.log('规则 1：vipship 路径硬阻断');
{
  test('vipship skills 路径被拦截', () => {
    const r = runHook('Edit', {
      file_path: `${PROJECT_DIR}/vipship/.claude/skills/cc-sql/SKILL.md`,
      old_string: 'a', new_string: 'b',
    });
    assert(isDenied(r), '应拦截 vipship 路径');
    assert(getDenyReason(r).includes('vipship'), '应提及 vipship');
  });
}

// --- 规则 2: 非绝对路径 → deny ---
console.log('\n规则 2：非绝对路径 → deny');
{
  test('相对路径被拦截', () => {
    const r = runHook('Edit', {
      file_path: '.claude/skills/cc-sql/SKILL.md',
      old_string: 'a', new_string: 'b',
    });
    assert(isDenied(r), '应拦截相对路径');
    assert(getDenyReason(r).includes('绝对路径'), '应提及绝对路径');
  });
}

// --- 规则 3: 跨项目路径 → deny ---
console.log('\n规则 3：跨项目路径 → deny');
{
  test('其他项目的 skills 路径被拦截', () => {
    const r = runHook('Edit', {
      file_path: '/Users/other/project/.claude/skills/cc-sql/SKILL.md',
      old_string: 'a', new_string: 'b',
    });
    assert(isDenied(r), '应拦截跨项目路径');
  });
}

// --- 规则 4: SKILL.md frontmatter 检查（Write）---
console.log('\n规则 4：SKILL.md frontmatter 检查');
{
  test('缺 frontmatter → deny', () => {
    const r = runHook('Write', {
      file_path: `${PROJECT_DIR}/.claude/skills/cc-test/SKILL.md`,
      content: '# 没有 frontmatter 的内容\n',
    });
    assert(isDenied(r), '应拦截缺 frontmatter');
    assert(getDenyReason(r).includes('frontmatter'), '应提及 frontmatter');
  });

  test('缺 description → deny', () => {
    const r = runHook('Write', {
      file_path: `${PROJECT_DIR}/.claude/skills/cc-test/SKILL.md`,
      content: '---\nname: cc-test\n---\n# 内容\n',
    });
    assert(isDenied(r), '应拦截缺 description');
    assert(getDenyReason(r).includes('description'), '应提及 description');
  });

  test('有 description → allow', () => {
    const r = runHook('Write', {
      file_path: `${PROJECT_DIR}/.claude/skills/cc-test/SKILL.md`,
      content: '---\nname: cc-test\ndescription: 测试用\n---\n# 内容\n',
    });
    assert(!isDenied(r), '有 description 应放行');
  });
}

// --- 规则 5: 禁止 version/lastUpdated ---
console.log('\n规则 5：禁止 version/lastUpdated');
{
  test('Write SKILL.md 带 version → deny', () => {
    const r = runHook('Write', {
      file_path: `${PROJECT_DIR}/.claude/skills/cc-test/SKILL.md`,
      content: '---\nname: cc-test\ndescription: 测试\nversion: 1.0\n---\n',
    });
    assert(isDenied(r), '应拦截 version');
  });

  test('Edit 引入 lastUpdated → deny', () => {
    const r = runHook('Edit', {
      file_path: `${PROJECT_DIR}/.claude/skills/cc-test/SKILL.md`,
      old_string: 'old', new_string: 'lastUpdated: 2025-01-01\nnew',
    });
    assert(isDenied(r), '应拦截 lastUpdated');
  });

  test('Edit skill-rules.json 引入 version → deny', () => {
    const r = runHook('Edit', {
      file_path: `${PROJECT_DIR}/.claude/skills/skill-rules.json`,
      old_string: '"old"', new_string: 'version: 2\n"new"',
    });
    assert(isDenied(r), '应拦截 skill-rules.json 中的 version');
  });
}

// --- 合法编辑 → allow ---
console.log('\n合法编辑 → allow');
{
  test('正常 Edit skills 文件放行', () => {
    const r = runHook('Edit', {
      file_path: `${PROJECT_DIR}/.claude/skills/cc-sql/query.py`,
      old_string: 'old', new_string: 'new',
    });
    assert(!isDenied(r), '正常 edit 应放行');
  });

  test('非 skills 路径不管', () => {
    const r = runHook('Edit', {
      file_path: `${PROJECT_DIR}/src/main.js`,
      old_string: 'a', new_string: 'b',
    });
    assert(!isDenied(r), '非 skills 路径应放行');
  });

  test('无 file_path 放行', () => {
    const r = runHook('Edit', {});
    assert(!isDenied(r), '无 file_path 应放行');
  });
}

// --- 异常不崩溃（.catch 兜底）---
console.log('\n异常处理');
{
  test('hook 退出码为 0（不崩溃）', () => {
    const r = runHook('Write', {
      file_path: `${PROJECT_DIR}/.claude/skills/cc-test/SKILL.md`,
      content: '---\nname: cc-test\ndescription: ok\n---\n# ok',
    });
    assert.strictEqual(r.exitCode, 0, `退出码应为 0，实际 ${r.exitCode}`);
  });
}

// ============================================================================
// 汇总
// ============================================================================

console.log(`\n${'='.repeat(50)}`);
console.log(`测试结果: ${passCount}/${testCount} 通过`);
if (failCount > 0) {
  console.log(`❌ ${failCount} 个失败`);
  process.exit(1);
} else {
  console.log('✅ 全部通过');
}
