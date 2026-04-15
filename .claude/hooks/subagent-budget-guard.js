#!/usr/bin/env node

/**
 * Subagent Budget Guard - PreToolUse Hook for Agent
 *
 * 在 Agent 工具调用前进行预算验证：
 * 1. Prompt 长度检查（超长 → additionalContext 提醒精简）
 * 2. Description 完整性检查（缺失 → 提醒补充）
 * 3. 可观测性日志输出
 *
 * 策略：纯建议模式（additionalContext），不阻断。
 * 挂载点：PreToolUse(Agent)
 * @assumption 模型可能生成过长的 subagent prompt 或遗漏 description
 */

const MAX_PROMPT_CHARS = 8000;
const WARN_PROMPT_CHARS = 5000;

function main() {
    let input = '';

    process.stdin.setEncoding('utf8');
    process.stdin.on('data', (chunk) => {
        input += chunk;
    });
    process.stdin.on('end', () => {
        try {
            const data = JSON.parse(input);
            const result = check(data);
            if (result) {
                process.stdout.write(JSON.stringify(result));
            }
        } catch (e) {
            // Parse error — silently allow
        }
    });
}

function check(data) {
    const toolInput = data.tool_input || {};
    const prompt = toolInput.prompt || '';
    const description = toolInput.description || '';
    const subagentType = toolInput.subagent_type || 'general-purpose';
    const model = toolInput.model || 'inherited';

    const warnings = [];

    // 1. Prompt length check
    if (prompt.length > MAX_PROMPT_CHARS) {
        warnings.push(
            `⚠️ Subagent prompt 过长 (${prompt.length} chars > ${MAX_PROMPT_CHARS})。` +
            `长 prompt 浪费 subagent 上下文预算，考虑：(1) 精简到核心指令 (2) 用文件路径引用替代内联内容 (3) 拆分为多个小 agent。`
        );
    } else if (prompt.length > WARN_PROMPT_CHARS) {
        // Log but don't warn
        log(`📊 Agent prompt: ${prompt.length} chars (${subagentType})`);
    }

    // 2. Description completeness check
    if (!description || description.trim().length < 3) {
        warnings.push(
            `⚠️ Agent 缺少 description 参数。请补充 3-5 词概要（如 "分析接口调用链"），用于可观测性追踪。`
        );
    }

    // 3. Observability log (always)
    log(`🤖 Agent dispatch: type=${subagentType} | model=${model} | prompt=${prompt.length}c | desc="${description}"`);

    if (warnings.length > 0) {
        return {
            hookSpecificOutput: {
                hookEventName: "PreToolUse",
                additionalContext: warnings.join('\n')
            }
        };
    }

    return null;
}

function log(message) {
    console.error(message);
}

main();
