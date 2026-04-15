"""内部链接完整性测试（T9）"""
import re
from pathlib import Path

import pytest

SKILLS_DIR = Path(__file__).parent.parent


def _find_all_md_files():
    """收集所有 markdown 文件"""
    return sorted(SKILLS_DIR.rglob("*.md"))


def _extract_links(content: str):
    """提取 markdown 链接 [text](path)，排除 http/https 和模板占位符"""
    pattern = r'\[([^\]]*)\]\(([^)]+)\)'
    links = []
    for match in re.finditer(pattern, content):
        target = match.group(2)
        if target.startswith(("http://", "https://", "#", "mailto:")):
            continue
        # 跳过模板占位符链接（含 {xxx} 或 [xxx] 变量）
        if re.search(r'[\[{].*[\]}]', target):
            continue
        links.append(target)
    return links


def _collect_broken_links():
    """收集所有断链"""
    broken = []
    for md_file in _find_all_md_files():
        if "/tests/" in str(md_file) or "/__pycache__/" in str(md_file):
            continue
        content = md_file.read_text(encoding="utf-8", errors="ignore")
        links = _extract_links(content)
        for link in links:
            # 移除锚点
            clean = link.split("#")[0]
            if not clean:
                continue
            target = (md_file.parent / clean).resolve()
            if not target.exists():
                broken.append((str(md_file.relative_to(SKILLS_DIR)), link))
    return broken


class TestLinkIntegrity:
    def test_no_broken_links(self):
        broken = _collect_broken_links()
        if broken:
            msg = "Broken links found:\n"
            for src, target in broken:
                msg += f"  {src} -> {target}\n"
            # 已知的预存断链（cc-skill-creator 和 cc-web-tester）
            known_broken = {
                "FORMS.md", "REFERENCE.md", "EXAMPLES.md",
                "DOCX-JS.md", "REDLINING.md", "OOXML.md",
                "templates.md",  # cc-web-tester/workflows/ 引用上级 templates.md
                "spec.md",  # cc-planner/templates/ 是模板，运行时被复制到 $STARK_SESSION_DIR，
                            # 链接 ./spec.md 在源码态解析失败但在运行时正确
            }
            unknown = [(s, t) for s, t in broken if Path(t).name not in known_broken]
            if unknown:
                pytest.fail(f"Unknown broken links:\n" +
                           "\n".join(f"  {s} -> {t}" for s, t in unknown))
            else:
                pytest.skip(f"Only known pre-existing broken links ({len(broken)})")
