"""学术搜索API客户端"""

import asyncio
import logging
import re
from abc import ABC, abstractmethod
from typing import Optional
from urllib.parse import quote

import httpx

from .config import Config
from .models import BibEntry, SearchResult

logger = logging.getLogger(__name__)


class BaseSearchClient(ABC):
    """搜索客户端基类"""
    
    def __init__(self, config: Config):
        self.config = config
    
    @abstractmethod
    async def search(self, entry: BibEntry) -> list[SearchResult]:
        """搜索论文
        
        Args:
            entry: 要搜索的BibTeX条目
            
        Returns:
            搜索结果列表
        """
        pass
    
    @property
    @abstractmethod
    def source_name(self) -> str:
        """返回数据源名称"""
        pass


class SemanticScholarClient(BaseSearchClient):
    """Semantic Scholar API客户端"""
    
    BASE_URL = "https://api.semanticscholar.org/graph/v1"
    
    @property
    def source_name(self) -> str:
        return "semantic_scholar"
    
    async def search(self, entry: BibEntry) -> list[SearchResult]:
        results = []
        
        headers = {}
        if self.config.semantic_scholar.api_key:
            headers["x-api-key"] = self.config.semantic_scholar.api_key
        
        # 构建搜索查询
        query = entry.title
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(
                    f"{self.BASE_URL}/paper/search",
                    params={
                        "query": query,
                        "limit": 5,
                        "fields": "title,authors,year,venue,externalIds,url"
                    },
                    headers=headers
                )
                response.raise_for_status()
                data = response.json()
                
                for paper in data.get("data", []):
                    authors = [
                        a.get("name", "") 
                        for a in paper.get("authors", [])
                    ]
                    
                    external_ids = paper.get("externalIds", {}) or {}
                    doi = external_ids.get("DOI")
                    
                    result = SearchResult(
                        source=self.source_name,
                        title=paper.get("title", ""),
                        authors=authors,
                        year=paper.get("year"),
                        doi=doi,
                        url=paper.get("url", ""),
                        journal=paper.get("venue", ""),
                    )
                    results.append(result)
                    
            except Exception as e:
                # 静默处理错误，返回空结果
                pass
        
        return results


class CrossRefClient(BaseSearchClient):
    """CrossRef API客户端"""
    
    BASE_URL = "https://api.crossref.org/works"
    
    @property
    def source_name(self) -> str:
        return "crossref"
    
    async def search(self, entry: BibEntry) -> list[SearchResult]:
        results = []
        
        headers = {
            "User-Agent": "TrueCitation/0.1.0 (https://github.com/true-citation)"
        }
        if self.config.crossref.email:
            headers["User-Agent"] += f" (mailto:{self.config.crossref.email})"
        
        # 构建查询
        query = entry.title
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                params = {
                    "query.title": query,
                    "rows": 5,
                }
                
                # 如果有作者信息，添加作者查询
                if entry.authors:
                    # 取第一个作者的姓氏
                    first_author = entry.authors[0]
                    last_name = first_author.split()[-1] if first_author else ""
                    if last_name:
                        params["query.author"] = last_name
                
                response = await client.get(
                    self.BASE_URL,
                    params=params,
                    headers=headers
                )
                response.raise_for_status()
                data = response.json()
                
                for item in data.get("message", {}).get("items", []):
                    # 解析作者
                    authors = []
                    for author in item.get("author", []):
                        given = author.get("given", "")
                        family = author.get("family", "")
                        if given and family:
                            authors.append(f"{given} {family}")
                        elif family:
                            authors.append(family)
                    
                    # 获取标题
                    titles = item.get("title", [])
                    title = titles[0] if titles else ""
                    
                    # 获取年份
                    year = None
                    published = item.get("published", {})
                    date_parts = published.get("date-parts", [[]])
                    if date_parts and date_parts[0]:
                        year = date_parts[0][0]
                    
                    # 获取URL
                    url = item.get("URL", "")
                    
                    # 获取期刊/会议名称
                    container = item.get("container-title", [])
                    journal = container[0] if container else ""
                    
                    result = SearchResult(
                        source=self.source_name,
                        title=title,
                        authors=authors,
                        year=year,
                        doi=item.get("DOI"),
                        url=url,
                        journal=journal,
                        volume=item.get("volume"),
                        pages=item.get("page"),
                    )
                    results.append(result)
                    
            except Exception as e:
                pass
        
        return results


class OpenAlexClient(BaseSearchClient):
    """OpenAlex API客户端"""
    
    BASE_URL = "https://api.openalex.org/works"
    
    @property
    def source_name(self) -> str:
        return "openalex"
    
    async def search(self, entry: BibEntry) -> list[SearchResult]:
        results = []
        
        headers = {}
        if self.config.openalex.email:
            headers["User-Agent"] = f"mailto:{self.config.openalex.email}"
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                # OpenAlex搜索
                params = {
                    "search": entry.title,
                    "per_page": 5,
                }
                
                response = await client.get(
                    self.BASE_URL,
                    params=params,
                    headers=headers
                )
                response.raise_for_status()
                data = response.json()
                
                for work in data.get("results", []):
                    # 解析作者
                    authors = []
                    for authorship in work.get("authorships", []):
                        author = authorship.get("author", {})
                        name = author.get("display_name", "")
                        if name:
                            authors.append(name)
                    
                    # 获取年份
                    year = work.get("publication_year")
                    
                    # 获取DOI
                    doi = work.get("doi", "")
                    if doi and doi.startswith("https://doi.org/"):
                        doi = doi.replace("https://doi.org/", "")
                    
                    # 获取期刊
                    primary_location = work.get("primary_location", {}) or {}
                    source = primary_location.get("source", {}) or {}
                    journal = source.get("display_name", "")
                    
                    result = SearchResult(
                        source=self.source_name,
                        title=work.get("title", ""),
                        authors=authors,
                        year=year,
                        doi=doi,
                        url=work.get("id", ""),
                        journal=journal,
                    )
                    results.append(result)
                    
            except Exception as e:
                pass
        
        return results


class DBLPClient(BaseSearchClient):
    """DBLP API客户端"""
    
    BASE_URL = "https://dblp.org/search/publ/api"
    
    @property
    def source_name(self) -> str:
        return "dblp"
    
    async def search(self, entry: BibEntry) -> list[SearchResult]:
        if not self.config.dblp.enabled:
            return []
        
        results = []
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                params = {
                    "q": entry.title,
                    "format": "json",
                    "h": 5,  # 返回数量
                }
                
                response = await client.get(
                    self.BASE_URL,
                    params=params
                )
                response.raise_for_status()
                data = response.json()
                
                hits = data.get("result", {}).get("hits", {}).get("hit", [])
                
                for hit in hits:
                    info = hit.get("info", {})
                    
                    # 解析作者
                    authors_data = info.get("authors", {}).get("author", [])
                    if isinstance(authors_data, dict):
                        authors_data = [authors_data]
                    authors = []
                    for a in authors_data:
                        if isinstance(a, dict):
                            authors.append(a.get("text", ""))
                        else:
                            authors.append(str(a))
                    
                    # 获取年份
                    year_str = info.get("year", "")
                    year = int(year_str) if year_str.isdigit() else None
                    
                    # 获取URL
                    url = info.get("ee", "")
                    if isinstance(url, list):
                        url = url[0] if url else ""
                    
                    # 获取DOI
                    doi = None
                    if url and "doi.org" in url:
                        doi = url.split("doi.org/")[-1]
                    
                    result = SearchResult(
                        source=self.source_name,
                        title=info.get("title", "").rstrip('.'),
                        authors=authors,
                        year=year,
                        doi=doi,
                        url=url,
                        journal=info.get("venue", ""),
                        booktitle=info.get("venue", ""),
                        volume=info.get("volume"),
                        pages=info.get("pages"),
                    )
                    results.append(result)
                    
            except Exception as e:
                pass
        
        return results


class SerpAPIClient(BaseSearchClient):
    """SerpAPI (Google Scholar) 客户端"""
    
    BASE_URL = "https://serpapi.com/search"
    
    @property
    def source_name(self) -> str:
        return "google_scholar"
    
    async def search(self, entry: BibEntry) -> list[SearchResult]:
        if not self.config.serpapi.api_key:
            return []
        
        results = []
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                params = {
                    "engine": "google_scholar",
                    "q": entry.title,
                    "api_key": self.config.serpapi.api_key,
                    "num": 5,
                }
                
                response = await client.get(
                    self.BASE_URL,
                    params=params
                )
                response.raise_for_status()
                data = response.json()
                
                for result_item in data.get("organic_results", []):
                    # 解析作者和年份从snippet
                    snippet = result_item.get("publication_info", {}).get("summary", "")
                    
                    # 尝试提取年份
                    year = None
                    year_match = re.search(r'\b(19|20)\d{2}\b', snippet)
                    if year_match:
                        year = int(year_match.group())
                    
                    # 尝试提取作者
                    authors = []
                    authors_str = result_item.get("publication_info", {}).get("authors", [])
                    if authors_str:
                        for a in authors_str:
                            authors.append(a.get("name", ""))
                    
                    result = SearchResult(
                        source=self.source_name,
                        title=result_item.get("title", ""),
                        authors=authors,
                        year=year,
                        url=result_item.get("link", ""),
                    )
                    results.append(result)
                    
            except Exception as e:
                pass
        
        return results


class SearchManager:
    """搜索管理器，协调多个搜索客户端"""
    
    def __init__(self, config: Config):
        self.config = config
        self.clients: list[BaseSearchClient] = [
            SemanticScholarClient(config),
            CrossRefClient(config),
            OpenAlexClient(config),
            DBLPClient(config),
            SerpAPIClient(config),
        ]
    
    async def search_all(self, entry: BibEntry) -> list[SearchResult]:
        """在所有数据源中搜索（不带重试）
        
        Args:
            entry: 要搜索的BibTeX条目
            
        Returns:
            所有数据源的搜索结果合并
        """
        tasks = [client.search(entry) for client in self.clients]
        results_lists = await asyncio.gather(*tasks, return_exceptions=True)
        
        all_results = []
        for i, results in enumerate(results_lists):
            if isinstance(results, list):
                all_results.extend(results)
            elif isinstance(results, Exception):
                logger.debug(f"{self.clients[i].source_name} 搜索失败: {results}")
        
        return all_results
    
    async def _search_with_retry(
        self, client: BaseSearchClient, entry: BibEntry, max_retries: int = 2
    ) -> list[SearchResult]:
        """带重试的单个客户端搜索"""
        last_exception = None
        for attempt in range(max_retries + 1):
            try:
                return await client.search(entry)
            except Exception as e:
                last_exception = e
                if attempt < max_retries:
                    await asyncio.sleep(1.0 * (attempt + 1))
                    logger.debug(
                        f"{client.source_name} 搜索失败 (尝试 {attempt + 1}/{max_retries + 1}): {e}"
                    )
        
        logger.warning(f"{client.source_name} 搜索最终失败: {last_exception}")
        return []
    
    async def search_all_with_retry(self, entry: BibEntry, max_retries: int = 2) -> list[SearchResult]:
        """在所有数据源中搜索（带重试）
        
        Args:
            entry: 要搜索的BibTeX条目
            max_retries: 每个数据源最大重试次数
            
        Returns:
            所有数据源的搜索结果合并
        """
        tasks = [self._search_with_retry(client, entry, max_retries) for client in self.clients]
        results_lists = await asyncio.gather(*tasks)
        
        all_results = []
        for results in results_lists:
            all_results.extend(results)
        
        return all_results
