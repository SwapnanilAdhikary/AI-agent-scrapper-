import json
import anthropic

ANALYSIS_MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS = 4096


def _build_prompt(repo_data: dict) -> str:
    """Build the analysis prompt from scraped repo data."""
    metadata = repo_data.get("metadata", {})
    dep_files = repo_data.get("dependency_files", {})
    readme = repo_data.get("readme", "")

    sections = []
    sections.append(f"# Repository: {metadata.get('full_name', repo_data.get('repo', 'Unknown'))}")
    sections.append(f"URL: {repo_data.get('url', '')}")
    sections.append(f"Description: {metadata.get('description', 'N/A')}")
    sections.append(f"Primary Language: {metadata.get('language', 'N/A')}")
    sections.append(f"Stars: {metadata.get('stars', 0)} | Forks: {metadata.get('forks', 0)}")
    sections.append(f"License: {metadata.get('license', 'N/A')}")
    sections.append(f"Topics: {', '.join(metadata.get('topics', [])) or 'None'}")
    sections.append(f"Last Updated: {metadata.get('updated_at', 'N/A')}")

    if dep_files:
        sections.append("\n## Dependency Files")
        for filename, content in dep_files.items():
            sections.append(f"\n### {filename}\n```\n{content}\n```")

    if readme:
        sections.append(f"\n## README (truncated)\n{readme}")

    return "\n".join(sections)


SYSTEM_PROMPT = """You are an expert software engineer and open-source analyst. You analyze GitHub repositories and provide structured assessments.

You MUST respond with valid JSON only — no markdown fences, no extra text. The JSON must follow this exact schema:

{
  "repo_name": "string — full repo name (owner/repo)",
  "repo_url": "string — GitHub URL",
  "purpose": "string — 2-3 sentence summary of what the project does and who it's for",
  "tech_stack": "string — concise summary like 'Python + FastAPI + Pydantic + SQLAlchemy'",
  "modules": [
    {
      "name": "string — package/module name",
      "version": "string — version if known, else 'N/A'",
      "category": "string — e.g. 'Web Framework', 'Database', 'Testing', 'CLI', 'AI/ML', 'Utility'",
      "description": "string — one sentence on what this module does in the project"
    }
  ],
  "use_case_score": "integer 1-10 — how useful/impactful is this project's use case",
  "code_quality_score": "integer 1-10 — inferred from structure, dependencies, and README quality",
  "library_usage_score": "integer 1-10 — how well-chosen and modern are the dependencies",
  "overall_score": "integer 1-10 — weighted average of all factors",
  "strengths": ["string — bullet point", "..."],
  "weaknesses": ["string — bullet point", "..."]
}

Score guidelines:
- 9-10: Exceptional, industry-leading
- 7-8: Very good, well-engineered
- 5-6: Decent, functional but room for improvement
- 3-4: Below average, notable issues
- 1-2: Poor, significant problems"""


def analyze_repo(repo_data: dict, api_key: str) -> dict:
    """
    Send scraped repo data to Claude for analysis.
    Returns a structured dict with the analysis results.
    """
    if "error" in repo_data:
        return {
            "repo_name": repo_data.get("repo", "Unknown"),
            "repo_url": repo_data.get("url", ""),
            "error": repo_data["error"],
            "purpose": "Could not analyze — scraping failed",
            "tech_stack": "N/A",
            "modules": [],
            "use_case_score": 0,
            "code_quality_score": 0,
            "library_usage_score": 0,
            "overall_score": 0,
            "strengths": [],
            "weaknesses": ["Failed to scrape repository data"],
        }

    prompt = _build_prompt(repo_data)

    client = anthropic.Anthropic(api_key=api_key)

    try:
        message = client.messages.create(
            model=ANALYSIS_MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": f"Analyze this GitHub repository and return your assessment as JSON:\n\n{prompt}",
                }
            ],
        )

        response_text = message.content[0].text.strip()

        if response_text.startswith("```"):
            lines = response_text.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            response_text = "\n".join(lines)

        analysis = json.loads(response_text)

        for key in ["use_case_score", "code_quality_score", "library_usage_score", "overall_score"]:
            if key in analysis:
                analysis[key] = int(analysis[key])

        return analysis

    except json.JSONDecodeError as e:
        return {
            "repo_name": repo_data.get("metadata", {}).get("full_name", "Unknown"),
            "repo_url": repo_data.get("url", ""),
            "error": f"Failed to parse Claude response as JSON: {e}",
            "purpose": "Analysis failed — invalid JSON response",
            "tech_stack": "N/A",
            "modules": [],
            "use_case_score": 0,
            "code_quality_score": 0,
            "library_usage_score": 0,
            "overall_score": 0,
            "strengths": [],
            "weaknesses": ["AI analysis returned invalid JSON"],
        }
    except Exception as e:
        return {
            "repo_name": repo_data.get("metadata", {}).get("full_name", "Unknown"),
            "repo_url": repo_data.get("url", ""),
            "error": str(e),
            "purpose": f"Analysis failed: {e}",
            "tech_stack": "N/A",
            "modules": [],
            "use_case_score": 0,
            "code_quality_score": 0,
            "library_usage_score": 0,
            "overall_score": 0,
            "strengths": [],
            "weaknesses": [f"Error during analysis: {e}"],
        }


def rank_repos(analyses: list[dict]) -> list[dict]:
    """
    Sort repos by overall_score descending and assign rank.
    Returns the full list with 'rank' field added; top 3 are flagged.
    """
    valid = [a for a in analyses if a.get("overall_score", 0) > 0]
    errored = [a for a in analyses if a.get("overall_score", 0) == 0]

    valid.sort(key=lambda x: x.get("overall_score", 0), reverse=True)

    for i, analysis in enumerate(valid, start=1):
        analysis["rank"] = i
        analysis["is_top_3"] = i <= 3

    for analysis in errored:
        analysis["rank"] = None
        analysis["is_top_3"] = False

    return valid + errored
