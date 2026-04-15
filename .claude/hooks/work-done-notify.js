#!/usr/bin/env node
/**
 * Stop hook: Claude Code 工作完成时发送通知
 * 始终 exit(0)，通知失败不阻塞
 * @assumption 长任务完成后用户可能不在终端前
 */

const { readStdin, log } = require('../scripts/lib/utils');
const { execFile } = require('child_process');
const path = require('path');

async function main() {
  const input = await readStdin();

  // Ralph 循环中不通知（非真正完成）
  if (input.stop_hook_active) {
    return;
  }

  // 无实质工作不通知
  const summary = (input.transcript_summary || '').trim();
  if (!summary) {
    return;
  }

  // 截取前 100 字符作为通知内容
  const body = summary.length > 100 ? summary.slice(0, 100) + '…' : summary;

  const scriptPath = path.resolve(__dirname, '../scripts/notify.sh');
  await new Promise((resolve) => {
    execFile('bash', [scriptPath, 'Claude Code 完成', body], (err) => {
      if (err) {
        log(`[work-done-notify] 通知失败: ${err.message}`);
      }
      resolve();
    });
  });
}

main().catch(() => {}).finally(() => process.exit(0));
