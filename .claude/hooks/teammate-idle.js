#!/usr/bin/env node
/**
 * TeammateIdle Hook - Agent Teams 队友闲置处理
 *
 * 触发时机: 队友完成当前工作即将闲置时
 * 行为:
 *   - exit(0): 允许队友闲置（所有任务已完成）
 *   - exit(2): 发送反馈让队友继续工作（stdout 内容作为反馈）
 *
 * 策略: "提醒一次然后放行"
 *   - 第一次闲置 → exit(2) 提醒检查任务列表
 *   - 第二次闲置 → exit(0) 放行，等 lead 调度
 *   - 计数器按 agent 隔离，互不干扰
 * @assumption 队友空闲时不会主动通知 Lead
 */

const fs = require('fs');
const path = require('path');
const os = require('os');
const { readStdin, log } = require('../scripts/lib/utils');

function getCounterPath(teamName) {
  return path.join(os.tmpdir(), `claude-idle-${teamName || 'default'}.json`);
}

function loadCounters(filePath) {
  try {
    return JSON.parse(fs.readFileSync(filePath, 'utf8'));
  } catch {
    return {};
  }
}

function saveCounters(filePath, data) {
  fs.writeFileSync(filePath, JSON.stringify(data));
}

async function main() {
  const input = await readStdin();

  const agentName = input.agent_name || 'unknown';
  const teamName = input.team_name || '';

  const counterPath = getCounterPath(teamName);
  const counters = loadCounters(counterPath);

  const count = (counters[agentName] || 0) + 1;
  counters[agentName] = count;
  saveCounters(counterPath, counters);

  log(`[teammate-idle] 队友 "${agentName}" 第 ${count} 次闲置`);

  if (count <= 1) {
    // 第一次闲置：提醒检查任务列表
    console.log([
      '你当前没有活跃任务。请执行以下步骤：',
      '1. 检查共享任务列表（TaskList），查看是否有 pending 状态的未认领任务',
      '2. 如果有未认领任务，认领并执行',
      '3. 如果没有更多任务，向 lead 报告完成情况'
    ].join('\n'));
    process.exit(2);
  } else {
    // 第二次及以后：放行，交给 lead 调度
    log(`[teammate-idle] 队友 "${agentName}" 已提醒过，允许闲置`);
    process.exit(0);
  }
}

main().catch(err => {
  log(`[teammate-idle] Error: ${err.message}`);
  process.exit(0);
});
