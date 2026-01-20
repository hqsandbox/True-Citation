"""配置管理"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml


@dataclass
class SemanticScholarConfig:
    api_key: str = ""


@dataclass
class CrossRefConfig:
    email: str = ""


@dataclass
class OpenAlexConfig:
    email: str = ""


@dataclass
class SerpAPIConfig:
    api_key: str = ""


@dataclass
class DBLPConfig:
    enabled: bool = True


@dataclass
class VerificationConfig:
    title_similarity_threshold: float = 0.85
    min_author_match: int = 1
    year_tolerance: int = 1
    max_concurrent_requests: int = 3
    request_delay: float = 0.5


@dataclass
class OutputConfig:
    report_format: str = "markdown"
    generate_corrected_bib: bool = True
    output_dir: str = "./output"


@dataclass
class Config:
    semantic_scholar: SemanticScholarConfig = field(default_factory=SemanticScholarConfig)
    crossref: CrossRefConfig = field(default_factory=CrossRefConfig)
    openalex: OpenAlexConfig = field(default_factory=OpenAlexConfig)
    serpapi: SerpAPIConfig = field(default_factory=SerpAPIConfig)
    dblp: DBLPConfig = field(default_factory=DBLPConfig)
    verification: VerificationConfig = field(default_factory=VerificationConfig)
    output: OutputConfig = field(default_factory=OutputConfig)


def load_config(config_path: Optional[Path] = None) -> Config:
    """加载配置文件
    
    Args:
        config_path: 配置文件路径，默认为当前目录下的config.yaml
        
    Returns:
        Config对象
    """
    if config_path is None:
        config_path = Path("config.yaml")
    
    config = Config()
    
    if not config_path.exists():
        return config
    
    with open(config_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f) or {}
    
    # 解析各部分配置
    if 'semantic_scholar' in data:
        ss = data['semantic_scholar']
        config.semantic_scholar = SemanticScholarConfig(
            api_key=ss.get('api_key', '')
        )
    
    if 'crossref' in data:
        cr = data['crossref']
        config.crossref = CrossRefConfig(
            email=cr.get('email', '')
        )
    
    if 'openalex' in data:
        oa = data['openalex']
        config.openalex = OpenAlexConfig(
            email=oa.get('email', '')
        )
    
    if 'serpapi' in data:
        sp = data['serpapi']
        config.serpapi = SerpAPIConfig(
            api_key=sp.get('api_key', '')
        )
    
    if 'dblp' in data:
        db = data['dblp']
        config.dblp = DBLPConfig(
            enabled=db.get('enabled', True)
        )
    
    if 'verification' in data:
        v = data['verification']
        config.verification = VerificationConfig(
            title_similarity_threshold=v.get('title_similarity_threshold', 0.85),
            min_author_match=v.get('min_author_match', 1),
            year_tolerance=v.get('year_tolerance', 1),
            max_concurrent_requests=v.get('max_concurrent_requests', 3),
            request_delay=v.get('request_delay', 0.5),
        )
    
    if 'output' in data:
        o = data['output']
        config.output = OutputConfig(
            report_format=o.get('report_format', 'markdown'),
            generate_corrected_bib=o.get('generate_corrected_bib', True),
            output_dir=o.get('output_dir', './output'),
        )
    
    return config
