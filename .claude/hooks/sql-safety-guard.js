#!/usr/bin/env node
/**
 * SQL Safety Guard - PreToolUse Hook for Bash
 * Fix: DIRECT_DB_CLIENTS → findDbClientInvocation() (2026-04-12)
 *
 * 防御两类场景：
 * 1. LLM 绕过 query.py 直接执行 mysql/psql/sqlite3 命令 → deny（必须通过 cc-sql）
 * 2. query.py 调用时轻量前置检查 SQL 参数 → 早期拦截 DML/DDL（security.py 的第二道防线）
 *
 * 不做的事：
 * - 不重复 security.py 的 AST 级别检查（sqlparse 比正则精确得多）
 * - 不检查非 SQL 相关的 Bash 命令（直接放行）
 *
 * 三层守护模型：
 *   L1: Claude Code allowed-tools (skill 级别权限)
 *   L2: security.py (sqlparse AST 检查) ← query.py 内部
 *   L3: 本 hook (正则前置拦截) ← 兜底，防绕过 query.py
 *
 * 挂载点: PreToolUse(Bash)
 */

const { readStdin } = require('../scripts/lib/utils');

// 直接数据库客户端名称（绕过 query.py = 绕过 security.py）
const DB_CLIENT_NAMES = ['mysql', 'psql', 'sqlite3', 'mongosh', 'mongo', 'redis-cli'];
// 命令前缀词（可出现在实际命令之前）
const CMD_PREFIX_WORDS = new Set(['sudo', 'env', 'nohup', 'time', 'nice', 'strace']);

// DML/DDL 关键词（在 query.py 参数中的早期检测）
const DML_DDL_PATTERN = /\b(INSERT|UPDATE|DELETE|DROP|TRUNCATE|ALTER|CREATE|REPLACE|RENAME|GRANT|REVOKE)\b/i;

// query.py 调用模式
const QUERY_PY_PATTERN = /python[23]?\s+.*cc-sql\/query\.py/;

// 其他 cc-sql 脚本（tables.py, columns.py, describe.py, cache.py, databases.py）
const CC_SQL_SCRIPT_PATTERN = /python[23]?\s+.*cc-sql\/(tables|columns|describe|databases|cache)\.py/;

function deny(reason) {
  process.stderr.write(`[sql-safety-guard] DENY: ${reason}\n`);
  process.stdout.write(JSON.stringify({
    hookSpecificOutput: {
      hookEventName: 'PreToolUse',
      permissionDecision: 'deny',
      permissionDecisionReason: reason,
    },
  }));
}

function allow() {
  // 不输出 = 不干预
}

/**
 * 检测命令中是否有数据库客户端调用（在"命令位置"，非参数文本中）
 * 将命令按 |, &&, ||, ; 分段，检查每段的第一个非前缀词是否是 DB 客户端
 * 这样 `git commit -m "...mysql..."` 不会误报，但 `cat foo | mysql` 会被拦截
 */
function findDbClientInvocation(command) {
  const segments = command.split(/[|;&]+/).map(s => s.trim());
  for (const seg of segments) {
    if (!seg) continue;
    const words = seg.split(/\s+/);
    let i = 0;
    // 跳过前缀命令（sudo, env 等）
    while (i < words.length && CMD_PREFIX_WORDS.has(words[i])) i++;
    const cmdName = (words[i] || '').replace(/^.*\//, ''); // 去掉路径前缀如 /usr/bin/mysql → mysql
    if (DB_CLIENT_NAMES.includes(cmdName)) return cmdName;
  }
  return null;
}

function extractSqlArg(command) {
  // query.py 的 SQL 来源：
  // 1. 位置参数: query.py "SELECT ..."
  // 2. --file: query.py --file xxx.sql（hook 无法检查文件内容，跳过）
  // 3. stdin pipe: echo "SELECT ..." | query.py（hook 无法检查，跳过）

  // 提取引号内的 SQL（位置参数）— [\w-]+ 匹配含连字符的 flag 如 --no-index-check
  const quoted = command.match(/query\.py\s+(?:--[\w-]+(?:\s+\S+)?\s+)*["']([^"']+)["']/);
  if (quoted) return quoted[1];

  // 提取无引号的 SQL（位置参数，取 query.py 后最后一个非 flag 参数）
  const unquoted = command.match(/query\.py\s+(?:--[\w-]+(?:\s+\S+)?\s+)*(\S+.*)/);
  if (unquoted) {
    const rest = unquoted[1];
    if (!rest.startsWith('-')) return rest;
  }

  return null;
}

async function main() {
  const input = await readStdin();
  const toolInput = input.tool_input || {};
  const command = toolInput.command || '';

  if (!command) return allow();

  // ━━━ 规则 1: 直接数据库客户端命令 → deny ━━━
  const dbClient = findDbClientInvocation(command);
  if (dbClient) {
    return deny(
      `禁止直接使用 ${dbClient} 命令访问数据库。` +
      `请通过 cc-sql skill 执行查询: python .claude/skills/cc-sql/query.py "your SQL"。` +
      `cc-sql 内置安全校验（只读、禁 SELECT *、自动 LIMIT、聚合需 WHERE）。`
    );
  }

  // ━━━ 规则 2: 其他 cc-sql 工具脚本 → 直接放行 ━━━
  if (CC_SQL_SCRIPT_PATTERN.test(command)) return allow();

  // ━━━ 规则 3: query.py 调用 → 轻量前置检查 ━━━
  if (QUERY_PY_PATTERN.test(command)) {
    const sql = extractSqlArg(command);
    if (sql && DML_DDL_PATTERN.test(sql)) {
      const keyword = sql.match(DML_DDL_PATTERN)[1].toUpperCase();
      return deny(
        `query.py 参数中检测到 ${keyword} 关键词，cc-sql 仅允许 SELECT/SHOW/DESCRIBE/EXPLAIN。` +
        `（注：即使此 hook 放行，query.py 内部的 security.py 也会阻断此操作）`
      );
    }
    // SQL 参数看起来合规，放行给 security.py 做精确检查
    return allow();
  }

  // ━━━ 非 SQL 相关命令 → 放行 ━━━
  return allow();
}

main();
