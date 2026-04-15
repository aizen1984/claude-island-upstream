#!/usr/bin/env node
/**
 * TaskCompleted Hook - Agent Teams 任务完成质量门控
 *
 * 触发时机: 任务即将被标记为 completed 时
 * 行为:
 *   - exit(0): 允许任务标记完成
 *   - exit(2): 阻止完成，将 stdout 内容作为反馈发回（要求补充工作）
 *
 * 策略: 基本质量检查提醒，确保任务产出符合规范
 * @assumption 任务完成事件需要触发后续状态更新
 */

const { readStdin, log } = require('../scripts/lib/utils');

async function main() {
  const input = await readStdin();

  const taskId = input.task_id || 'unknown';
  const taskTitle = input.task_title || input.task_subject || '';
  const agentName = input.agent_name || 'unknown';

  log(`[task-completed] 队友 "${agentName}" 标记任务完成: ${taskTitle || taskId}`);

  // 非代码任务（分析、查询、复验、汇总等）直接放行
  const nonCodeKeywords = ['复验', '补充', '汇总', '分析', '查询', '验证', '边际', '调研', '梳理', '排查', '总结', '审查', '对比'];
  const isNonCodeTask = nonCodeKeywords.some(kw => taskTitle.includes(kw));

  if (isNonCodeTask) {
    log(`[task-completed] 非代码任务，直接放行: ${taskTitle}`);
    process.exit(0);
  }

  // 代码开发任务：advisory 提醒（不阻断，避免死循环）
  log([
    `[task-completed] 质量提醒 - "${taskTitle}":`,
    '  1. 代码是否符合项目规范（分层注入、事务注解、异常处理）',
    '  2. 是否有编译错误',
    '  3. 变更文件是否已保存',
  ].join('\n'));
  process.exit(0);
}

main().catch(err => {
  log(`[task-completed] Error: ${err.message}`);
  process.exit(0);
});
