import os
import re
import sys
import argparse
import time
import pandas as pd
from dotenv import load_dotenv

from github_scraper import scrape_repo
from ai_analyzer import analyze_repo, rank_repos
from report_generator import generate_reports


def find_github_column(df: pd.DataFrame) -> str:
    """Auto-detect the column containing GitHub URLs."""
    for col in df.columns:
        sample = df[col].dropna().astype(str)
        if sample.str.contains(r"github\.com", case=False).any():
            return col

    for col in df.columns:
        col_lower = col.lower()
        if any(keyword in col_lower for keyword in ["url", "link", "github", "repo"]):
            return col

    raise ValueError(
        "Could not auto-detect a column with GitHub URLs. "
        "Ensure your CSV has a column containing github.com links."
    )


def load_input_file(path: str) -> list[str]:
    """Load input file (CSV or Excel) and extract GitHub URLs."""
    df = None

    # Try Excel first (handles .xlsx/.xls disguised as .csv too)
    try:
        df = pd.read_excel(path, engine="openpyxl")
    except Exception:
        pass

    # Fall back to CSV with encoding detection
    if df is None:
        for encoding in ["utf-8", "utf-8-sig", "cp1252", "latin-1", "iso-8859-1"]:
            try:
                df = pd.read_csv(path, encoding=encoding)
                break
            except (UnicodeDecodeError, pd.errors.ParserError):
                continue

    if df is None:
        df = pd.read_csv(path, encoding="latin-1")

    print(f"Loaded {len(df)} rows from {path}")

    col = find_github_column(df)
    print(f"Detected GitHub URL column: '{col}'")

    raw_values = df[col].dropna().astype(str).tolist()

    urls = []
    seen = set()
    for val in raw_values:
        # Split on whitespace to handle multiple URLs in one cell
        for token in val.split():
            token = token.strip()
            if "github.com" not in token.lower():
                continue
            # Strip /tree/... and /blob/... suffixes to get the repo root
            token = re.sub(r"/(tree|blob)/.*$", "", token)
            if token not in seen:
                seen.add(token)
                urls.append(token)

    if not urls:
        raise ValueError("No valid GitHub URLs found in the input file.")

    print(f"Found {len(urls)} unique GitHub URLs to analyze\n")
    return urls


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="AI Agent GitHub Scraper — Analyze GitHub repos with Claude AI"
    )
    parser.add_argument(
        "--input", "-i",
        default="sample_input.csv",
        help="Path to input CSV file containing GitHub URLs (default: sample_input.csv)",
    )
    parser.add_argument(
        "--output", "-o",
        default="./results",
        help="Output directory for generated reports (default: ./results)",
    )
    parser.add_argument(
        "--token", "-t",
        default=None,
        help="GitHub personal access token (optional, increases rate limit)",
    )
    args = parser.parse_args()

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set.")
        print("Create a .env file with: ANTHROPIC_API_KEY=your_key_here")
        print("Or set it as an environment variable.")
        sys.exit(1)

    github_token = args.token or os.getenv("GITHUB_TOKEN")

    print("=" * 60)
    print("  AI Agent GitHub Scraper")
    print("=" * 60)
    print()

    urls = load_input_file(args.input)

    print("-" * 60)
    print("PHASE 1: Scraping GitHub Repositories")
    print("-" * 60)

    scraped_repos = []
    for i, url in enumerate(urls, start=1):
        print(f"\n[{i}/{len(urls)}] {url}")
        repo_data = scrape_repo(url, token=github_token)
        scraped_repos.append(repo_data)

        if "error" in repo_data:
            print(f"  WARNING: {repo_data['error']}")
        else:
            meta = repo_data.get("metadata", {})
            deps = repo_data.get("dependency_files", {})
            print(f"  -> {meta.get('language', '?')} | {meta.get('stars', 0)} stars | {len(deps)} dep files found")

        if i < len(urls):
            time.sleep(1)

    print(f"\n\nScraping complete: {len(scraped_repos)} repos processed")

    print()
    print("-" * 60)
    print("PHASE 2: AI Analysis with Claude")
    print("-" * 60)

    analyses = []
    for i, repo_data in enumerate(scraped_repos, start=1):
        name = repo_data.get("metadata", {}).get("full_name", repo_data.get("url", "Unknown"))
        print(f"\n[{i}/{len(scraped_repos)}] Analyzing {name}...")

        analysis = analyze_repo(repo_data, api_key)
        analyses.append(analysis)

        score = analysis.get("overall_score", 0)
        if score > 0:
            print(f"  -> Score: {score}/10 | Stack: {analysis.get('tech_stack', 'N/A')}")
        else:
            print(f"  -> Analysis failed: {analysis.get('error', 'Unknown error')}")

        if i < len(scraped_repos):
            time.sleep(1)

    print(f"\n\nAnalysis complete: {len(analyses)} repos analyzed")

    print()
    print("-" * 60)
    print("PHASE 3: Ranking & Report Generation")
    print("-" * 60)

    ranked = rank_repos(analyses)

    csv_path, excel_path = generate_reports(ranked, args.output)

    print(f"\nReports generated:")
    print(f"  CSV:   {os.path.abspath(csv_path)}")
    print(f"  Excel: {os.path.abspath(excel_path)}")

    print()
    print("=" * 60)
    print("  TOP 3 REPOSITORIES")
    print("=" * 60)

    top3 = [a for a in ranked if a.get("is_top_3")]
    if top3:
        for a in top3:
            print(f"\n  #{a['rank']} — {a.get('repo_name', 'Unknown')} (Score: {a.get('overall_score', 0)}/10)")
            print(f"     {a.get('purpose', 'N/A')[:120]}")
            print(f"     Stack: {a.get('tech_stack', 'N/A')}")
    else:
        print("\n  No repos could be ranked (all analyses may have failed).")

    print()
    print("=" * 60)
    print("  Done!")
    print("=" * 60)


if __name__ == "__main__":
    main()
