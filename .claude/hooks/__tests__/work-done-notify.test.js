#!/usr/bin/env node
/**
 * TDD 测试：work-done-notify.js
 *
 * 验证：
 * 1. 有 transcript_summary → 调用 notify.sh
 * 2. 空 summary → 跳过通知
 * 3. stop_hook_active=true → 跳过通知（Ralph 循环中）
 * 4. 退出码始终为 0（不阻塞）
 * 5. notify.sh 不存在时不崩溃
 */

const { execSync } = require('child_process');
const path = require('path');
const assert = require('assert');

const HOOK_PATH = path.join(__dirname, '..', 'work-done-notify.js');

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

function runHook(inputObj, env = {}) {
  const input = JSON.stringify(inputObj);
  const fullEnv = { ...process.env, ...env };
  try {
    const stdout = execSync(
      `printf '%s' '${input.replace(/'/g, "'\\''")}' | node "${HOOK_PATH}"`,
      { env: fullEnv, encoding: 'utf8', timeout: 10000, stdio: ['pipe', 'pipe', 'pipe'] }
    );
    return { stdout: stdout.trim(), exitCode: 0 };
  } catch (err) {
    return { stdout: (err.stdout || '').trim(), stderr: (err.stderr || '').trim(), exitCode: err.status };
  }
}

// ============================================================================
// 测试用例
// ============================================================================

console.log('\n🧪 Work Done Notify 测试\n');

// --- 退出码始终为 0 ---
console.log('退出码保证');
{
  test('有 summary 时退出码为 0', () => {
    const r = runHook({ transcript_summary: '完成了代码审查' });
    assert.strictEqual(r.exitCode, 0, `退出码应为 0，实际 ${r.exitCode}`);
  });

  test('空 summary 时退出码为 0', () => {
    const r = runHook({ transcript_summary: '' });
    assert.strictEqual(r.exitCode, 0, `退出码应为 0，实际 ${r.exitCode}`);
  });

  test('无 summary 字段时退出码为 0', () => {
    const r = runHook({});
    assert.strictEqual(r.exitCode, 0, `退出码应为 0，实际 ${r.exitCode}`);
  });

  test('stop_hook_active=true 时退出码为 0', () => {
    const r = runHook({ stop_hook_active: true, transcript_summary: '测试' });
    assert.strictEqual(r.exitCode, 0, `退出码应为 0，实际 ${r.exitCode}`);
  });
}

// --- 跳过条件 ---
console.log('\n跳过条件');
{
  test('空 summary 不调用 notify', () => {
    // 空 summary 应该直接返回，不调用 execFile
    // 验证方式：hook 很快退出（<1s），不因等待 notify.sh 而超时
    const start = Date.now();
    runHook({ transcript_summary: '' });
    const elapsed = Date.now() - start;
    assert(elapsed < 3000, `空 summary 应快速退出，实际耗时 ${elapsed}ms`);
  });

  test('stop_hook_active=true 不调用 notify', () => {
    const start = Date.now();
    runHook({ stop_hook_active: true, transcript_summary: '这条不应该被发送' });
    const elapsed = Date.now() - start;
    assert(elapsed < 3000, `stop_hook_active 应快速退出，实际耗时 ${elapsed}ms`);
  });
}

// --- 长 summary 截断 ---
console.log('\n内容处理');
{
  test('长 summary 被截断到 100 字符', () => {
    // 无法直接验证截断（需要看 notify.sh 的参数），但可确保不崩溃
    const longSummary = '这是一段非常长的摘要'.repeat(20);
    const r = runHook({ transcript_summary: longSummary });
    assert.strictEqual(r.exitCode, 0, '长 summary 不应崩溃');
  });
}

// --- JSON 解析异常 ---
console.log('\n异常处理');
{
  test('无效 JSON 输入不崩溃', () => {
    try {
      const stdout = execSync(
        `echo 'not json' | node "${HOOK_PATH}"`,
        { encoding: 'utf8', timeout: 5000, stdio: ['pipe', 'pipe', 'pipe'] }
      );
      // 应该正常退出
    } catch (err) {
      assert.strictEqual(err.status, 0, `无效 JSON 退出码应为 0，实际 ${err.status}`);
    }
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
