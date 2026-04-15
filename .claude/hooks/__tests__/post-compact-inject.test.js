#!/usr/bin/env node
/**
 * TDD 测试：post-compact-inject.js
 *
 * 使用 Node.js 内置 assert + child_process，无外部依赖。
 * 通过构造 /tmp 下的模拟数据验证各场景。
 */

const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');
const os = require('os');
const crypto = require('crypto');
const assert = require('assert');

const HOOK_PATH = path.join(__dirname, '..', 'post-compact-inject.js');
const PROJECT_DIR = path.resolve(__dirname, '..', '..', '..');

// ============================================================================
// 测试工具
// ============================================================================

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

function runHook(env = {}) {
  const fullEnv = {
    ...process.env,
    CLAUDE_PROJECT_DIR: PROJECT_DIR,
    ...env,
  };
  try {
    const stdout = execSync(`echo '{}' | node "${HOOK_PATH}"`, {
      env: fullEnv,
      encoding: 'utf8',
      timeout: 5000,
    });
    return { stdout: stdout.trim(), exitCode: 0 };
  } catch (err) {
    return { stdout: (err.stdout || '').trim(), exitCode: err.status };
  }
}

function parseOutput(stdout) {
  if (!stdout) return null;
  try {
    return JSON.parse(stdout);
  } catch {
    return null;
  }
}

function getContext(stdout) {
  const data = parseOutput(stdout);
  return data?.hookSpecificOutput?.additionalContext || '';
}

// 创建临时 plan.md 并返回目录路径
function createTempPlan(content) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'postcompact-test-'));
  fs.writeFileSync(path.join(dir, 'plan.md'), content, 'utf8');
  return dir;
}

// 创建模拟 Ralph 状态文件
function createMockRalph(projectHash, sessionId, planPath) {
  const uuid = crypto.randomBytes(8).toString('hex');
  const prefix = path.join(os.tmpdir(), `stark-ralph-${projectHash}-${uuid}`);
  const anchor = path.join(os.tmpdir(), `stark-ralph-${projectHash}-${sessionId}-current`);

  fs.writeFileSync(anchor, uuid, 'utf8');
  fs.writeFileSync(`${prefix}-active`, 'active', 'utf8');
  fs.writeFileSync(`${prefix}-plan`, planPath, 'utf8');

  return {
    uuid,
    prefix,
    anchor,
    cleanup() {
      [anchor, `${prefix}-active`, `${prefix}-plan`].forEach(f => {
        try { fs.unlinkSync(f); } catch { /* ignore */ }
      });
    },
  };
}

function cleanup(dir) {
  try { fs.rmSync(dir, { recursive: true }); } catch { /* ignore */ }
}

// ============================================================================
// 测试用例
// ============================================================================

console.log('\n🧪 PostCompact Hook 测试\n');

// --- 场景 1：有 plan.md + 有进行中任务 ---
console.log('场景 1：有 plan.md + 有进行中任务');
{
  const planContent = `# 测试计划
### ✅ T1: 已完成任务A
### 🔄 T2: 进行中任务B
### ⬜ T3: 待执行任务C
`;
  const dir = createTempPlan(planContent);
  const { stdout } = runHook({ STARK_SESSION_DIR: dir, CLAUDE_SESSION_ID: 'test-s1' });
  const ctx = getContext(stdout);

  test('输出包含当前任务', () => {
    assert(ctx.includes('进行中任务B'), `未找到当前任务，输出: ${ctx}`);
  });
  test('输出包含进度统计', () => {
    assert(ctx.includes('1/3'), `未找到进度 1/3，输出: ${ctx}`);
  });
  test('输出包含自省提醒', () => {
    assert(ctx.includes('CLAUDE.md'), `未找到自省提醒，输出: ${ctx}`);
  });
  test('输出包含压缩标记', () => {
    assert(ctx.includes('⚡'), `未找到压缩标记，输出: ${ctx}`);
  });

  cleanup(dir);
}

// --- 场景 2：有 plan.md + 全部完成 ---
console.log('\n场景 2：有 plan.md + 全部完成');
{
  const planContent = `# 测试计划
### ✅ T1: 任务A
### ✅ T2: 任务B
### ✅ T3: 任务C
`;
  const dir = createTempPlan(planContent);
  const { stdout } = runHook({ STARK_SESSION_DIR: dir, CLAUDE_SESSION_ID: 'test-s2' });
  const ctx = getContext(stdout);

  test('进度显示全部完成', () => {
    assert(ctx.includes('3/3'), `未找到进度 3/3，输出: ${ctx}`);
  });
  test('包含已完成任务列表', () => {
    assert(ctx.includes('已完成'), `未找到已完成标记，输出: ${ctx}`);
  });
  test('包含自省提醒', () => {
    assert(ctx.includes('CLAUDE.md'), `未找到自省提醒`);
  });

  cleanup(dir);
}

// --- 场景 3：有 plan.md + 无任务标记 ---
console.log('\n场景 3：有 plan.md + 无任务标记');
{
  const planContent = `# 空计划
这里只有文字，没有任务标记。
`;
  const dir = createTempPlan(planContent);
  const { stdout } = runHook({ STARK_SESSION_DIR: dir, CLAUDE_SESSION_ID: 'test-s3' });
  const ctx = getContext(stdout);

  test('无任务时仅自省提醒', () => {
    assert(ctx.includes('CLAUDE.md'), `未找到自省提醒`);
    assert(!ctx.includes('进度'), `不应包含进度信息，输出: ${ctx}`);
  });

  cleanup(dir);
}

// --- 场景 4：无 plan.md ---
console.log('\n场景 4：无 plan.md');
{
  const { stdout } = runHook({
    STARK_SESSION_DIR: '/tmp/nonexistent-dir-12345',
    CLAUDE_SESSION_ID: 'test-s4',
  });
  const ctx = getContext(stdout);

  test('无 plan 时仅自省提醒', () => {
    assert(ctx.includes('CLAUDE.md'), `未找到自省提醒`);
  });
  test('不包含任务进度', () => {
    assert(!ctx.includes('当前:'), `不应包含任务进度，输出: ${ctx}`);
  });

  cleanup('/tmp/nonexistent-dir-12345');
}

// --- 场景 5：markdown header 过滤 ---
console.log('\n场景 5：markdown header ### 过滤');
{
  const planContent = `# 计划
### ⬜ T1: 带 header 的任务名
`;
  const dir = createTempPlan(planContent);
  const { stdout } = runHook({ STARK_SESSION_DIR: dir, CLAUDE_SESSION_ID: 'test-s5' });
  const ctx = getContext(stdout);

  test('任务名不含 ### 前缀', () => {
    assert(!ctx.includes('###'), `任务名仍含 ###，输出: ${ctx}`);
  });
  test('任务名正确提取', () => {
    assert(ctx.includes('带 header 的任务名'), `未正确提取任务名，输出: ${ctx}`);
  });

  cleanup(dir);
}

// --- 场景 6：任务名超 60 字符截断 ---
console.log('\n场景 6：任务名超 60 字符截断');
{
  const longName = '这是一个非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常长的任务名称用来测试截断逻辑';
  const planContent = `# 计划
### ⬜ T1: ${longName}
`;
  const dir = createTempPlan(planContent);
  const { stdout } = runHook({ STARK_SESSION_DIR: dir, CLAUDE_SESSION_ID: 'test-s6' });
  const ctx = getContext(stdout);

  test('任务名被截断到 60 字符以内', () => {
    // 提取"当前:"后面的内容
    const match = ctx.match(/当前:\s*(.+)/);
    assert(match, `未找到当前任务，输出: ${ctx}`);
    const taskName = match[1].split('\n')[0].trim();
    assert(taskName.length <= 60, `任务名 ${taskName.length} 字符，超过 60`);
  });

  cleanup(dir);
}

// --- 场景 7：脚本异常不阻断 ---
console.log('\n场景 7：异常场景退出码为 0');
{
  // 给一个存在但无权限的路径
  const { stdout, exitCode } = runHook({
    STARK_SESSION_DIR: '/tmp/nonexistent-dir-99999',
    CLAUDE_SESSION_ID: 'test-s7',
  });

  test('退出码为 0', () => {
    assert.strictEqual(exitCode, 0, `退出码 ${exitCode}，期望 0`);
  });
}

// --- 场景 8：JSON 输出结构合规 ---
console.log('\n场景 8：JSON 输出结构合规');
{
  const planContent = `# 计划
### 🔄 T1: 测试任务
`;
  const dir = createTempPlan(planContent);
  const { stdout } = runHook({ STARK_SESSION_DIR: dir, CLAUDE_SESSION_ID: 'test-s8' });
  const data = parseOutput(stdout);

  test('顶层有 hookSpecificOutput', () => {
    assert(data?.hookSpecificOutput, 'hookSpecificOutput 缺失');
  });
  test('hookSpecificOutput 有 additionalContext', () => {
    assert(typeof data?.hookSpecificOutput?.additionalContext === 'string',
      'additionalContext 不是 string');
  });
  test('无多余顶层字段', () => {
    const keys = Object.keys(data);
    assert.strictEqual(keys.length, 1, `期望 1 个顶层字段，实际 ${keys.length}: ${keys}`);
  });

  cleanup(dir);
}

// --- 场景 9：Ralph 路径优先于 STARK_SESSION_DIR ---
console.log('\n场景 9：Ralph 路径优先级');
{
  const projectHash = crypto.createHash('md5').update(PROJECT_DIR).digest('hex').slice(0, 8);
  const sessionId = 'test-s9-priority';

  // 创建两个不同的 plan
  const ralphDir = createTempPlan(`# Ralph Plan\n### 🔄 T1: Ralph优先任务\n`);
  const sessionDir = createTempPlan(`# Session Plan\n### 🔄 T1: Session后备任务\n`);

  const ralphPlanPath = path.join(ralphDir, 'plan.md');
  const ralph = createMockRalph(projectHash, sessionId, ralphPlanPath);

  const { stdout } = runHook({
    STARK_SESSION_DIR: sessionDir,
    CLAUDE_SESSION_ID: sessionId,
  });
  const ctx = getContext(stdout);

  test('Ralph 路径优先', () => {
    assert(ctx.includes('Ralph优先任务'), `应包含 Ralph 任务，输出: ${ctx}`);
    assert(!ctx.includes('Session后备任务'), `不应包含 Session 任务，输出: ${ctx}`);
  });

  ralph.cleanup();
  cleanup(ralphDir);
  cleanup(sessionDir);
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
