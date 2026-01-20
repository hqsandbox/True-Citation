"""数据模型定义"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class VerificationStatus(Enum):
    """验证状态"""
    VERIFIED = "verified"      # 已验证，找到匹配
    SUSPICIOUS = "suspicious"  # 可疑，部分匹配
    ERROR = "error"           # 错误，未找到或严重不匹配
    PENDING = "pending"       # 待验证
    SKIPPED = "skipped"       # 跳过（未在tex中使用）


@dataclass
class BibEntry:
    """BibTeX条目"""
    key: str
    entry_type: str  # article, inproceedings, book, etc.
    title: str
    authors: list[str] = field(default_factory=list)
    year: Optional[int] = None
    journal: Optional[str] = None
    booktitle: Optional[str] = None
    volume: Optional[str] = None
    number: Optional[str] = None
    pages: Optional[str] = None
    doi: Optional[str] = None
    url: Optional[str] = None
    publisher: Optional[str] = None
    raw_entry: str = ""  # 原始BibTeX文本
    
    def to_bibtex(self) -> str:
        """生成BibTeX格式字符串"""
        lines = [f"@{self.entry_type}{{{self.key},"]
        
        if self.authors:
            lines.append(f"  author = {{{' and '.join(self.authors)}}},")
        if self.title:
            lines.append(f"  title = {{{self.title}}},")
        if self.year:
            lines.append(f"  year = {{{self.year}}},")
        if self.journal:
            lines.append(f"  journal = {{{self.journal}}},")
        if self.booktitle:
            lines.append(f"  booktitle = {{{self.booktitle}}},")
        if self.volume:
            lines.append(f"  volume = {{{self.volume}}},")
        if self.number:
            lines.append(f"  number = {{{self.number}}},")
        if self.pages:
            lines.append(f"  pages = {{{self.pages}}},")
        if self.doi:
            lines.append(f"  doi = {{{self.doi}}},")
        if self.url:
            lines.append(f"  url = {{{self.url}}},")
        if self.publisher:
            lines.append(f"  publisher = {{{self.publisher}}},")
        
        lines.append("}")
        return "\n".join(lines)


@dataclass
class SearchResult:
    """搜索结果"""
    source: str  # semantic_scholar, crossref, openalex, dblp
    title: str
    authors: list[str] = field(default_factory=list)
    year: Optional[int] = None
    doi: Optional[str] = None
    url: Optional[str] = None
    journal: Optional[str] = None
    booktitle: Optional[str] = None
    volume: Optional[str] = None
    pages: Optional[str] = None
    
    # 匹配得分
    title_similarity: float = 0.0
    author_match_count: int = 0
    year_match: bool = False
    overall_score: float = 0.0


@dataclass
class VerificationResult:
    """验证结果"""
    entry: BibEntry
    status: VerificationStatus
    message: str = ""
    search_results: list[SearchResult] = field(default_factory=list)
    best_match: Optional[SearchResult] = None
    corrected_entry: Optional[BibEntry] = None
    
    @property
    def status_emoji(self) -> str:
        return {
            VerificationStatus.VERIFIED: "✅",
            VerificationStatus.SUSPICIOUS: "⚠️",
            VerificationStatus.ERROR: "❌",
            VerificationStatus.PENDING: "⏳",
            VerificationStatus.SKIPPED: "⏭️",
        }.get(self.status, "❓")
