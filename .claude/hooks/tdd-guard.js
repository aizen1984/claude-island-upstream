#!/usr/bin/env node

/**
 * TDD Guard - PreToolUse Hook for Write|Edit
 *
 * 在 TDD 模式激活期间，检查被编辑的 Java 源文件是否有对应测试文件。
 * 建议模式：无测试文件时通过 additionalContext 提醒，建议先写测试。
 *
 * 激活条件：.claude/tdd-session-active 文件存在
 * 检查范围：`src/main/java/ ** / *.java（排除豁免路径)`
 * 豁免路径：dto/config/enums/entity/model/constants/common
 * 内容豁免：纯数据类（仅含 @Data/@Getter/@Setter 注解，无业务方法）
 * @assumption 模型不会主动在实现前编写测试
 */

const fs = require('fs');
const path = require('path');

const EXEMPT_DIRS = ['dto', 'config', 'enums', 'entity', 'model', 'constants', 'common'];

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
            // Parse error or unexpected input — silently allow
        }
    });
}

function check(data) {
    const toolInput = data.tool_input || {};
    const filePath = toolInput.file_path || toolInput.filePath || '';

    if (!filePath) return null;

    // 1. Check if TDD session is active
    const projectDir = process.env.CLAUDE_PROJECT_DIR || process.cwd();
    const sessionFile = path.join(projectDir, '.claude', 'tdd-session-active');

    if (!fs.existsSync(sessionFile)) return null;

    // 2. Check if file is a Java source file (not test)
    const normalized = filePath.replace(/\\/g, '/');
    if (!normalized.includes('src/main/java/') || !normalized.endsWith('.java')) return null;

    // 3. Check exempt directories
    const parts = normalized.split('/');
    for (const dir of EXEMPT_DIRS) {
        if (parts.includes(dir)) return null;
    }

    // 4. Derive test file path
    const testPath = normalized.replace('src/main/java/', 'src/test/java/').replace(/\.java$/, 'Test.java');
    const absoluteTestPath = path.isAbsolute(testPath) ? testPath : path.join(projectDir, testPath);

    // 5. Content-based exemption: pure data classes (@Data/@Getter/@Setter without business methods)
    //    对 Write：用 tool_input.content（待写入内容）
    //    对 Edit：读取当前文件并模拟替换后检查（反映编辑后的真实内容）
    const absoluteFilePath = path.isAbsolute(filePath) ? filePath : path.join(projectDir, filePath);
    const toolName = data.tool_name || '';
    let contentToCheck = '';

    if (toolName === 'Write' && toolInput.content) {
        contentToCheck = toolInput.content;
    } else {
        try {
            let fileContent = fs.readFileSync(absoluteFilePath, 'utf8');
            if (toolName === 'Edit' && toolInput.old_string && toolInput.new_string) {
                fileContent = fileContent.replace(toolInput.old_string, toolInput.new_string);
            }
            contentToCheck = fileContent;
        } catch (e) {
            // File not readable — proceed with check (will require test)
        }
    }

    if (contentToCheck) {
        const hasDataAnnotation = /@Data|@Getter|@Setter|@Builder|@NoArgsConstructor|@AllArgsConstructor/.test(contentToCheck);
        const hasBusinessMethod = /public\s+(?!(?:get|set|is|hashCode|equals|toString|builder|canEqual|of|from|valueOf)\b)\w+\s+\w+\s*\(/.test(contentToCheck);
        if (hasDataAnnotation && !hasBusinessMethod) return null; // Pure data class, exempt
    }

    // 6. Check if test file exists and has valid tests
    try {
        const testContent = fs.readFileSync(absoluteTestPath, 'utf8');
        const hasTestMethods = /@Test/.test(testContent);
        const isClassIgnored = /^\s*@Ignore\b/m.test(testContent) && /^\s*public\s+class\b/m.test(testContent);
        if (hasTestMethods && !isClassIgnored) return null; // Has real, non-ignored tests
    } catch (e) {
        // Test file doesn't exist, will block below
    }

    // 7. Block edit — force test-first
    const fileName = path.basename(filePath);
    const testFileName = path.basename(testPath);

    return {
        hookSpecificOutput: {
            hookEventName: 'PreToolUse',
            additionalContext: `🧪 TDD 提醒: ${fileName} 没有对应测试文件 ${testFileName}（或测试文件为空）。建议先写测试再写实现。\n路径: ${testPath}`,
        },
    };
}

main();
