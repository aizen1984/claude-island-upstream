#!/usr/bin/env node
/**
 * Code Quality Guard - PreToolUse Hook for Edit|Write (多语言版)
 *
 * 基于 java-quality-guard.js 扩展，支持 Java / Python / Frontend (TS/TSX/Vue/JSX/JS)。
 * 通过 ROUTERS 按文件扩展名路由到对应语言的检查器。
 *
 * 阻断策略: error/warning → deny | info → allow + additionalContext
 * 防循环: 同文件连续 block 3 次后降级为 warn
 * 挂载点: PreToolUse(Edit|Write)
 */

const fs = require('fs');
const path = require('path');
const { readStdin, log } = require('../scripts/lib/utils');

// ============================================================================
// 公共工具函数
// ============================================================================

function stripStringAndComment(line) {
  let result = line.replace(/"(?:[^"\\]|\\.)*"/g, '""');
  result = result.replace(/'(?:[^'\\]|\\.)*'/g, "''");
  result = result.replace(/\/\/.*$/, '');
  return result;
}

function countBracesDelta(line) {
  const clean = stripStringAndComment(line);
  let delta = 0;
  for (const ch of clean) {
    if (ch === '{') delta++;
    if (ch === '}') delta--;
  }
  return delta;
}

// ============================================================================
// 路由器 — 按文件扩展名分发到对应语言检查器
// ============================================================================

const ROUTERS = {
  '.java': checkJava,
  '.py': checkPython,
  '.ts': checkFrontend,
  '.tsx': checkFrontend,
  '.vue': checkFrontend,
  '.jsx': checkFrontend,
  '.js': checkFrontend,
};

// ============================================================================
// PreToolUse 内容提取 + 变更范围检测（共用，语言无关）
// ============================================================================

const BLOCK_COUNT_DIR = '/tmp/code-quality-guard';

function extractContent(input) {
  const toolName = input.tool_name || '';
  const toolInput = input.tool_input || {};

  if (toolName === 'Write') {
    return { content: toolInput.content || '', changedLines: null };
  }

  if (toolName === 'Edit') {
    const filePath = toolInput.file_path || toolInput.filePath || '';
    const oldString = toolInput.old_string;
    const newString = toolInput.new_string;
    if (!filePath || !oldString || !newString) return null;

    let currentContent;
    try { currentContent = fs.readFileSync(filePath, 'utf8'); } catch { return null; }

    const idx = currentContent.indexOf(oldString);
    if (idx === -1) return null;

    const merged = currentContent.substring(0, idx) + newString + currentContent.substring(idx + oldString.length);
    const startLine = currentContent.substring(0, idx).split('\n').length;
    const newLineCount = newString.split('\n').length;
    const endLine = startLine + newLineCount - 1;

    const strictChangedLines = new Set();
    for (let i = startLine; i <= endLine; i++) strictChangedLines.add(i);

    const changedLines = new Set();
    for (let i = Math.max(1, startLine - 5); i <= endLine + 3; i++) changedLines.add(i);

    return { content: merged, changedLines, strictChangedLines, originalContent: currentContent };
  }
  return null;
}

function filterByChangeRange(violations, changedLines, originalViolationRuleIds, strictChangedLines) {
  if (!changedLines) return violations;
  return violations.filter(v => {
    if (v.endLine && originalViolationRuleIds && originalViolationRuleIds.has(v.ruleId)) return false;
    if (v.endLine) {
      const lines = strictChangedLines || changedLines;
      for (let i = v.line; i <= v.endLine; i++) { if (lines.has(i)) return true; }
      return false;
    }
    return changedLines.has(v.line);
  });
}

// ============================================================================
// 防循环机制（共用）
// ============================================================================

const MAX_CONSECUTIVE_BLOCKS = 3;

function getBlockCountFile(filePath) {
  return path.join(BLOCK_COUNT_DIR, filePath.replace(/[/\\:]/g, '_'));
}

function simpleHash(content) {
  let h = 0;
  for (let i = 0; i < content.length; i++) h = ((h << 5) - h + content.charCodeAt(i)) | 0;
  return h.toString(36);
}

function getBlockCount(filePath, contentHash) {
  try {
    const data = JSON.parse(fs.readFileSync(getBlockCountFile(filePath), 'utf8'));
    if (Date.now() - data.ts > 5 * 60 * 1000) return 0;
    if (data.hash !== contentHash) return 0;
    return data.count || 0;
  } catch { return 0; }
}

function incrementBlockCount(filePath, contentHash, currentCount) {
  try {
    if (!fs.existsSync(BLOCK_COUNT_DIR)) fs.mkdirSync(BLOCK_COUNT_DIR, { recursive: true });
    fs.writeFileSync(getBlockCountFile(filePath), JSON.stringify({ count: currentCount + 1, ts: Date.now(), hash: contentHash }));
  } catch { /* ignore */ }
}

function resetBlockCount(filePath) {
  try { const f = getBlockCountFile(filePath); if (fs.existsSync(f)) fs.unlinkSync(f); } catch { /* ignore */ }
}

// ============================================================================
// ========= JAVA 规则（8 条：5 核心 + 3 P0 安全）=========
// ============================================================================

const JAVA_RULES = [
  { id: 'empty-catch', name: '空 catch 块', severity: 'error', check: checkEmptyCatch },
  { id: 'catch-generic-exception', name: '捕获泛型异常', severity: 'warning', check: checkGenericException },
  { id: 'system-out', name: '使用 System.out/err', severity: 'warning', check: checkSystemOut },
  { id: 'hard-coded-ip-url', name: '硬编码 IP/URL', severity: 'warning', check: checkHardCodedIpUrl },
  { id: 'method-too-long', name: '方法体过长', severity: 'warning', check: checkMethodTooLong, threshold: 80 },
  { id: 'sql-string-concat', name: 'SQL 拼接注入风险', severity: 'error', check: checkSqlStringConcat },
  { id: 'sensitive-log', name: '敏感字段写入日志', severity: 'error', check: checkSensitiveLog },
  { id: 'transaction-no-rollback', name: '@Transactional 缺 rollbackFor', severity: 'error', check: checkTransactionNoRollback },
];

function checkEmptyCatch(lines) {
  const violations = [];
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim();
    if (line.startsWith('//') || line.startsWith('*')) continue;
    if (/\bcatch\s*\(/.test(line)) {
      let hasContent = false;
      for (let j = i + 1; j < Math.min(i + 5, lines.length); j++) {
        const next = lines[j].trim();
        if (next === '}') break;
        if (next === '{' || next === '' || next.startsWith('//')) continue;
        hasContent = true; break;
      }
      if (!hasContent) violations.push({ line: i + 1, message: '空 catch 块，至少应记录日志' });
    }
  }
  return violations;
}

function checkGenericException(lines) {
  const violations = [];
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim();
    if (line.startsWith('//') || line.startsWith('*')) continue;
    if (/\bcatch\s*\([^)]*\b(Exception|Throwable|RuntimeException)\b/.test(line)) {
      const exType = line.match(/\b(Exception|Throwable|RuntimeException)\b/)?.[1];
      violations.push({ line: i + 1, message: `捕获了泛型异常 ${exType}，建议捕获具体异常类型` });
    }
  }
  return violations;
}

function checkSystemOut(lines) {
  const violations = [];
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim();
    if (line.startsWith('//') || line.startsWith('*')) continue;
    if (/System\.(out|err)\.(print|println|printf)/.test(line)) {
      violations.push({ line: i + 1, message: '使用了 System.out/err，应使用 SLF4J Logger' });
    }
  }
  return violations;
}

function checkHardCodedIpUrl(lines, filePath) {
  const violations = [];
  if (path.basename(filePath).match(/Test\.java$|Tests\.java$|IT\.java$/)) return violations;
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim();
    if (line.startsWith('//') || line.startsWith('*') || /\bstatic\s+final\b/.test(line)) continue;
    if (/"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}"/.test(line) && !/127\.0\.0\.1|0\.0\.0\.0|localhost/.test(line)) {
      violations.push({ line: i + 1, message: '硬编码 IP 地址，应使用配置中心' });
    }
    if (/"https?:\/\/[^"]+/.test(line) && !/@.*Value|@.*Url|@.*ConfigurationProperties|swagger|api-docs/.test(line)) {
      violations.push({ line: i + 1, message: '硬编码 URL，应使用配置中心或常量' });
    }
  }
  return violations;
}

function checkMethodTooLong(lines, _filePath, rule) {
  const violations = [];
  let methodStart = -1, methodName = '', braceDepth = 0, inMethod = false;
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim();
    const m = line.match(/^(?:(?:public|private|protected)\s+)?(?:static\s+)?(?:final\s+)?(?:synchronized\s+)?(?:\w+(?:<[^>]*>)?(?:\[\])*\s+)+(\w+)\s*\(/);
    if (m && !line.includes(';') && !line.startsWith('//') && !line.startsWith('*')) {
      methodStart = i; methodName = m[1]; braceDepth = 0; inMethod = false;
    }
    if (methodStart >= 0) {
      const delta = countBracesDelta(line);
      if (delta > 0 && !inMethod) inMethod = true;
      braceDepth += delta;
      if (inMethod && braceDepth === 0) {
        const length = i - methodStart + 1;
        if (length > rule.threshold) {
          violations.push({ line: methodStart + 1, endLine: i + 1, message: `方法 ${methodName}() 共 ${length} 行，超过 ${rule.threshold} 行阈值，建议拆分` });
        }
        methodStart = -1; inMethod = false;
      }
    }
  }
  return violations;
}

function checkSqlStringConcat(lines) {
  const violations = [];
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim();
    if (line.startsWith('//') || line.startsWith('*') || line.startsWith('/*')) continue;
    if (/"\s*(SELECT|UPDATE|DELETE|INSERT)\b[^"]*"\s*\+/.test(line) ||
        /\+\s*"\s*(SELECT|UPDATE|DELETE|INSERT)\b/.test(line) ||
        /"\s*(WHERE|AND|OR)\s+\w+\s*=\s*"\s*\+/.test(line)) {
      if (/\bstatic\s+final\b/.test(line)) continue;
      if (/^"[^"]*"\s*\+\s*"[^"]*"/.test(line.replace(/\s+/g, ''))) continue;
      violations.push({ line: i + 1, message: 'SQL 字符串拼接有注入风险，应使用参数化查询 #{} 或 Condition API' });
    }
  }
  return violations;
}

function checkSensitiveLog(lines) {
  const violations = [];
  const SENSITIVE = /\b(password|passwd|idCard|idNo|identityNo|mobile|phoneNo|cellphone|cardNo|bankCard|secret|secretKey|accessKey|accessToken|privateKey|creditCard)\b/i;
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim();
    if (line.startsWith('//') || line.startsWith('*')) continue;
    if (/\blog\.(info|debug|warn|error|trace)\s*\(/.test(line)) {
      const stripped = line.replace(/"(?:[^"\\]|\\.)*"/g, '');
      const m = stripped.match(SENSITIVE);
      if (m) violations.push({ line: i + 1, message: `日志中包含敏感字段 ${m[1]}，存在数据泄露风险，应脱敏后打印` });
    }
  }
  return violations;
}

function checkTransactionNoRollback(lines) {
  const violations = [];
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim();
    if (/^@Transactional\b/.test(line)) {
      let fullAnnotation = line;
      if (line.includes('(') && !line.includes(')')) {
        for (let j = i + 1; j < Math.min(i + 5, lines.length); j++) {
          fullAnnotation += ' ' + lines[j].trim();
          if (lines[j].includes(')')) break;
        }
      }
      if (!fullAnnotation.includes('rollbackFor')) {
        if (/readOnly\s*=\s*true/.test(fullAnnotation)) continue;
        if (/propagation\s*=\s*Propagation\.(NOT_SUPPORTED|NEVER|SUPPORTS)/.test(fullAnnotation)) continue;
        violations.push({ line: i + 1, message: '@Transactional 缺少 rollbackFor = Exception.class，默认只回滚 RuntimeException' });
      }
    }
  }
  return violations;
}

function checkJava(lines, filePath) {
  const allViolations = [];
  for (const rule of JAVA_RULES) {
    try {
      for (const v of rule.check(lines, filePath, rule)) {
        allViolations.push({ ruleId: rule.id, ruleName: rule.name, severity: rule.severity, ...v });
      }
    } catch (err) { log(`[code-quality] Java rule ${rule.id} error: ${err.message}`); }
  }
  return allViolations;
}

// ============================================================================
// ========= PYTHON 规则（8 条：5 安全 + 3 质量）=========
// ============================================================================

const PYTHON_RULES = [
  { id: 'py-eval-exec', name: 'eval/exec 使用', severity: 'error', check: checkPyEvalExec },
  { id: 'py-pickle-loads', name: 'pickle 反序列化', severity: 'error', check: checkPyPickleLoads },
  { id: 'py-yaml-unsafe', name: 'yaml.load 不安全', severity: 'error', check: checkPyYamlUnsafe },
  { id: 'py-subprocess-shell', name: 'subprocess shell=True', severity: 'error', check: checkPySubprocessShell },
  { id: 'py-sql-fstring', name: 'f-string SQL 注入', severity: 'error', check: checkPySqlFstring },
  { id: 'py-bare-except', name: '裸 except 或静默吞异常', severity: 'error', check: checkPyBareExcept },
  { id: 'py-mutable-default', name: '可变默认参数', severity: 'warning', check: checkPyMutableDefault },
  { id: 'py-print', name: '生产代码使用 print', severity: 'warning', check: checkPyPrint },
];

function checkPyEvalExec(lines, filePath) {
  const violations = [];
  if (isTestFile(filePath, 'py')) return violations;
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const trimmed = line.trim();
    if (trimmed.startsWith('#')) continue;
    if (/\beval\s*\(/.test(trimmed) && !/ast\.literal_eval/.test(trimmed)) {
      violations.push({ line: i + 1, message: '使用了 eval()，存在代码注入风险。应使用 ast.literal_eval() 或白名单解析' });
    }
    if (/\bexec\s*\(/.test(trimmed)) {
      violations.push({ line: i + 1, message: '使用了 exec()，存在代码注入风险。应避免动态执行代码' });
    }
  }
  return violations;
}

function checkPyPickleLoads(lines) {
  const violations = [];
  for (let i = 0; i < lines.length; i++) {
    const trimmed = lines[i].trim();
    if (trimmed.startsWith('#')) continue;
    if (/\bpickle\.(loads?|Unpickler)\s*\(/.test(trimmed)) {
      violations.push({ line: i + 1, message: '使用了 pickle 反序列化，存在远程代码执行（RCE）风险。应使用 json.loads() 或 msgpack' });
    }
  }
  return violations;
}

function checkPyYamlUnsafe(lines) {
  const violations = [];
  for (let i = 0; i < lines.length; i++) {
    const trimmed = lines[i].trim();
    if (trimmed.startsWith('#')) continue;
    if (/\byaml\.load\s*\(/.test(trimmed) && !/safe_load|SafeLoader|FullLoader/.test(trimmed)) {
      violations.push({ line: i + 1, message: 'yaml.load() 未指定 SafeLoader，存在 RCE 风险。应使用 yaml.safe_load()' });
    }
  }
  return violations;
}

function checkPySubprocessShell(lines) {
  const violations = [];
  let pendingSubprocess = -1; // 多行调用：记录 subprocess 起始行
  for (let i = 0; i < lines.length; i++) {
    const trimmed = lines[i].trim();
    if (trimmed.startsWith('#')) continue;
    // 单行模式
    if (/\bsubprocess\.\w+\(/.test(trimmed) && /shell\s*=\s*True/.test(trimmed)) {
      violations.push({ line: i + 1, message: 'subprocess 使用 shell=True，存在命令注入风险。应使用参数列表 + shell=False' });
      pendingSubprocess = -1;
      continue;
    }
    // 多行模式：记录 subprocess 调用起始
    if (/\bsubprocess\.\w+\(/.test(trimmed) && !trimmed.includes(')')) {
      pendingSubprocess = i;
    }
    // 多行模式：在后续行中查找 shell=True
    if (pendingSubprocess >= 0 && pendingSubprocess !== i) {
      if (/shell\s*=\s*True/.test(trimmed)) {
        violations.push({ line: pendingSubprocess + 1, message: 'subprocess 使用 shell=True（多行调用），存在命令注入风险。应使用参数列表 + shell=False' });
        pendingSubprocess = -1;
      }
      if (/\)/.test(trimmed)) pendingSubprocess = -1; // 调用结束
    }
    if (/\bos\.(system|popen)\s*\(/.test(trimmed)) {
      violations.push({ line: i + 1, message: '使用了 os.system/popen，无法安全传参。应使用 subprocess.run() + 参数列表' });
    }
  }
  return violations;
}

function checkPySqlFstring(lines) {
  const violations = [];
  for (let i = 0; i < lines.length; i++) {
    const trimmed = lines[i].trim();
    if (trimmed.startsWith('#')) continue;
    if (/^f["']/.test(trimmed) || /[^a-zA-Z]f["']/.test(trimmed)) {
      const hasSqlKeyword = /\b(SELECT|INSERT|UPDATE|DELETE|WHERE|FROM)\b/i.test(trimmed)
                           || (/\bJOIN\b/i.test(trimmed) && !/\.join\b/i.test(trimmed));
      if (hasSqlKeyword && /\{[^}]+\}/.test(trimmed)) {
        violations.push({ line: i + 1, message: 'f-string 拼接 SQL，存在注入风险。应使用参数化查询 execute("... %s", (val,))' });
      }
    }
    if (/["'].*\b(SELECT|INSERT|UPDATE|DELETE)\b.*["']\s*%\s/.test(trimmed) && !/\(%s/.test(trimmed)) {
      violations.push({ line: i + 1, message: '% 格式化拼接 SQL，存在注入风险。应使用参数化查询' });
    }
  }
  return violations;
}

function checkPyBareExcept(lines) {
  const violations = [];
  for (let i = 0; i < lines.length; i++) {
    const trimmed = lines[i].trim();
    if (trimmed.startsWith('#')) continue;
    if (/^except\s*:/.test(trimmed)) {
      violations.push({ line: i + 1, message: '裸 except: 会吞掉 KeyboardInterrupt/SystemExit。应使用 except Exception as e:' });
    }
    if (/^except\s+BaseException\s*:/.test(trimmed)) {
      violations.push({ line: i + 1, message: 'except BaseException 会捕获 SystemExit 等。应使用 except Exception as e:' });
    }
    if (/^except\s+(Exception|[A-Z]\w+Error|[A-Z]\w+Exception)\s*(as\s+\w+)?\s*:/.test(trimmed)) {
      let hasContent = false;
      let breakReason = 'empty'; // 'empty' = 空块, 'pass' = 显式 pass
      for (let j = i + 1; j < Math.min(i + 5, lines.length); j++) {
        const next = lines[j].trim();
        if (next === '' || next.startsWith('#')) continue;
        if (/^\S/.test(lines[j])) break; // 退缩进，except 块结束
        if (next === 'pass') { breakReason = 'pass'; break; }
        hasContent = true; break;
      }
      if (!hasContent) {
        const exceptType = trimmed.split(':')[0];
        const msg = breakReason === 'pass'
          ? `${exceptType}: pass 静默吞掉异常。至少应 logger.exception() + 考虑 raise`
          : `${exceptType}: 空 except 块静默吞掉异常。应添加日志记录或 raise`;
        violations.push({ line: i + 1, message: msg });
      }
    }
  }
  return violations;
}

function checkPyMutableDefault(lines) {
  const violations = [];
  for (let i = 0; i < lines.length; i++) {
    const trimmed = lines[i].trim();
    if (trimmed.startsWith('#')) continue;
    if (/\bdef\s+\w+\s*\(/.test(trimmed)) {
      // 逐个参数检查可变默认值（支持 def foo(a=None, items=[]) 多参数）
      const params = trimmed.replace(/^def\s+\w+\s*\(/, '').replace(/\)\s*[-:].*$/, '');
      if (/=\s*(\[\s*\]|\{\s*\}|set\s*\(\s*\))/.test(params)) {
        violations.push({ line: i + 1, message: '可变默认参数（list/dict/set），所有调用共享同一对象。应使用 None 默认值' });
      }
    }
  }
  return violations;
}

function checkPyPrint(lines, filePath) {
  const violations = [];
  if (isTestFile(filePath, 'py')) return violations;
  const baseName = path.basename(filePath);
  if (baseName === 'manage.py' || baseName.startsWith('conftest')) return violations;
  // CLI tools in scripts/ or bin/ legitimately use print() for terminal output
  if (/[/\\](scripts|bin)[/\\]/.test(filePath)) return violations;
  // CLI viewer tools in ~/.claude/hooks/ (view-*.py are alias-invoked, terminal output is the product)
  if (/[/\\]\.claude[/\\]hooks[/\\]view-[^/\\]+\.py$/.test(filePath)) return violations;
  for (let i = 0; i < lines.length; i++) {
    const trimmed = lines[i].trim();
    if (trimmed.startsWith('#')) continue;
    if (/\bprint\s*\(/.test(trimmed) && !/^\s*#/.test(lines[i])) {
      violations.push({ line: i + 1, message: '生产代码使用 print()，应使用 logging 模块' });
    }
  }
  return violations;
}

function checkPython(lines, filePath) {
  const allViolations = [];
  for (const rule of PYTHON_RULES) {
    try {
      for (const v of rule.check(lines, filePath, rule)) {
        allViolations.push({ ruleId: rule.id, ruleName: rule.name, severity: rule.severity, ...v });
      }
    } catch (err) { log(`[code-quality] Python rule ${rule.id} error: ${err.message}`); }
  }
  return allViolations;
}

// ============================================================================
// ========= FRONTEND 规则（8 条：4 安全 + 4 质量）=========
// ============================================================================

const FRONTEND_RULES = [
  { id: 'fe-eval', name: 'eval/Function 使用', severity: 'error', check: checkFeEval },
  { id: 'fe-innerhtml', name: '不安全的 innerHTML', severity: 'error', check: checkFeInnerHtml },
  { id: 'fe-hardcoded-secret', name: '硬编码密钥', severity: 'error', check: checkFeHardcodedSecret },
  { id: 'fe-href-injection', name: '未校验的 href', severity: 'error', check: checkFeHrefInjection },
  { id: 'fe-any-type', name: '使用 any 类型', severity: 'warning', check: checkFeAnyType },
  { id: 'fe-console-log', name: '生产代码 console.log', severity: 'warning', check: checkFeConsoleLog },
  { id: 'fe-localstorage-token', name: 'localStorage 存 Token', severity: 'warning', check: checkFeLocalStorageToken },
  { id: 'fe-target-blank', name: 'target="_blank" 无 rel', severity: 'warning', check: checkFeTargetBlank },
];

function checkFeEval(lines, filePath) {
  const violations = [];
  if (isTestFile(filePath, 'fe')) return violations;
  for (let i = 0; i < lines.length; i++) {
    const trimmed = lines[i].trim();
    if (trimmed.startsWith('//') || trimmed.startsWith('*')) continue;
    if (/\beval\s*\(/.test(trimmed)) {
      violations.push({ line: i + 1, message: '使用了 eval()，存在代码执行风险。禁止对用户输入使用 eval' });
    }
    if (/\bnew\s+Function\s*\(/.test(trimmed)) {
      violations.push({ line: i + 1, message: '使用了 new Function()，等同于 eval。禁止动态代码执行' });
    }
  }
  return violations;
}

function checkFeInnerHtml(lines) {
  const violations = [];
  for (let i = 0; i < lines.length; i++) {
    const trimmed = lines[i].trim();
    if (trimmed.startsWith('//') || trimmed.startsWith('*')) continue;
    if (/dangerouslySetInnerHTML/.test(trimmed) && !/DOMPurify|sanitize|purify/.test(trimmed)) {
      let hasSanitize = false;
      for (let j = Math.max(0, i - 3); j <= Math.min(lines.length - 1, i + 3); j++) {
        if (/DOMPurify|sanitize|purify|xss/i.test(lines[j])) { hasSanitize = true; break; }
      }
      if (!hasSanitize) {
        violations.push({ line: i + 1, message: 'dangerouslySetInnerHTML 未经消毒，存在 XSS 风险。必须使用 DOMPurify.sanitize()' });
      }
    }
    if (/\.innerHTML\s*=/.test(trimmed) && !/DOMPurify|sanitize|purify/.test(trimmed)) {
      violations.push({ line: i + 1, message: '直接设置 innerHTML，存在 XSS 风险。应使用 textContent 或 DOMPurify.sanitize()' });
    }
  }
  return violations;
}

function checkFeHardcodedSecret(lines, filePath) {
  const violations = [];
  if (isTestFile(filePath, 'fe')) return violations;
  const SECRET_PATTERN = /\b(api[_-]?key|api[_-]?secret|secret[_-]?key|access[_-]?token|private[_-]?key|auth[_-]?token)\b\s*[:=]\s*["'`][A-Za-z0-9+/=_-]{16,}/i;
  for (let i = 0; i < lines.length; i++) {
    const trimmed = lines[i].trim();
    if (trimmed.startsWith('//') || trimmed.startsWith('*')) continue;
    if (SECRET_PATTERN.test(trimmed) && !/process\.env|import\.meta\.env|\.env/.test(trimmed)) {
      violations.push({ line: i + 1, message: '疑似硬编码密钥/Token，应使用环境变量' });
    }
  }
  return violations;
}

function checkFeHrefInjection(lines) {
  const violations = [];
  for (let i = 0; i < lines.length; i++) {
    const trimmed = lines[i].trim();
    if (trimmed.startsWith('//') || trimmed.startsWith('*')) continue;
    if (/href\s*=\s*\{/.test(trimmed) && !/https?:|mailto:|tel:|#/.test(trimmed)) {
      let hasSanitize = false;
      for (let j = Math.max(0, i - 5); j <= Math.min(lines.length - 1, i + 5); j++) {
        if (/sanitize|validate|isValidUrl|startsWith.*http|protocol/i.test(lines[j])) { hasSanitize = true; break; }
      }
      if (!hasSanitize) {
        violations.push({ line: i + 1, message: 'href 绑定动态值未校验协议，可能存在 javascript: 注入。应校验 URL 以 https:// 开头' });
      }
    }
  }
  return violations;
}

function checkFeAnyType(lines, filePath) {
  const violations = [];
  if (isTestFile(filePath, 'fe')) return violations;
  const ext = path.extname(filePath);
  if (ext !== '.ts' && ext !== '.tsx') return violations;
  for (let i = 0; i < lines.length; i++) {
    const trimmed = lines[i].trim();
    if (trimmed.startsWith('//') || trimmed.startsWith('*')) continue;
    if (/:\s*any\b/.test(trimmed) || /as\s+any\b/.test(trimmed) || /<any>/.test(trimmed)) {
      if (/eslint-disable|@ts-ignore|@ts-expect-error/.test(trimmed)) continue;
      violations.push({ line: i + 1, message: '使用了 any 类型，丧失类型检查价值。应使用 unknown + 类型收窄' });
    }
  }
  return violations;
}

function checkFeConsoleLog(lines, filePath) {
  const violations = [];
  if (isTestFile(filePath, 'fe')) return violations;
  for (let i = 0; i < lines.length; i++) {
    const trimmed = lines[i].trim();
    if (trimmed.startsWith('//') || trimmed.startsWith('*')) continue;
    if (/\bconsole\.(log|debug|info)\s*\(/.test(trimmed)) {
      violations.push({ line: i + 1, message: '生产代码使用 console.log，应使用专用 logger 或移除' });
    }
  }
  return violations;
}

function checkFeLocalStorageToken(lines) {
  const violations = [];
  for (let i = 0; i < lines.length; i++) {
    const trimmed = lines[i].trim();
    if (trimmed.startsWith('//') || trimmed.startsWith('*')) continue;
    if (/localStorage\.setItem\s*\(/.test(trimmed) && /token|jwt|session|auth/i.test(trimmed)) {
      violations.push({ line: i + 1, message: 'Token/JWT 存入 localStorage，XSS 可窃取。应使用 HttpOnly Cookie' });
    }
  }
  return violations;
}

function checkFeTargetBlank(lines) {
  const violations = [];
  for (let i = 0; i < lines.length; i++) {
    const trimmed = lines[i].trim();
    if (trimmed.startsWith('//') || trimmed.startsWith('*')) continue;
    if (/target\s*=\s*["'`]_blank["'`]/.test(trimmed)) {
      let hasRel = false;
      for (let j = Math.max(0, i - 2); j <= Math.min(lines.length - 1, i + 2); j++) {
        if (/rel\s*=\s*["'`][^"'`]*noopener/.test(lines[j])) { hasRel = true; break; }
      }
      if (!hasRel) {
        violations.push({ line: i + 1, message: 'target="_blank" 缺少 rel="noopener noreferrer"，存在反向 tabnabbing 风险' });
      }
    }
  }
  return violations;
}

function checkFrontend(lines, filePath) {
  const allViolations = [];
  for (const rule of FRONTEND_RULES) {
    try {
      for (const v of rule.check(lines, filePath, rule)) {
        allViolations.push({ ruleId: rule.id, ruleName: rule.name, severity: rule.severity, ...v });
      }
    } catch (err) { log(`[code-quality] Frontend rule ${rule.id} error: ${err.message}`); }
  }
  return allViolations;
}

// ============================================================================
// 共用工具
// ============================================================================

function isTestFile(filePath, lang) {
  const baseName = path.basename(filePath);
  if (lang === 'py') {
    return baseName.startsWith('test_') || baseName.endsWith('_test.py') || /conftest\.py$/.test(baseName) || filePath.includes('/tests/') || filePath.includes('/test/');
  }
  if (lang === 'fe') {
    return /\.(test|spec|e2e|cy)\.(ts|tsx|js|jsx)$/.test(baseName) || filePath.includes('__tests__/') || filePath.includes('/__mocks__/');
  }
  return false;
}

// ============================================================================
// 输出格式（多语言通用）
// ============================================================================

const LANG_LABELS = {
  '.java': 'Java',
  '.py': 'Python',
  '.ts': 'TypeScript', '.tsx': 'React TSX',
  '.vue': 'Vue', '.jsx': 'React JSX', '.js': 'JavaScript',
};

function formatViolations(violations, filePath, isEditMode) {
  if (violations.length === 0) return null;
  const fileName = path.basename(filePath);
  const ext = path.extname(filePath);
  const langLabel = LANG_LABELS[ext] || ext;
  const errors = violations.filter(v => v.severity === 'error');
  const warnings = violations.filter(v => v.severity === 'warning');

  let msg = `\n🛑 [Code Quality Guard][${langLabel}] ${fileName} 发现 ${violations.length} 个问题`;
  if (isEditMode) msg += '（仅检查本次修改范围）';
  msg += '：\n';

  if (errors.length > 0) { msg += '\n🔴 错误（必须修复）：\n'; for (const v of errors) msg += `  L${v.line} [${v.ruleId}]: ${v.message}\n`; }
  if (warnings.length > 0) { msg += '\n🟡 警告（建议修复）：\n'; for (const v of warnings) msg += `  L${v.line} [${v.ruleId}]: ${v.message}\n`; }
  if (isEditMode) msg += '\n⛔ 开闭原则：以上问题仅针对本次新增/修改代码。已有代码保持不动。';
  msg += '\n请修正代码后重新提交。';
  return msg;
}

// ============================================================================
// 主入口
// ============================================================================

async function main() {
  const input = await readStdin();
  const toolInput = input.tool_input || {};
  const filePath = toolInput.file_path || toolInput.filePath || '';
  if (!filePath) process.exit(0);
  // 排除构建产物和依赖目录
  if (filePath.includes('/node_modules/') || filePath.includes('/dist/') || filePath.includes('/build/') || filePath.includes('/.next/')) process.exit(0);

  const ext = path.extname(filePath).toLowerCase();
  const checker = ROUTERS[ext];
  if (!checker) process.exit(0);

  const extracted = extractContent(input);
  if (!extracted || !extracted.content) process.exit(0);

  const { content, changedLines, strictChangedLines, originalContent } = extracted;
  const lines = content.split('\n');
  const isEditMode = changedLines !== null;

  let originalViolationRuleIds = null;
  if (isEditMode && originalContent) {
    const origViolations = checker(originalContent.split('\n'), filePath);
    originalViolationRuleIds = new Set();
    for (const v of origViolations) { if (v.endLine) originalViolationRuleIds.add(v.ruleId); }
  }

  let violations = checker(lines, filePath);
  violations = filterByChangeRange(violations, changedLines, originalViolationRuleIds, strictChangedLines);

  if (violations.length === 0) { resetBlockCount(filePath); process.exit(0); }

  const errorViolations = violations.filter(v => v.severity === 'error');
  const warningViolations = violations.filter(v => v.severity === 'warning');
  const blockingViolations = [...errorViolations, ...warningViolations];

  const contentHash = simpleHash(content);
  const blockCount = getBlockCount(filePath, contentHash);
  const shouldDegrade = blockCount >= MAX_CONSECUTIVE_BLOCKS;
  const hasErrors = errorViolations.length > 0;
  const errorHardLimit = MAX_CONSECUTIVE_BLOCKS * 2;
  const shouldEscalate = hasErrors && blockCount >= errorHardLimit;

  const langLabel = LANG_LABELS[ext] || ext;

  if (blockingViolations.length > 0 && (!shouldDegrade || (hasErrors && !shouldEscalate))) {
    incrementBlockCount(filePath, contentHash, blockCount);
    const message = formatViolations(violations, filePath, isEditMode);
    process.stdout.write(JSON.stringify({
      hookSpecificOutput: { hookEventName: 'PreToolUse', permissionDecision: 'deny', permissionDecisionReason: message },
    }));
    log(`[code-quality][${langLabel}] DENY ${path.basename(filePath)}: ${errorViolations.length}E + ${warningViolations.length}W (${blockCount + 1}/${hasErrors ? errorHardLimit : MAX_CONSECUTIVE_BLOCKS})`);
  } else if (shouldDegrade || shouldEscalate) {
    resetBlockCount(filePath);
    const hint = shouldEscalate ? '🔴 error 级连续阻断达上限，降级放行。请人工检查。' : '⚠️ 连续阻断达上限，降级放行。';
    const message = formatViolations(violations, filePath, isEditMode) + '\n\n' + hint;
    process.stdout.write(JSON.stringify({
      hookSpecificOutput: { hookEventName: 'PreToolUse', permissionDecision: 'allow', additionalContext: message },
    }));
    log(`[code-quality][${langLabel}] ${shouldEscalate ? 'ESCALATE' : 'DEGRADE'} ${path.basename(filePath)}`);
  }

  process.exit(0);
}

main().catch(err => { log(`[code-quality] Error: ${err.message}`); process.exit(0); });
