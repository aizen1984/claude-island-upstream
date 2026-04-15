# 数据报告防失真协议 (data-report-protocol)

> **目的**：防止 agent 动态生成数据报告时的 under-reporting（漏报）、fabrication（瞎编）、aggregation drift（缝合丢失）
>
> **适用**：frontmatter 声明 `report_generation: true` 的所有 skill
>
> **与 check_consistency.py 的关系**：check_consistency.py 是**静态 lint**（拦截文档漂移），本协议是**运行时契约**（拦截报告生成时的失真）。两者互补，不重叠。
>
> **理论依据**：
> - Anthropic 官方 [minimizing-hallucinations](https://platform.claude.com/docs/en/docs/minimizing-hallucinations)（quote grounding + citation verification）
> - LLM×MapReduce 论文（structured information protocol + in-context confidence calibration）
> - HumanLayer harness engineering（back-pressure verification loop）
> - Iter 3 真实教训（9 处命中被漏报 33%，根因是 AP3+AP4 同时发作）

## 零、意图

数据报告型 skill 的核心工作模式是 Map-Reduce：多个 subagent 并行扫描不同输入源（Map），主 agent 或脚本汇总为最终报告（Reduce）。这个模式有三个固有失真点：

1. **Map 阶段瞎编**：subagent 在没有证据时生成"看起来合理"的 finding（AP3 fabrication）
2. **Map 阶段漏报**：subagent 以为扫描完了但实际只覆盖部分（AP4 silent under-reporting）
3. **Reduce 阶段缝合丢失**：LLM 汇总时 context rot 导致 27 个结果变成 15 个

本协议针对这三点分别给出 **Quote Grounding / Constrained Output Contract / Deterministic Reduce** 三条防线。

## 一、适用范围 + opt-out

**必须遵守**（`report_generation: true` 且生成结构化报告）：
- cc-adversarial / cc-code-reviewer / cc-troubleshoot / cc-api-analyzer / cc-work-mode（SUMMARIZE 阶段）

**推荐遵守**（生成混合结构/散文报告）：
- cc-design（逆向路径）/ cc-web-tester / cc-eval

**允许 opt-out**（以下场景可以仅遵守防线 1 不遵守 2-3）：
- 简单评分报告（单一数值输出，无 findings 列表）
- 纯散文分析（无需聚合的叙述性输出）

opt-out 时在 frontmatter 显式声明：`report_protocol_mode: grounding-only`

## 二、Quote Grounding 强制引用协议（防 AP3 fabrication）

### 2.1 核心规则

**每条 finding/claim 必须附带原文 word-for-word 引用。没有引用的 claim 必须删除并显式标记删除位置**。

### 2.2 标签语法

subagent 在生成报告时必须使用如下标签结构：

```xml
<quote file="path/to/file.md" line="42">原文字符逐字</quote>
```

字段要求：
- `file` 必须是相对路径或绝对路径，调用方 CWD 可定位的实际文件
- `line` 必须是整数行号（多行引用用 `line="42-48"`）
- 标签内容必须是**原文字符逐字**，不允许改写、截断、省略号

### 2.3 no-match 声明（反 silent failure）

如果某项规则零命中，**必须显式声明**，不允许省略：

```xml
<no-match pattern="disable-model-invocation" scope="cc-skill-creator/SKILL.md" reason="frontmatter 不含此字段"/>
```

这让"扫过了但没命中"和"忘了扫"变得**可区分**，是防 AP4 同构盲区的关键机制。

### 2.4 [REMOVED:no-quote] 删除标记

Agent 自审阶段必须扫描自己生成的报告，对**无 quote 支持的 claim** 执行：

```markdown
## P0 Findings

- ✅ finding 1: 配置缺失 <quote file="SKILL.md" line="12">allowed-tools:</quote>
- ✅ finding 2: 引用断链 <quote file="workflows.md" line="88">第六章 xxx</quote>
- [REMOVED:no-quote] 原本想报"存在性能问题"但找不到原文支持，删除。
```

**为什么保留删除标记而不是静默删除**：让用户看见"哪里本来想说但没证据" = 把 silent failure 变成 explicit gap。这是 Anthropic 官方 [minimizing-hallucinations](https://platform.claude.com/docs/en/docs/minimizing-hallucinations) 例子中 `[ ]` 空括号的变体实现。

## 三、Constrained Output Contract（防 AP4 silent under-reporting）

### 3.1 JSON Schema 模板（subagent 输出契约）

subagent 必须输出且仅输出如下结构的 JSON，不允许自由文本：

```json
{
  "skill_name": "cc-xxx",
  "agent_role": "reviewer|scanner|analyzer",
  "scanned_files": ["SKILL.md", "scripts/foo.py"],
  "scanned_patterns": [
    {"pattern": "\\d+步", "hits": 2, "scope": "SKILL.md"},
    {"pattern": "disable-model-invocation", "hits": 0, "scope": "frontmatter"}
  ],
  "findings": [
    {
      "severity": "P0|P1|P2",
      "file": "SKILL.md",
      "line": 42,
      "quote": "按6步流程执行",
      "rule_violated": "CSO-no-step-count",
      "suggested_fix": "按流程执行"
    }
  ],
  "scan_complete": true,
  "unscanned_reason": null,
  "self_audit_passed": true
}
```

### 3.2 关键字段说明

| 字段 | 作用 | 反什么反模式 |
|------|------|------------|
| `scanned_patterns[].hits: 0` | 强制列出零命中，证明"扫过了" | AP4 silent failure |
| `scanned_patterns[].scope` | 限定扫描范围，避免"全局扫了"的模糊声明 | AP3 虚假完备 |
| `findings[].quote` | 每条 finding 的 ground truth | AP3 fabrication |
| `scan_complete: false` + `unscanned_reason` | 允许 agent 说"我没扫完"而不是假装扫完 | AP3 "I don't know" 授权 |
| `self_audit_passed: true` | subagent 必须在输出前自审引用完整性 | 双重验证 |

### 3.3 scan_complete 自证机制

灵感来自 Anthropic 的"Allow Claude to say 'I don't know'"原则。如果 subagent 遇到：
- 输入文件过大无法完整读取
- 某个模式语义复杂无法判断
- 权限不足访问某目录

**必须**输出 `scan_complete: false` + 详细 `unscanned_reason`。主 agent / Reduce 脚本会把这些条目单独标记，**不计入"完成扫描"**。

## 四、Deterministic Reduce 指南（防 aggregation drift）

### 4.1 铁律：不用 LLM 缝合多个 Map 结果

27 个 subagent 输出的 JSON 结果**必须由 Python 脚本汇总**，不允许 LLM 在 context 里"阅读所有报告然后总结"。LLM 缝合的失败模式是 context rot —— 27 个变成 15 个，且丢失的那 12 个不可追溯。

### 4.2 Python 聚合骨架（copy-paste 模板）

每个报告型 skill 应在 `{skill}/scripts/aggregate_findings.py` 提供如下结构：

```python
# aggregate_findings.py
"""
Deterministic reduce for map-reduce style report generation.
Reads all subagent JSON outputs → merges → detects coverage gaps.
"""
import json, glob, sys
from collections import defaultdict
from pathlib import Path

def aggregate(json_dir: Path) -> dict:
    findings_by_skill = defaultdict(list)
    unscanned_alerts = []
    pattern_coverage = defaultdict(set)
    dropped_no_quote = []

    for f in glob.glob(str(json_dir / "*.json")):
        data = json.loads(Path(f).read_text())
        skill = data["skill_name"]

        # Red line 1: scan_complete=false 顶层告警
        if not data.get("scan_complete", True):
            unscanned_alerts.append({
                "skill": skill,
                "reason": data.get("unscanned_reason", "unknown"),
                "source": f
            })

        # Red line 2: 无 quote 的 finding 必须丢弃并记日志
        for finding in data.get("findings", []):
            if not finding.get("quote"):
                dropped_no_quote.append({
                    "skill": skill,
                    "finding": finding,
                    "reason": "no-quote-support"
                })
                continue
            findings_by_skill[skill].append(finding)

        # Red line 3: 记录每个正则被哪些 skill 扫过（AP4 盲区检测）
        for p in data.get("scanned_patterns", []):
            pattern_coverage[p["pattern"]].add(skill)

    # Red line 4: 覆盖率不足的正则标记为"coverage gap"
    total_skills = len(findings_by_skill)
    coverage_gaps = [
        {"pattern": p, "covered_skills": len(skills), "total": total_skills}
        for p, skills in pattern_coverage.items()
        if total_skills > 0 and len(skills) < total_skills * 0.5
    ]

    return {
        "findings_by_skill": dict(findings_by_skill),
        "unscanned_alerts": unscanned_alerts,
        "dropped_no_quote": dropped_no_quote,
        "coverage_gaps": coverage_gaps,
        "total_skills_scanned": total_skills,
    }

if __name__ == "__main__":
    result = aggregate(Path(sys.argv[1]))
    print(json.dumps(result, indent=2, ensure_ascii=False))
    # 非 0 退出如有警告
    if result["unscanned_alerts"] or result["dropped_no_quote"]:
        sys.exit(2)
```

### 4.3 四条红线的作用对照

| 红线 | 防什么 | Iter 3 复盘 |
|------|-------|------------|
| 1. scan_complete 告警 | 隐藏的"没扫完" | - |
| 2. 无 quote 丢弃 | AP3 瞎编 | 如果当时有，27 个 agent 的假 finding 会被 drop |
| 3. 正则覆盖率记录 | AP4 同构盲区 | 如果当时有，"adversarial-verification.md 只在 5 skill 扫过"会显式暴露 |
| 4. coverage gap 告警 | 部分 agent 没扫 | 如果当时有，会立即要求补扫 |

## 五、Back-Pressure Verify Loop（两层防线）

### 5.1 静态 lint 层（已由 check_consistency.py 实现 — Iter 9/17）

10 条规则覆盖"修复成果的 regression 拦截"。与本协议**互补**：lint 确保修复不复发，本协议确保新报告不失真。

### 5.2 运行时层（Iter 23 将实现 `verify_report_runtime.py`）

独立脚本，作为 PostToolUse hook 或 handoff-style 独立工具：

- `verify_no_fabrication(report_path)`: 对每个 `<quote>` 执行反向 grep，原文不存在 → exit 2
- `verify_no_underreport(report_path, patterns)`: 对每个 pattern 在活文档上 grep，对比报告 scanned_patterns 字段，漏报 → exit 2

**exit 2 的语义**：HumanLayer harness engineering 的标准约定——Claude Code hook exit 2 会把 stderr 注入到 agent 下一轮 context，触发自动修复。`exit 1` 只是普通失败，agent 看不见错误内容。

## 六、skill 引用方式（执行层落地）

### 6.1 frontmatter 声明

```yaml
---
name: cc-code-reviewer
description: ...
report_generation: true
report_protocol: data-report-protocol   # 可选，默认值
report_protocol_mode: full              # full | grounding-only
allowed-tools: Read, Grep, Glob, Task, Bash
---
```

### 6.2 subagent prompt boilerplate（直接粘贴到 workflows/*.md）

```markdown
## 输出契约（强制）

你必须遵守 `shared-rules/data-report-protocol.md` 的 §二 Quote Grounding 和 §三 Constrained Output Contract。具体要求：

1. 每条 finding 必须附带 `<quote file="..." line="..."/>` 引用，内容为原文字符逐字
2. 零命中的规则必须用 `<no-match pattern="..." scope="..."/>` 显式声明
3. 最终输出必须是符合 §3.1 schema 的 JSON（不允许自由文本包裹）
4. 自审阶段：扫描你的 findings，任何无 quote 支持的 claim 用 `[REMOVED:no-quote]` 标记并删除
5. 如果无法完成扫描，输出 `scan_complete: false` + 详细 `unscanned_reason`，**不要假装扫完**
```

### 6.3 Deterministic Reduce 脚本位置约定

每个 `report_generation: true` 的 skill 应在 `{skill}/scripts/aggregate_findings.py` 提供符合 §4.2 骨架的脚本。允许扩展但不允许删除四条红线。

## 七、反例对照 + Iter 3 真实场景复盘

### 7.1 反例 1 — AP3 瞎编 finding

```markdown
❌ 错误：
## P0 Findings
- cc-code-reviewer 存在严重的性能问题，需要优化

✅ 正确：
## P0 Findings
- [REMOVED:no-quote] 原本想报"性能问题"，grep 未找到支持证据，删除。
```

### 7.2 反例 2 — AP4 silent under-reporting（Iter 3 真实场景）

Iter 3 的评审报告声称"adversarial-verification.md 路径断链在 5 个 skill 中命中"，但活文档实际 grep 命中 9 处。漏报的 4 处全在 cc-planner/workflows/ 子目录，27 个 general-purpose agent 全部没扫到。

**如果当时有本协议**：

```json
{
  "scanned_patterns": [
    {"pattern": "adversarial-verification.md", "hits": 5, "scope": "cc-*/SKILL.md 顶层"},
  ],
  "scan_complete": false,
  "unscanned_reason": "未扫描 cc-planner/workflows/ 子目录，范围限定在顶层 SKILL.md"
}
```

→ Reduce 脚本看到 `scan_complete: false` 立即告警 → 主 agent 要求补扫 → 9/5 漏报在第一轮就被捕获，不需要后来 AP4 手动发现。

### 7.3 反例 3 — Aggregation drift

```markdown
❌ 错误：
主 agent 说："我读了所有 27 个评审报告，总结如下..."（LLM 缝合）

✅ 正确：
主 agent 说："执行 python scripts/aggregate_findings.py reports/ 得到汇总 JSON。以下是脚本输出..."（Deterministic reduce）
```

## 八、版本历史

| 版本 | 日期 | 变更 | 相关 Iter |
|------|------|------|---------|
| 1.0 | 2026-04-09 | 初始协议，三防线 + skill 引用方式 | Iter 20 |
| 1.1 | 2026-04-09 | 本协议 scope 收敛到"结构失真"；迭代收敛 + 内容可读性分拆到 `shared-rules/report-iteration-protocol.md`。Iter 25 曾短暂加入 § 九/§ 十 作为 v2.0，Iter 26 按 SRP 分拆回迁 | Iter 26 |
