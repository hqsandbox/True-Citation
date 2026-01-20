"""BibTeX和LaTeX解析器"""

import re
from pathlib import Path
from typing import Optional

import bibtexparser
from bibtexparser.bparser import BibTexParser
from bibtexparser.customization import convert_to_unicode

from .models import BibEntry


def parse_authors(author_string: str) -> list[str]:
    """解析作者字符串为作者列表"""
    if not author_string:
        return []
    
    # 处理 "and" 分隔的作者
    authors = re.split(r'\s+and\s+', author_string, flags=re.IGNORECASE)
    
    result = []
    for author in authors:
        author = author.strip()
        if not author:
            continue
        
        # 处理 "Last, First" 格式
        if ',' in author:
            parts = author.split(',', 1)
            last = parts[0].strip()
            first = parts[1].strip() if len(parts) > 1 else ""
            author = f"{first} {last}".strip()
        
        # 清理多余空格和花括号
        author = re.sub(r'\s+', ' ', author)
        author = author.replace('{', '').replace('}', '')
        result.append(author)
    
    return result


def parse_year(year_string: str) -> Optional[int]:
    """解析年份字符串"""
    if not year_string:
        return None
    
    # 提取4位数字年份
    match = re.search(r'(\d{4})', str(year_string))
    if match:
        return int(match.group(1))
    return None


def parse_bib_file(bib_path: Path) -> dict[str, BibEntry]:
    """解析BibTeX文件
    
    Args:
        bib_path: BibTeX文件路径
        
    Returns:
        字典，key为引用键，value为BibEntry对象
    """
    parser = BibTexParser(common_strings=True)
    parser.customization = convert_to_unicode
    
    with open(bib_path, 'r', encoding='utf-8') as f:
        bib_database = bibtexparser.load(f, parser=parser)
    
    entries = {}
    for entry in bib_database.entries:
        key = entry.get('ID', '')
        if not key:
            continue
        
        bib_entry = BibEntry(
            key=key,
            entry_type=entry.get('ENTRYTYPE', 'misc'),
            title=entry.get('title', '').replace('{', '').replace('}', ''),
            authors=parse_authors(entry.get('author', '')),
            year=parse_year(entry.get('year', '')),
            journal=entry.get('journal', ''),
            booktitle=entry.get('booktitle', ''),
            volume=entry.get('volume', ''),
            number=entry.get('number', ''),
            pages=entry.get('pages', ''),
            doi=entry.get('doi', ''),
            url=entry.get('url', ''),
            publisher=entry.get('publisher', ''),
        )
        
        # 保存原始条目用于生成raw_entry
        raw_lines = [f"@{bib_entry.entry_type}{{{key},"]
        for k, v in entry.items():
            if k not in ('ID', 'ENTRYTYPE') and v:
                raw_lines.append(f"  {k} = {{{v}}},")
        raw_lines.append("}")
        bib_entry.raw_entry = "\n".join(raw_lines)
        
        entries[key] = bib_entry
    
    return entries


def extract_citations_from_tex(tex_path: Path) -> set[str]:
    """从LaTeX文件中提取引用键
    
    支持的引用命令: \\cite, \\citep, \\citet, \\citeauthor, \\citeyear 等
    
    Args:
        tex_path: LaTeX文件路径
        
    Returns:
        引用键集合
    """
    with open(tex_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 移除注释
    content = re.sub(r'(?<!\\)%.*$', '', content, flags=re.MULTILINE)
    
    citations = set()
    
    # 匹配各种cite命令
    # \cite{key1, key2}, \citep{key}, \citet{key}, \citeauthor{key}, etc.
    cite_pattern = r'\\(?:cite[pt]?|citeauthor|citeyear|citealt|citealp|citenum|parencite|textcite|autocite)\*?\s*(?:\[[^\]]*\])?\s*(?:\[[^\]]*\])?\s*\{([^}]+)\}'
    
    for match in re.finditer(cite_pattern, content):
        keys = match.group(1)
        # 处理多个key的情况，如 \cite{key1, key2, key3}
        for key in keys.split(','):
            key = key.strip()
            if key:
                citations.add(key)
    
    return citations


def extract_citations_from_multiple_tex(tex_paths: list[Path]) -> set[str]:
    """从多个LaTeX文件中提取引用键"""
    all_citations = set()
    for path in tex_paths:
        all_citations.update(extract_citations_from_tex(path))
    return all_citations
