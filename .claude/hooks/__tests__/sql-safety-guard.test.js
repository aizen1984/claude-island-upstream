#!/usr/bin/env node
/**
 * TDD 测试：sql-safety-guard.js
 *
 * 验证三层守护逻辑：
 * 1. 直接 DB 客户端命令 → deny
 * 2. cc-sql 脚本 → allow
 * 3. query.py + DML/DDL → deny
 * 4. 非 SQL 命令 → allow（核心回归：修复前所有 Bash 命令都崩溃）
 */

const { execSync } = require('child_process');
const path = require('path');
const assert = require('assert');

const HOOK_PATH = path.join(__dirname, '..', 'sql-safety-guard.js');

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

function runHook(command) {
  const input = JSON.stringify({ tool_name: 'Bash', tool_input: { command } });
  try {
    const stdout = execSync(`echo '${input.replace(/'/g, "'\\''")}' | node "${HOOK_PATH}"`, {
      encoding: 'utf8',
      timeout: 5000,
      stdio: ['pipe', 'pipe', 'pipe'],
    });
    return { stdout: stdout.trim(), exitCode: 0 };
  } catch (err) {
    return { stdout: (err.stdout || '').trim(), stderr: (err.stderr || '').trim(), exitCode: err.status };
  }
}

function isDenied(result) {
  if (!result.stdout) return false;
  try {
    const data = JSON.parse(result.stdout);
    return data?.hookSpecificOutput?.permissionDecision === 'deny';
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

console.log('\n🧪 SQL Safety Guard 测试\n');

// --- 规则 1: 直接 DB 客户端 → deny ---
console.log('规则 1：直接 DB 客户端命令 → deny');
{
  test('mysql 命令被拦截', () => {
    const r = runHook('mysql -u root -p mydb');
    assert(isDenied(r), `应拦截 mysql，stdout: ${r.stdout}`);
    assert(getDenyReason(r).includes('mysql'), '拒绝原因应提及 mysql');
  });

  test('psql 命令被拦截', () => {
    const r = runHook('psql -h localhost -d mydb');
    assert(isDenied(r), `应拦截 psql，stdout: ${r.stdout}`);
  });

  test('sqlite3 命令被拦截', () => {
    const r = runHook('sqlite3 test.db');
    assert(isDenied(r), `应拦截 sqlite3`);
  });

  test('sudo mysql 被拦截（跳过前缀词）', () => {
    const r = runHook('sudo mysql -u admin');
    assert(isDenied(r), `应拦截 sudo mysql`);
  });

  test('管道中的 mysql 被拦截', () => {
    const r = runHook('cat dump.sql | mysql -u root');
    assert(isDenied(r), `应拦截管道中的 mysql`);
  });

  test('redis-cli 被拦截', () => {
    const r = runHook('redis-cli -h 127.0.0.1');
    assert(isDenied(r), `应拦截 redis-cli`);
  });
}

// --- 规则 1 反例：不误报 ---
console.log('\n规则 1 反例：不误报');
{
  test('git commit 消息含 mysql 不误报', () => {
    const r = runHook('git commit -m "fix mysql connection pool"');
    assert(!isDenied(r), `不应拦截 git commit 消息中的 mysql`);
  });

  test('echo 含 mysql 不误报', () => {
    const r = runHook('echo "mysql is running"');
    assert(!isDenied(r), `不应拦截 echo 中的 mysql`);
  });

  test('grep mysql 不误报', () => {
    const r = runHook('grep mysql config.properties');
    assert(!isDenied(r), `不应拦截 grep mysql`);
  });
}

// --- 规则 2: cc-sql 脚本 → allow ---
console.log('\n规则 2：cc-sql 脚本 → allow');
{
  test('tables.py 放行', () => {
    const r = runHook('python3 .claude/skills/cc-sql/tables.py --env test');
    assert(!isDenied(r), '应放行 tables.py');
  });

  test('columns.py 放行', () => {
    const r = runHook('python3 .claude/skills/cc-sql/columns.py --table users');
    assert(!isDenied(r), '应放行 columns.py');
  });
}

// --- 规则 3: query.py + DML/DDL → deny ---
console.log('\n规则 3：query.py DML/DDL 检测');
{
  test('query.py SELECT 放行', () => {
    const r = runHook('python3 .claude/skills/cc-sql/query.py "SELECT id FROM users LIMIT 10"');
    assert(!isDenied(r), '应放行 SELECT');
  });

  test('query.py INSERT 拦截', () => {
    const r = runHook('python3 .claude/skills/cc-sql/query.py "INSERT INTO users VALUES (1)"');
    assert(isDenied(r), '应拦截 INSERT');
    assert(getDenyReason(r).includes('INSERT'), '拒绝原因应提及 INSERT');
  });

  test('query.py DROP 拦截', () => {
    const r = runHook('python3 .claude/skills/cc-sql/query.py "DROP TABLE users"');
    assert(isDenied(r), '应拦截 DROP');
  });

  test('query.py DELETE 拦截', () => {
    const r = runHook('python3 .claude/skills/cc-sql/query.py "DELETE FROM users WHERE id=1"');
    assert(isDenied(r), '应拦截 DELETE');
  });

  test('query.py 带 flag 的 SELECT 放行', () => {
    const r = runHook('python3 .claude/skills/cc-sql/query.py --env prod --no-index-check "SELECT count(*) FROM orders"');
    assert(!isDenied(r), '应放行带 flag 的 SELECT');
  });
}

// --- 规则 4: 非 SQL 命令 → allow（P0 回归测试）---
console.log('\n规则 4：非 SQL 命令 → allow（P0 回归）');
{
  test('cp 命令放行', () => {
    const r = runHook('cp "/path/to/file.md" "/path/to/file.md.bak"');
    assert(!isDenied(r), `不应拦截 cp 命令`);
    assert.strictEqual(r.exitCode, 0, `退出码应为 0，实际 ${r.exitCode}`);
  });

  test('git status 放行', () => {
    const r = runHook('git status');
    assert(!isDenied(r), '不应拦截 git status');
  });

  test('ls 放行', () => {
    const r = runHook('ls -la');
    assert(!isDenied(r), '不应拦截 ls');
  });

  test('npm install 放行', () => {
    const r = runHook('npm install lodash');
    assert(!isDenied(r), '不应拦截 npm install');
  });

  test('空命令放行', () => {
    const r = runHook('');
    assert(!isDenied(r), '空命令应放行');
  });

  test('hook 不崩溃（退出码为 0）', () => {
    const r = runHook('echo hello');
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
