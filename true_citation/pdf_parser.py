"""PDF解析模块 - 从PDF中提取引用信息"""

import re
from pathlib import Path
from typing import Optional

import fitz  # PyMuPDF

from .models import BibEntry


def extract_text_from_pdf(pdf_path: Path) -> str:
    """从PDF中提取文本"""
    doc = fitz.open(pdf_path)
    text = ""
    for page in doc:
        text += page.get_text()
    doc.close()
    return text


def find_references_section(text: str) -> str:
    """找到参考文献部分"""
    # 常见的参考文献标题
    patterns = [
        r'\n\s*References?\s*\n',
        r'\n\s*REFERENCES?\s*\n',
        r'\n\s*Bibliography\s*\n',
        r'\n\s*BIBLIOGRAPHY\s*\n',
        r'\n\s*参考文献\s*\n',
        r'\n\s*引用文献\s*\n',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            # 返回从参考文献开始到文档结束的部分
            return text[match.end():]
    
    # 如果找不到明确的参考文献部分，返回后30%的内容（通常包含参考文献）
    return text[int(len(text) * 0.7):]


def parse_reference_line(ref_text: str, index: int) -> Optional[BibEntry]:
    """解析单条参考文献
    
    尝试从参考文献文本中提取标题、作者、年份等信息
    """
    ref_text = ref_text.strip()
    if not ref_text or len(ref_text) < 20:
        return None
    
    # 尝试提取年份
    year = None
    year_match = re.search(r'\(?(19|20)\d{2}\)?', ref_text)
    if year_match:
        year_str = year_match.group().strip('()')
        year = int(year_str)
    
    # 尝试提取作者（通常在开头，以年份或标题开始位置为界）
    authors = []
    
    # 常见格式: "Author1, Author2, and Author3 (2023). Title..."
    # 或: "Author1, A., Author2, B. (2023). Title..."
    author_section = ref_text
    if year_match:
        author_section = ref_text[:year_match.start()]
    
    # 清理作者部分
    author_section = author_section.strip().rstrip('.,')
    
    # 简单地按 "and" 或 "&" 分割
    if author_section:
        # 替换各种分隔符
        author_section = re.sub(r'\s+and\s+', ', ', author_section, flags=re.IGNORECASE)
        author_section = re.sub(r'\s*&\s*', ', ', author_section)
        
        # 按逗号分割，但要小心处理 "Last, First" 格式
        # 这里简化处理，假设用 ; 或 and 分隔不同作者
        author_parts = re.split(r'[;]|\s+and\s+', author_section, flags=re.IGNORECASE)
        
        for part in author_parts:
            part = part.strip().rstrip('.,')
            if part and len(part) > 1:
                # 进一步检查是否像作者名
                # 简单检查：包含字母，不是太长
                if re.search(r'[a-zA-Z]', part) and len(part) < 100:
                    authors.append(part)
    
    # 尝试提取标题
    title = ""
    
    # 标题通常在年份之后，用引号括起来或者是斜体
    # 格式1: ... (2023). "Title here." Journal...
    # 格式2: ... (2023). Title here. Journal...
    if year_match:
        after_year = ref_text[year_match.end():].strip().lstrip('.),:')
        
        # 尝试找引号内的标题
        quote_match = re.search(r'["""\'](.+?)["""\']', after_year)
        if quote_match:
            title = quote_match.group(1)
        else:
            # 否则取到下一个句号为止
            period_match = re.search(r'^(.+?)\.', after_year.strip())
            if period_match:
                title = period_match.group(1)
            else:
                # 取前100个字符作为标题
                title = after_year[:100].split('.')[0]
    
    # 清理标题
    title = title.strip().strip('"\'.,')
    
    if not title:
        return None
    
    # 生成key
    key = f"ref_{index}"
    if authors:
        first_author_last = authors[0].split()[-1].lower() if authors[0].split() else ""
        first_author_last = re.sub(r'[^a-z]', '', first_author_last)
        if first_author_last and year:
            key = f"{first_author_last}{year}"
        elif first_author_last:
            key = f"{first_author_last}_ref{index}"
    
    return BibEntry(
        key=key,
        entry_type="misc",
        title=title,
        authors=authors[:5],  # 限制作者数量
        year=year,
    )


def extract_references_from_pdf(pdf_path: Path) -> list[BibEntry]:
    """从PDF中提取参考文献
    
    Args:
        pdf_path: PDF文件路径
        
    Returns:
        提取的BibEntry列表
    """
    text = extract_text_from_pdf(pdf_path)
    ref_section = find_references_section(text)
    
    entries = []
    
    # 尝试按编号分割参考文献
    # 格式1: [1] Reference text...
    # 格式2: 1. Reference text...
    
    # 尝试 [n] 格式
    numbered_refs = re.split(r'\n\s*\[(\d+)\]\s*', ref_section)
    if len(numbered_refs) > 2:
        # 成功分割
        i = 1
        while i < len(numbered_refs):
            if i + 1 < len(numbered_refs):
                ref_text = numbered_refs[i + 1]
                entry = parse_reference_line(ref_text, int(numbered_refs[i]))
                if entry:
                    entries.append(entry)
            i += 2
    else:
        # 尝试 n. 格式
        numbered_refs = re.split(r'\n\s*(\d+)\.\s+', ref_section)
        if len(numbered_refs) > 2:
            i = 1
            while i < len(numbered_refs):
                if i + 1 < len(numbered_refs):
                    ref_text = numbered_refs[i + 1]
                    entry = parse_reference_line(ref_text, int(numbered_refs[i]))
                    if entry:
                        entries.append(entry)
                i += 2
        else:
            # 按段落分割
            paragraphs = re.split(r'\n\s*\n', ref_section)
            for idx, para in enumerate(paragraphs):
                entry = parse_reference_line(para, idx + 1)
                if entry:
                    entries.append(entry)
    
    return entries


def pdf_to_bib_entries(pdf_path: Path) -> tuple[list[BibEntry], set[str]]:
    """从PDF提取引用信息
    
    Args:
        pdf_path: PDF文件路径
        
    Returns:
        (entries, used_keys) - 条目列表和使用的key集合
        对于PDF，所有提取的引用都视为"已使用"
    """
    entries = extract_references_from_pdf(pdf_path)
    used_keys = {entry.key for entry in entries}
    return entries, used_keys
