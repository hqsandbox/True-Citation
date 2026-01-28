"""True-Citation CLI入口"""

import asyncio
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table
from rich.panel import Panel

from .config import load_config
from .models import BibEntry, VerificationStatus
from .parsers import parse_bib_file, extract_citations_from_multiple_tex
from .pdf_parser import pdf_to_bib_entries
from .reporter import ReportGenerator
from .verifier import Verifier

app = typer.Typer(
    name="true-citation",
    help="论文引用真实性验证工具",
    add_completion=False,
)
console = Console()


def print_summary(results: list) -> None:
    """打印验证结果摘要"""
    counts = {status: 0 for status in VerificationStatus}
    for result in results:
        counts[result.status] += 1
    
    total = len(results)
    
    table = Table(title="验证结果摘要", show_header=True)
    table.add_column("状态", style="bold")
    table.add_column("数量", justify="right")
    table.add_column("占比", justify="right")
    
    if counts[VerificationStatus.VERIFIED] > 0:
        table.add_row(
            "✅ 已验证", 
            str(counts[VerificationStatus.VERIFIED]),
            f"{counts[VerificationStatus.VERIFIED]/total*100:.1f}%"
        )
    if counts[VerificationStatus.SUSPICIOUS] > 0:
        table.add_row(
            "⚠️  可疑", 
            str(counts[VerificationStatus.SUSPICIOUS]),
            f"{counts[VerificationStatus.SUSPICIOUS]/total*100:.1f}%"
        )
    if counts[VerificationStatus.ERROR] > 0:
        table.add_row(
            "❌ 错误", 
            str(counts[VerificationStatus.ERROR]),
            f"{counts[VerificationStatus.ERROR]/total*100:.1f}%"
        )
    if counts[VerificationStatus.SKIPPED] > 0:
        table.add_row(
            "⏭️  跳过", 
            str(counts[VerificationStatus.SKIPPED]),
            f"{counts[VerificationStatus.SKIPPED]/total*100:.1f}%"
        )
    
    table.add_row("", "", "", style="dim")
    table.add_row("总计", str(total), "100%", style="bold")
    
    console.print(table)


@app.command()
def verify(
    bib: Optional[Path] = typer.Option(
        None, "--bib", "-b",
        help="BibTeX文件路径",
        exists=True,
        file_okay=True,
        dir_okay=False,
    ),
    tex: Optional[list[Path]] = typer.Option(
        None, "--tex", "-t",
        help="LaTeX文件路径（可多次指定）",
        exists=True,
        file_okay=True,
        dir_okay=False,
    ),
    pdf: Optional[Path] = typer.Option(
        None, "--pdf", "-p",
        help="PDF文件路径（直接从PDF提取引用）",
        exists=True,
        file_okay=True,
        dir_okay=False,
    ),
    config_path: Optional[Path] = typer.Option(
        None, "--config", "-c",
        help="配置文件路径",
        exists=True,
        file_okay=True,
        dir_okay=False,
    ),
    format: str = typer.Option(
        "markdown", "--format", "-f",
        help="报告格式 (markdown, json, html)",
    ),
    output_dir: Optional[Path] = typer.Option(
        None, "--output", "-o",
        help="输出目录",
    ),
    no_report: bool = typer.Option(
        False, "--no-report",
        help="不生成报告文件",
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v",
        help="显示详细输出",
    ),
) -> None:
    """验证论文引用的真实性"""
    
    # 检查输入参数
    if pdf is None and (bib is None or not tex):
        console.print("[red]错误: 必须提供 --pdf 或者 (--bib 和 --tex)[/red]")
        raise typer.Exit(1)
    
    # 加载配置
    config = load_config(config_path)
    
    if output_dir:
        config.output.output_dir = str(output_dir)
    
    console.print(Panel.fit(
        "[bold blue]🔍 True-Citation[/bold blue]\n论文引用真实性验证工具",
        border_style="blue"
    ))
    
    # 获取待验证的条目
    entries: dict[str, BibEntry] = {}
    used_keys: set[str] = set()
    
    if pdf:
        console.print(f"\n📄 从PDF提取引用: [cyan]{pdf}[/cyan]")
        entries_list, used_keys = pdf_to_bib_entries(pdf)
        entries = {e.key: e for e in entries_list}
        console.print(f"   提取到 {len(entries)} 条引用")
    else:
        # 解析BibTeX
        console.print(f"\n📚 解析BibTeX: [cyan]{bib}[/cyan]")
        entries = parse_bib_file(bib)
        console.print(f"   共 {len(entries)} 条引用记录")
        
        # 提取TeX中使用的引用
        console.print(f"\n📝 解析LaTeX文件:")
        for tex_file in tex:
            console.print(f"   - [cyan]{tex_file}[/cyan]")
        used_keys = extract_citations_from_multiple_tex(tex)
        console.print(f"   共使用 {len(used_keys)} 条引用")
    
    # 过滤出需要验证的条目
    entries_to_verify = []
    missing_keys = []
    for key in used_keys:
        if key in entries:
            entries_to_verify.append(entries[key])
        else:
            missing_keys.append(key)
    
    # 报告在TeX中引用但BibTeX中缺失的key
    if missing_keys:
        console.print(f"\n[yellow]⚠️  {len(missing_keys)} 条引用在BibTeX中未找到:[/yellow]")
        for key in missing_keys:
            console.print(f"   - [yellow]{key}[/yellow]")
    
    if not entries_to_verify:
        console.print("\n[yellow]⚠️  没有需要验证的引用[/yellow]")
        raise typer.Exit(0)
    
    console.print(f"\n🔎 开始验证 {len(entries_to_verify)} 条引用...\n")
    
    # 执行验证
    verifier = Verifier(config)
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("验证中...", total=len(entries_to_verify))
        
        def update_progress(completed: int, total: int):
            progress.update(task, completed=completed)
        
        results = asyncio.run(
            verifier.verify_entries(entries_to_verify, progress_callback=update_progress)
        )
    
    # 打印摘要
    console.print()
    print_summary(results)
    
    # 打印详细结果（如果有问题的）
    problem_results = [
        r for r in results 
        if r.status in (VerificationStatus.ERROR, VerificationStatus.SUSPICIOUS)
    ]
    
    if problem_results and verbose:
        console.print("\n[bold]问题引用详情:[/bold]\n")
        for result in problem_results:
            console.print(f"{result.status_emoji} [bold][{result.entry.key}][/bold]")
            console.print(f"   标题: {result.entry.title[:60]}...")
            console.print(f"   问题: {result.message}")
            if result.corrected_entry:
                console.print("   [dim]已生成修正建议，详见报告[/dim]")
            console.print()
    
    # 生成报告
    if not no_report:
        output_path = Path(config.output.output_dir)
        reporter = ReportGenerator(results, output_path)
        
        report_path = reporter.save_report(format)
        console.print(f"\n📋 报告已保存: [green]{report_path}[/green]")
        
        if config.output.generate_corrected_bib:
            bib_path = reporter.save_corrected_bib()
            console.print(f"📝 修正BibTeX: [green]{bib_path}[/green]")
    
    # 返回退出码
    error_count = sum(1 for r in results if r.status == VerificationStatus.ERROR)
    if error_count > 0:
        raise typer.Exit(1)


@app.command()
def init():
    """初始化配置文件"""
    config_path = Path("config.yaml")
    example_path = Path(__file__).parent.parent / "config.example.yaml"
    
    if config_path.exists():
        console.print("[yellow]config.yaml 已存在[/yellow]")
        overwrite = typer.confirm("是否覆盖?")
        if not overwrite:
            raise typer.Exit(0)
    
    # 复制示例配置
    if example_path.exists():
        import shutil
        shutil.copy(example_path, config_path)
    else:
        # 创建默认配置
        default_config = """# True-Citation 配置文件

semantic_scholar:
  api_key: ""

crossref:
  email: ""

openalex:
  email: ""

serpapi:
  api_key: ""

dblp:
  enabled: true

verification:
  title_similarity_threshold: 0.85
  min_author_match: 1
  year_tolerance: 1
  max_concurrent_requests: 3
  request_delay: 0.5

output:
  report_format: markdown
  generate_corrected_bib: true
  output_dir: "./output"
"""
        with open(config_path, 'w', encoding='utf-8') as f:
            f.write(default_config)
    
    console.print(f"[green]✅ 配置文件已创建: {config_path}[/green]")
    console.print("请编辑配置文件填入你的API密钥（大多数API无需密钥也可使用）")


def main():
    """主入口"""
    app()


if __name__ == "__main__":
    main()
