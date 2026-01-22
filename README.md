# True-Citation: 论文引用真实性验证工具

一个用于验证学术论文引用真实性的Python命令行工具。

## 功能特性

- **BibTeX + LaTeX 验证**: 解析 `.bib` 文件，只检查 `.tex` 文件中实际使用的引用
- **PDF 验证**: 直接从 PDF 文件提取引用信息并验证
- **多源交叉验证**: 通过 Semantic Scholar、CrossRef、OpenAlex、DBLP 等多个学术数据库验证
- **智能匹配**: 使用模糊匹配算法比对标题、作者、年份等信息
- **修正建议**: 对于错误或可疑的引用，提供正确的 BibTeX 条目（含 URL）
- **详细报告**: 生成 Markdown/JSON/HTML 格式的验证报告

## 安装

```bash
# 克隆仓库
git clone https://github.com/hqsandbox/True-Citation
cd True-Citation

# 安装依赖
pip install -r requirements.txt

# 复制配置文件
cp config.example.yaml config.yaml
```

## 配置

该部分可跳过（可以不用 API，但用了会更快）。如要配置，可编辑 `config.yaml` 文件，填入你的 API 密钥：

```yaml
semantic_scholar:
  api_key: "your-api-key"  # 可选，提高速率限制

crossref:
  email: "your-email@example.com"  # 建议填写
```

## 使用方法

### 验证 BibTeX + LaTeX 文件

```bash
# 基本用法
python -m true_citation verify --bib references.bib --tex main.tex

# 多个 tex 文件
python -m true_citation verify --bib references.bib --tex main.tex --tex appendix.tex

# 指定输出格式
python -m true_citation verify --bib references.bib --tex main.tex --format markdown

# 指定配置文件
python -m true_citation verify --bib references.bib --tex main.tex --config my_config.yaml
```

### 验证 PDF 文件

```bash
python -m true_citation verify --pdf paper.pdf
```

### 输出示例

```
🔍 True-Citation 验证报告

✅ 已验证 (15/20)
❌ 错误 (3/20)
⚠️ 可疑 (2/20)

--- 详细结果 ---

❌ [smith2023deep] Smith et al. "Deep Learning for NLP"
   问题: 标题不匹配，未找到此作者的该论文
   建议修正:
   @article{smith2023deep,
     author = {Smith, John and Doe, Jane},
     title = {Deep Learning Methods for Natural Language Processing},
     journal = {ACL},
     year = {2023},
     url = {https://aclanthology.org/...}
   }
```

## 验证逻辑

1. **解析输入**: 从 BibTeX 提取引用元数据，从 TeX 提取使用的引用键
2. **过滤**: 只验证 TeX 中实际使用的引用
3. **搜索**: 在多个学术数据库中搜索每条引用
4. **匹配**: 比对标题相似度、作者匹配、年份等
5. **判定**: 
   - ✅ **已验证**: 在数据库中找到高度匹配的记录
   - ⚠️ **可疑**: 部分匹配，可能有小错误
   - ❌ **错误**: 未找到匹配或严重不匹配
6. **修正**: 对错误/可疑项生成修正后的 BibTeX

## API 说明

| API | 免费 | 需要Key | 说明 |
|-----|------|---------|------|
| Semantic Scholar | ✅ | 可选 | 综合学术搜索，有key速率更高 |
| CrossRef | ✅ | 否 | DOI 元数据，填邮箱速率更高 |
| OpenAlex | ✅ | 否 | 开放学术图谱 |
| DBLP | ✅ | 否 | 计算机科学文献 |
| SerpAPI | ❌ | 必需 | Google Scholar 搜索 |

## License

MIT
