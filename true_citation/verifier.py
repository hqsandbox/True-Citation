"""引用验证核心逻辑"""

import asyncio
import re
from typing import Optional

from rapidfuzz import fuzz

from .config import Config
from .models import BibEntry, SearchResult, VerificationResult, VerificationStatus
from .search import SearchManager


def normalize_title(title: str) -> str:
    """标准化标题用于比较"""
    # 转小写
    title = title.lower()
    # 移除标点符号
    title = re.sub(r'[^\w\s]', '', title)
    # 合并空格
    title = re.sub(r'\s+', ' ', title).strip()
    return title


def normalize_author_name(name: str) -> str:
    """标准化作者名用于比较"""
    name = name.lower()
    # 移除标点
    name = re.sub(r'[^\w\s]', '', name)
    # 合并空格
    name = re.sub(r'\s+', ' ', name).strip()
    return name


def get_author_last_name(name: str) -> str:
    """提取作者姓氏"""
    name = normalize_author_name(name)
    parts = name.split()
    return parts[-1] if parts else ""


def calculate_title_similarity(title1: str, title2: str) -> float:
    """计算标题相似度 (0-1)"""
    if not title1 or not title2:
        return 0.0
    t1 = normalize_title(title1)
    t2 = normalize_title(title2)
    
    if not t1 or not t2:
        return 0.0
    
    # 使用多种相似度算法取最高分
    ratio = fuzz.ratio(t1, t2) / 100.0
    partial_ratio = fuzz.partial_ratio(t1, t2) / 100.0
    token_sort = fuzz.token_sort_ratio(t1, t2) / 100.0
    
    return max(ratio, partial_ratio, token_sort)


def count_author_matches(authors1: list[str], authors2: list[str]) -> int:
    """计算匹配的作者数量（基于姓氏）"""
    if not authors1 or not authors2:
        return 0
    
    last_names1 = {get_author_last_name(a) for a in authors1 if a}
    last_names2 = {get_author_last_name(a) for a in authors2 if a}
    
    # 移除空字符串
    last_names1.discard("")
    last_names2.discard("")
    
    return len(last_names1 & last_names2)


def check_year_match(year1: Optional[int], year2: Optional[int], tolerance: int = 1) -> bool:
    """检查年份是否匹配（允许一定误差）"""
    if year1 is None or year2 is None:
        return True  # 如果缺少年份信息，不作为不匹配的依据
    
    return abs(year1 - year2) <= tolerance


def calculate_overall_score(
    title_similarity: float,
    author_match_count: int,
    total_authors: int,
    year_match: bool,
    has_doi_match: bool
) -> float:
    """计算综合匹配得分"""
    score = 0.0
    
    # 标题相似度权重最高 (50%)
    score += title_similarity * 0.5
    
    # 作者匹配 (30%)
    if total_authors > 0:
        author_ratio = min(author_match_count / max(total_authors, 1), 1.0)
        score += author_ratio * 0.3
    else:
        # 如果没有作者信息，给一个中等分数
        score += 0.15
    
    # 年份匹配 (10%)
    if year_match:
        score += 0.1
    
    # DOI匹配 (10%)
    if has_doi_match:
        score += 0.1
    
    return score


def score_search_result(entry: BibEntry, result: SearchResult, config: Config) -> SearchResult:
    """为搜索结果计算匹配得分"""
    # 计算标题相似度
    result.title_similarity = calculate_title_similarity(entry.title, result.title)
    
    # 计算作者匹配数
    result.author_match_count = count_author_matches(entry.authors, result.authors)
    
    # 检查年份匹配
    result.year_match = check_year_match(
        entry.year, 
        result.year, 
        config.verification.year_tolerance
    )
    
    # 检查DOI匹配
    has_doi_match = False
    if entry.doi and result.doi:
        has_doi_match = entry.doi.lower() == result.doi.lower()
    
    # 计算综合得分
    result.overall_score = calculate_overall_score(
        result.title_similarity,
        result.author_match_count,
        len(entry.authors),
        result.year_match,
        has_doi_match
    )
    
    return result


def create_corrected_entry(entry: BibEntry, match: SearchResult) -> BibEntry:
    """基于搜索结果创建修正后的BibTeX条目"""
    return BibEntry(
        key=entry.key,
        entry_type=entry.entry_type,
        title=match.title or entry.title,
        authors=match.authors if match.authors else entry.authors,
        year=match.year or entry.year,
        journal=match.journal or entry.journal,
        booktitle=match.booktitle or entry.booktitle,
        volume=match.volume or entry.volume,
        pages=match.pages or entry.pages,
        doi=match.doi or entry.doi,
        url=match.url or entry.url,
        publisher=entry.publisher,
    )


class Verifier:
    """引用验证器"""
    
    def __init__(self, config: Config):
        self.config = config
        self.search_manager = SearchManager(config)
    
    async def verify_entry(self, entry: BibEntry) -> VerificationResult:
        """验证单个引用条目"""
        # 搜索
        search_results = await self.search_manager.search_all(entry)
        
        if not search_results:
            return VerificationResult(
                entry=entry,
                status=VerificationStatus.ERROR,
                message="在所有数据源中均未找到匹配记录",
                search_results=[],
            )
        
        # 为每个结果计算得分
        scored_results = [
            score_search_result(entry, result, self.config)
            for result in search_results
        ]
        
        # 按得分排序
        scored_results.sort(key=lambda x: x.overall_score, reverse=True)
        
        best_match = scored_results[0]
        
        # 判定状态
        threshold = self.config.verification.title_similarity_threshold
        min_authors = self.config.verification.min_author_match
        
        if best_match.title_similarity >= threshold:
            if best_match.author_match_count >= min_authors or not entry.authors:
                status = VerificationStatus.VERIFIED
                message = f"已验证 (标题相似度: {best_match.title_similarity:.1%}, 来源: {best_match.source})"
            else:
                status = VerificationStatus.SUSPICIOUS
                message = f"标题匹配但作者不一致 (匹配{best_match.author_match_count}/{len(entry.authors)}位作者)"
        elif best_match.title_similarity >= 0.6:
            status = VerificationStatus.SUSPICIOUS
            message = f"部分匹配 (标题相似度: {best_match.title_similarity:.1%})"
        else:
            status = VerificationStatus.ERROR
            message = f"未找到可靠匹配 (最高相似度: {best_match.title_similarity:.1%})"
        
        # 如果不是完全验证通过，生成修正建议
        corrected_entry = None
        if status != VerificationStatus.VERIFIED and best_match.title_similarity >= 0.5:
            corrected_entry = create_corrected_entry(entry, best_match)
        
        return VerificationResult(
            entry=entry,
            status=status,
            message=message,
            search_results=scored_results[:5],  # 只保留前5个结果
            best_match=best_match,
            corrected_entry=corrected_entry,
        )
    
    async def verify_entries(
        self, 
        entries: list[BibEntry],
        progress_callback=None
    ) -> list[VerificationResult]:
        """验证多个引用条目
        
        Args:
            entries: 要验证的条目列表
            progress_callback: 进度回调函数，签名为 (completed, total)
        """
        results = []
        semaphore = asyncio.Semaphore(self.config.verification.max_concurrent_requests)
        
        async def verify_with_semaphore(entry: BibEntry, index: int) -> VerificationResult:
            async with semaphore:
                result = await self.verify_entry(entry)
                if progress_callback:
                    progress_callback(index + 1, len(entries))
                # 添加延迟避免请求过快
                await asyncio.sleep(self.config.verification.request_delay)
                return result
        
        tasks = [
            verify_with_semaphore(entry, i) 
            for i, entry in enumerate(entries)
        ]
        
        results = await asyncio.gather(*tasks)
        return list(results)
