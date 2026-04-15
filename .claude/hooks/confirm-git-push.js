#!/usr/bin/env node
/**
 * Confirm git push operations
 *
 * Cross-platform (Windows, macOS, Linux)
 *
 * Adapted from: everything-claude-code hooks configuration
 *
 * Blocks dangerous push operations:
 * - Force push → exit(2) 阻断（始终，无白名单）
 * - Push to main/master → exit(2) 阻断（白名单仓库除外）
 *
 * 白名单机制：个人仓库允许 push main，协作仓库保持拦截。
 * 通过命令中的 cd 路径或 process.cwd() 判断仓库归属。
 *
 * @assumption 模型可能在未经用户确认的情况下 force push 或推送到 main
 */

const { readStdin, log } = require('../scripts/lib/utils');

// ━━━ 白名单配置 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// 这些路径下的仓库允许 push to main/master
// 在此添加个人仓库路径（前缀匹配）
const MAIN_PUSH_WHITELIST = [
  '/Users/caochen/IdeaProjects/ai/my_claude',
  '/Users/caochen/tools/shuhe-kb',
];
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

/**
 * 从命令字符串中提取目标目录
 * 优先解析 cd 路径，回退到 process.cwd()
 */
function resolveTargetDir(command) {
  // 1. 命令中有 cd → 用 cd 的路径
  const cdMatch = command.match(/cd\s+["']?([^"'&;]+)/);
  if (cdMatch) return cdMatch[1].trim();
  // 2. 没有 cd → 用 CLAUDE_PROJECT_DIR（Claude Code 保证设置为项目根）
  // 注：process.cwd() 是 hook 子进程的 cwd，不等于 Bash shell 的 cwd
  return process.env.CLAUDE_PROJECT_DIR || process.cwd();
}

function isWhitelisted(command) {
  const targetDir = resolveTargetDir(command);
  return MAIN_PUSH_WHITELIST.some(dir => targetDir.startsWith(dir));
}

async function main() {
  const input = await readStdin();

  // Get command from tool input
  const toolInput = input.tool_input || {};
  const command = toolInput.command || '';

  // Only check git push commands
  if (!/git\s+push/i.test(command)) {
    process.exit(0);
  }

  // Check for force push → 阻断（始终，无白名单）
  if (/--force\b|(?:^|\s)-[a-zA-Z]*f/i.test(command)) {
    const reason = `[Hook] ⛔ BLOCKED: Force push detected! Command: ${command}`;
    log(reason);
    process.exit(2);
  }

  // Check for push to main/master → 阻断（白名单仓库除外）
  if (/\b(main|master)\b/i.test(command)) {
    if (isWhitelisted(command)) {
      log(`[Hook] ✅ Push to main allowed (whitelisted repo: ${resolveTargetDir(command)})`);
    } else {
      const reason = `[Hook] ⛔ BLOCKED: Direct push to main/master is not allowed. Command: ${command}. Use a PR instead, or add repo to MAIN_PUSH_WHITELIST in confirm-git-push.js.`;
      log(reason);
      process.exit(2);
    }
  }

  // Normal push - gentle reminder
  log(`[Hook] Git push: ${command}`);
  log(`[Hook] Ensure all changes have been reviewed.`);

  process.exit(0);
}

main().catch(err => {
  console.error('[GitPush] Error:', err.message);
  process.exit(0);
});
