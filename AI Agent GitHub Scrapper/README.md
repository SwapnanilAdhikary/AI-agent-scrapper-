# AI Agent GitHub Scraper

A Python CLI tool that reads GitHub repository URLs from a CSV file, scrapes each repo using the GitHub API, analyzes them with Anthropic Claude AI, and produces ranked reports as both CSV and Excel files.

## What It Does

1. **Reads** a CSV containing GitHub repo links
2. **Scrapes** each repo for metadata, dependency files, and README
3. **Analyzes** each repo with Claude AI to identify modules, purpose, tech stack, and quality scores
4. **Ranks** all repos and picks the top 3
5. **Outputs** a detailed CSV and a formatted Excel workbook

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Set Your Anthropic API Key

Copy the example env file and add your key:

```bash
cp .env.example .env
```

Then edit `.env`:

```
ANTHROPIC_API_KEY=sk-ant-your-key-here
```

### 3. Prepare Your Input CSV

Create a CSV file with a column containing GitHub URLs. The tool auto-detects the URL column. Example:

```csv
name,github_url
FastAPI,https://github.com/tiangolo/fastapi
Langchain,https://github.com/langchain-ai/langchain
Flask,https://github.com/pallets/flask
```

A `sample_input.csv` is included for testing.

## Usage

```bash
# Run with the sample input
python main.py

# Specify your own CSV and output directory
python main.py --input my_repos.csv --output ./my_results

# With a GitHub token (increases rate limit from 60 to 5000 requests/hour)
python main.py --input repos.csv --token ghp_your_token_here
```

### CLI Arguments

| Argument | Default | Description |
|---|---|---|
| `--input`, `-i` | `sample_input.csv` | Path to input CSV with GitHub URLs |
| `--output`, `-o` | `./results` | Output directory for reports |
| `--token`, `-t` | None | GitHub personal access token (optional) |

## Output

The tool generates two files in the output directory:

- **`github_analysis.csv`** — Flat CSV with all repos and their analysis
- **`github_analysis.xlsx`** — Formatted Excel with two sheets:
  - **All Repos** — Full detail for every repo
  - **Top 3 Rankings** — The top 3 repos with scores and justification

### Fields in the Report

| Field | Description |
|---|---|
| Rank | Position based on overall score |
| Repo Name | Full `owner/repo` name |
| URL | GitHub link |
| Purpose | AI-generated summary of what the repo does |
| Tech Stack | Key technologies used |
| Modules (Names) | Comma-separated dependency list |
| Modules (Detail) | Each module with category and description |
| Use Case Score | 1-10 rating of the project's usefulness |
| Code Quality Score | 1-10 rating inferred from structure and practices |
| Library Usage Score | 1-10 rating of dependency choices |
| Overall Score | 1-10 combined rating |
| Strengths | Key advantages |
| Weaknesses | Areas for improvement |

## Rate Limits

Without a GitHub token, the GitHub API allows 60 requests per hour. Each repo uses 3-5 API calls, so you can analyze roughly 12-15 repos per run. To increase this to 5000 requests/hour, provide a [GitHub personal access token](https://github.com/settings/tokens).

## Project Structure

```
main.py                 CLI entry point
github_scraper.py       GitHub API integration
ai_analyzer.py          Claude AI analysis engine
report_generator.py     CSV + Excel report builder
requirements.txt        Python dependencies
.env.example            API key template
sample_input.csv        Example input for testing
```
