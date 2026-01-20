"""报告生成器"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from .models import VerificationResult, VerificationStatus


class ReportGenerator:
    """验证报告生成器"""
    
    def __init__(self, results: list[VerificationResult], output_dir: Path):
        self.results = results
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def _count_by_status(self) -> dict[VerificationStatus, int]:
        """统计各状态数量"""
        counts = {status: 0 for status in VerificationStatus}
        for result in self.results:
            counts[result.status] += 1
        return counts
    
    def generate_markdown(self) -> str:
        """生成Markdown格式报告"""
        counts = self._count_by_status()
        total = len(self.results)
        
        lines = [
            "# 🔍 True-Citation 验证报告",
            "",
            f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## 📊 统计摘要",
            "",
            f"| 状态 | 数量 | 占比 |",
            f"|------|------|------|",
            f"| ✅ 已验证 | {counts[VerificationStatus.VERIFIED]} | {counts[VerificationStatus.VERIFIED]/total*100:.1f}% |" if total > 0 else "",
            f"| ⚠️ 可疑 | {counts[VerificationStatus.SUSPICIOUS]} | {counts[VerificationStatus.SUSPICIOUS]/total*100:.1f}% |" if total > 0 else "",
            f"| ❌ 错误 | {counts[VerificationStatus.ERROR]} | {counts[VerificationStatus.ERROR]/total*100:.1f}% |" if total > 0 else "",
            f"| ⏭️ 跳过 | {counts[VerificationStatus.SKIPPED]} | {counts[VerificationStatus.SKIPPED]/total*100:.1f}% |" if total > 0 else "",
            f"| **总计** | **{total}** | **100%** |",
            "",
        ]
        
        # 按状态分组显示
        for status, emoji_name in [
            (VerificationStatus.ERROR, "❌ 错误引用"),
            (VerificationStatus.SUSPICIOUS, "⚠️ 可疑引用"),
            (VerificationStatus.VERIFIED, "✅ 已验证引用"),
        ]:
            status_results = [r for r in self.results if r.status == status]
            if not status_results:
                continue
            
            lines.append(f"## {emoji_name} ({len(status_results)})")
            lines.append("")
            
            for result in status_results:
                entry = result.entry
                lines.append(f"### [{entry.key}]")
                lines.append("")
                lines.append(f"**原始信息:**")
                lines.append(f"- 标题: {entry.title}")
                lines.append(f"- 作者: {', '.join(entry.authors) if entry.authors else '未知'}")
                lines.append(f"- 年份: {entry.year or '未知'}")
                if entry.doi:
                    lines.append(f"- DOI: {entry.doi}")
                lines.append("")
                lines.append(f"**验证结果:** {result.message}")
                lines.append("")
                
                # 如果有最佳匹配
                if result.best_match:
                    match = result.best_match
                    lines.append(f"**最佳匹配 (来源: {match.source}):**")
                    lines.append(f"- 标题: {match.title}")
                    lines.append(f"- 作者: {', '.join(match.authors) if match.authors else '未知'}")
                    lines.append(f"- 年份: {match.year or '未知'}")
                    lines.append(f"- 标题相似度: {match.title_similarity:.1%}")
                    lines.append(f"- 作者匹配数: {match.author_match_count}")
                    if match.url:
                        lines.append(f"- URL: {match.url}")
                    if match.doi:
                        lines.append(f"- DOI: {match.doi}")
                    lines.append("")
                
                # 如果有修正建议
                if result.corrected_entry:
                    lines.append("**建议修正的BibTeX:**")
                    lines.append("```bibtex")
                    lines.append(result.corrected_entry.to_bibtex())
                    lines.append("```")
                    lines.append("")
                
                lines.append("---")
                lines.append("")
        
        return "\n".join(lines)
    
    def generate_json(self) -> str:
        """生成JSON格式报告"""
        counts = self._count_by_status()
        
        data = {
            "generated_at": datetime.now().isoformat(),
            "summary": {
                "total": len(self.results),
                "verified": counts[VerificationStatus.VERIFIED],
                "suspicious": counts[VerificationStatus.SUSPICIOUS],
                "error": counts[VerificationStatus.ERROR],
                "skipped": counts[VerificationStatus.SKIPPED],
            },
            "results": []
        }
        
        for result in self.results:
            result_data = {
                "key": result.entry.key,
                "status": result.status.value,
                "message": result.message,
                "original": {
                    "title": result.entry.title,
                    "authors": result.entry.authors,
                    "year": result.entry.year,
                    "doi": result.entry.doi,
                },
            }
            
            if result.best_match:
                result_data["best_match"] = {
                    "source": result.best_match.source,
                    "title": result.best_match.title,
                    "authors": result.best_match.authors,
                    "year": result.best_match.year,
                    "doi": result.best_match.doi,
                    "url": result.best_match.url,
                    "title_similarity": result.best_match.title_similarity,
                    "author_match_count": result.best_match.author_match_count,
                }
            
            if result.corrected_entry:
                result_data["corrected_bibtex"] = result.corrected_entry.to_bibtex()
            
            data["results"].append(result_data)
        
        return json.dumps(data, ensure_ascii=False, indent=2)
    
    def generate_html(self) -> str:
        """生成HTML格式报告"""
        counts = self._count_by_status()
        total = len(self.results)
        
        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>True-Citation 验证报告</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }}
        .container {{
            background: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        h1 {{ color: #333; }}
        .summary {{
            display: flex;
            gap: 20px;
            margin: 20px 0;
        }}
        .stat-card {{
            padding: 20px;
            border-radius: 8px;
            flex: 1;
            text-align: center;
        }}
        .stat-card.verified {{ background: #d4edda; color: #155724; }}
        .stat-card.suspicious {{ background: #fff3cd; color: #856404; }}
        .stat-card.error {{ background: #f8d7da; color: #721c24; }}
        .stat-card h3 {{ margin: 0; font-size: 2em; }}
        .stat-card p {{ margin: 5px 0 0; }}
        .result {{
            border: 1px solid #ddd;
            border-radius: 8px;
            margin: 15px 0;
            overflow: hidden;
        }}
        .result-header {{
            padding: 15px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .result-header.verified {{ background: #d4edda; }}
        .result-header.suspicious {{ background: #fff3cd; }}
        .result-header.error {{ background: #f8d7da; }}
        .result-body {{ padding: 15px; }}
        .bibtex {{
            background: #f8f9fa;
            padding: 15px;
            border-radius: 4px;
            font-family: monospace;
            white-space: pre-wrap;
            overflow-x: auto;
        }}
        .tag {{
            display: inline-block;
            padding: 3px 8px;
            border-radius: 4px;
            font-size: 0.9em;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🔍 True-Citation 验证报告</h1>
        <p>生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        
        <div class="summary">
            <div class="stat-card verified">
                <h3>{counts[VerificationStatus.VERIFIED]}</h3>
                <p>✅ 已验证</p>
            </div>
            <div class="stat-card suspicious">
                <h3>{counts[VerificationStatus.SUSPICIOUS]}</h3>
                <p>⚠️ 可疑</p>
            </div>
            <div class="stat-card error">
                <h3>{counts[VerificationStatus.ERROR]}</h3>
                <p>❌ 错误</p>
            </div>
        </div>
"""
        
        # 添加各个结果
        for result in self.results:
            if result.status == VerificationStatus.SKIPPED:
                continue
            
            status_class = result.status.value
            html += f"""
        <div class="result">
            <div class="result-header {status_class}">
                <strong>[{result.entry.key}] {result.entry.title[:80]}{'...' if len(result.entry.title) > 80 else ''}</strong>
                <span class="tag">{result.status_emoji} {result.status.value}</span>
            </div>
            <div class="result-body">
                <p><strong>作者:</strong> {', '.join(result.entry.authors) if result.entry.authors else '未知'}</p>
                <p><strong>年份:</strong> {result.entry.year or '未知'}</p>
                <p><strong>验证结果:</strong> {result.message}</p>
"""
            
            if result.best_match:
                html += f"""
                <p><strong>最佳匹配 ({result.best_match.source}):</strong></p>
                <ul>
                    <li>标题: {result.best_match.title}</li>
                    <li>相似度: {result.best_match.title_similarity:.1%}</li>
                    <li>URL: <a href="{result.best_match.url}" target="_blank">{result.best_match.url}</a></li>
                </ul>
"""
            
            if result.corrected_entry:
                html += f"""
                <p><strong>建议修正的BibTeX:</strong></p>
                <div class="bibtex">{result.corrected_entry.to_bibtex()}</div>
"""
            
            html += """
            </div>
        </div>
"""
        
        html += """
    </div>
</body>
</html>
"""
        return html
    
    def generate_corrected_bib(self) -> str:
        """生成修正后的完整BibTeX文件"""
        lines = [
            "% True-Citation 修正后的参考文献",
            f"% 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
        ]
        
        for result in self.results:
            if result.status == VerificationStatus.SKIPPED:
                continue
            
            # 如果有修正建议，使用修正后的版本
            if result.corrected_entry:
                lines.append(f"% 原始条目有问题，以下是修正版本")
                lines.append(result.corrected_entry.to_bibtex())
            else:
                # 否则使用原始条目（对于已验证的）
                lines.append(result.entry.to_bibtex())
            
            lines.append("")
        
        return "\n".join(lines)
    
    def save_report(self, format: str = "markdown") -> Path:
        """保存报告到文件
        
        Args:
            format: 报告格式 (markdown, json, html)
            
        Returns:
            生成的报告文件路径
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if format == "markdown":
            content = self.generate_markdown()
            filename = f"report_{timestamp}.md"
        elif format == "json":
            content = self.generate_json()
            filename = f"report_{timestamp}.json"
        elif format == "html":
            content = self.generate_html()
            filename = f"report_{timestamp}.html"
        else:
            raise ValueError(f"不支持的报告格式: {format}")
        
        filepath = self.output_dir / filename
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return filepath
    
    def save_corrected_bib(self) -> Path:
        """保存修正后的BibTeX文件"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        content = self.generate_corrected_bib()
        filename = f"corrected_{timestamp}.bib"
        
        filepath = self.output_dir / filename
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return filepath
