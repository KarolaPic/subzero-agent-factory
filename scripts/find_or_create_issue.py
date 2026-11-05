#!/usr/bin/env python3
"""
Find or create an issue for $run-epic.

Accepts either an explicit issue reference (#N, issue N, N) or a plain text request.
- Explicit issue: returns the issue number immediately.
- Plain text request:
  1. Checks if request is unclear (too short, vague terms without specifics).
  2. Searches open issues for:
     a) Exact hidden idempotency marker: <!-- run-epic-request: <normalized> -->
     b) Exact normalized title match.
     c) Significant keyword / semantic overlap.
  3. Outcomes:
     - One clear match -> returns match details.
     - Multiple candidate matches -> returns multiple_matches with candidates so runner can ask César.
     - Unclear request -> returns unclear status with reason so runner can ask César.
     - No match -> creates a new issue with a complete task card (Goal, Done when, Don't touch),
       labels it 'agent' (and 'epic' if requested), includes the hidden marker, and validates the task card.
"""

import argparse
import json
import os
import re
import subprocess
import sys
from typing import Any, Dict, List, Optional, Tuple

STOP_WORDS = {
    "a", "an", "the", "in", "on", "at", "to", "for", "of", "and", "or",
    "with", "by", "from", "as", "is", "are", "was", "were", "be", "been",
    "this", "that", "these", "those", "it", "its", "into", "onto", "about",
    "please", "can", "you", "we", "i", "need", "want", "should", "would",
    "me", "us", "my", "our", "all", "do", "does", "did", "have", "has",
}

UNCLEAR_WORDS = {
    "fix", "bug", "issue", "problem", "broken", "update", "change",
    "test", "tests", "make", "build", "run", "help", "feature",
}


def normalize_request(request: str) -> str:
    """Normalize whitespace and lower-case text for marker comparison."""
    cleaned = re.sub(r"\s+", " ", request).strip().lower()
    return cleaned


def extract_keywords(text: str) -> List[str]:
    """Tokenize and filter stop words and punctuation."""
    tokens = re.findall(r"[a-zA-Z0-9_\-]+", text.lower())
    return [t for t in tokens if t not in STOP_WORDS and len(t) > 1]


def parse_explicit_issue(query: str) -> Optional[int]:
    """Check if query is #N, # N, issue N, issue #N, or N."""
    q = query.strip()
    m = re.match(r"^(?:(?:issue\s*#?\s*)|(?:#\s*))?(\d+)$", q, re.IGNORECASE)
    if m:
        return int(m.group(1))
    return None


def is_unclear_request(query: str) -> Tuple[bool, str]:
    """Determine if a free-text request is too vague or lacks actionable context."""
    norm = normalize_request(query)
    keywords = extract_keywords(norm)

    if not norm or len(norm) < 3:
        return True, "Request is empty or too short to describe an actionable task."

    if len(keywords) == 0:
        return True, f"Request contains only common stop words: '{query}'."

    if len(keywords) == 1 and keywords[0] in UNCLEAR_WORDS:
        return True, f"Request is too vague ('{keywords[0]}'). Please provide specific components, behaviors, or outcomes."

    if len(keywords) == 2 and all(k in UNCLEAR_WORDS for k in keywords):
        return True, f"Request '{query}' contains only generic keywords without identifying the target component."

    return False, ""


def query_open_issues() -> List[Dict[str, Any]]:
    """Fetch open issues from GitHub repository."""
    cmd = [
        "gh", "issue", "list",
        "--state", "open",
        "--limit", "100",
        "--json", "number,title,body,labels"
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return json.loads(res.stdout)
    except Exception as e:
        sys.stderr.write(f"Warning: Failed to query gh issues: {e}\n")
        return []


def search_matching_issues(query: str, issues: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Search issues using matching precedence:
    1. Exact hidden idempotency marker in issue body.
    2. Exact title match (case-insensitive).
    3. Keyword overlap score against title and body.
    """
    norm_query = normalize_request(query)
    marker = f"<!-- run-epic-request: {norm_query} -->"

    # 1. Exact hidden marker check (highest priority, guaranteed idempotency)
    for issue in issues:
        body = issue.get("body") or ""
        if marker in body:
            return {
                "status": "match_found",
                "match_type": "marker",
                "issue": issue["number"],
                "title": issue.get("title", ""),
                "score": 100.0,
            }

    # 2. Exact title match
    for issue in issues:
        title = normalize_request(issue.get("title") or "")
        # Strip common prefixes like feat: / docs: / fix:
        title_clean = re.sub(r"^(feat|fix|docs|refactor|chore|test)(?:\([^)]*\))?:\s*", "", title)
        query_clean = re.sub(r"^(feat|fix|docs|refactor|chore|test)(?:\([^)]*\))?:\s*", "", norm_query)
        if title == norm_query or title_clean == query_clean:
            return {
                "status": "match_found",
                "match_type": "exact_title",
                "issue": issue["number"],
                "title": issue.get("title", ""),
                "score": 95.0,
            }

    # 3. Keyword / token matching
    query_keywords = set(extract_keywords(query))
    if not query_keywords:
        return {"status": "no_match", "matches": []}

    scored_issues: List[Tuple[float, Dict[str, Any]]] = []

    for issue in issues:
        title_keywords = set(extract_keywords(issue.get("title") or ""))
        body_keywords = set(extract_keywords(issue.get("body") or ""))

        # Score calculation: title overlap carries 3x weight of body overlap
        title_overlap = query_keywords.intersection(title_keywords)
        body_overlap = query_keywords.intersection(body_keywords)

        if not title_overlap and len(body_overlap) < len(query_keywords):
            continue

        score = (len(title_overlap) * 3.0 + len(body_overlap) * 1.0) / (len(query_keywords) * 3.0)
        
        # If all query keywords are in the title, score is high
        if query_keywords.issubset(title_keywords):
            score = max(score, 0.90)

        if score >= 0.50:
            scored_issues.append((score, issue))

    # Sort descending by score
    scored_issues.sort(key=lambda x: x[0], reverse=True)

    if not scored_issues:
        return {"status": "no_match", "matches": []}

    best_score, best_issue = scored_issues[0]

    # If single clear match or top match is significantly better than second match
    if len(scored_issues) == 1:
        if best_score >= 0.65:
            return {
                "status": "match_found",
                "match_type": "keyword",
                "issue": best_issue["number"],
                "title": best_issue.get("title", ""),
                "score": round(best_score * 100, 1),
            }
        else:
            return {
                "status": "multiple_matches",
                "reason": f"Top candidate matched with weak confidence ({round(best_score * 100, 1)}%).",
                "matches": [
                    {"number": s[1]["number"], "title": s[1]["title"], "score": round(s[0] * 100, 1)}
                    for s in scored_issues
                ],
            }

    second_score, second_issue = scored_issues[1]

    # Clear winner threshold
    if best_score >= 0.80 and (best_score - second_score) >= 0.25:
        return {
            "status": "match_found",
            "match_type": "keyword",
            "issue": best_issue["number"],
            "title": best_issue.get("title", ""),
            "score": round(best_score * 100, 1),
        }

    # Ambiguous matches: several close candidates
    candidates = [
        {"number": s[1]["number"], "title": s[1]["title"], "score": round(s[0] * 100, 1)}
        for s in scored_issues[:5]
    ]
    return {
        "status": "multiple_matches",
        "reason": f"Multiple potential candidate issues match request '{query}'.",
        "matches": candidates,
    }


def generate_task_card(request: str, is_epic: bool = False) -> Tuple[str, str]:
    """Generate standardized title and body adhering to task card specification."""
    norm = normalize_request(request)
    marker = f"<!-- run-epic-request: {norm} -->"

    # Title formatting
    title_text = request.strip()
    if not re.match(r"^(feat|fix|docs|refactor|chore|test)(?:\([^)]*\))?:", title_text, re.IGNORECASE):
        title = f"feat: {title_text}"
    else:
        title = title_text

    body = f"""{marker}

## Goal
{request.strip()}

## Done when
- [ ] Core functionality for '{request.strip()}' is implemented and verified.
- [ ] Unit and integration test coverage added with 100% test suite passing.
- [ ] Passes runtime verification and adversarial audit review.
- [ ] Autonomous reviewer agent approval received.
- [ ] Required CI checks pass.

## Don't touch
- Core model pipeline configurations in models.yml.
- Existing intake/routing matrix rules.
- Zero paid API keys rule.
- No issue or PR comments rule.
- Never delete branches.
"""
    return title, body


def validate_task_card(body: str) -> bool:
    """Verify presence of mandatory sections per AGENTS.md Section 2 (#26)."""
    has_goal = bool(re.search(r"##\s+Goal\b", body, re.IGNORECASE))
    has_done_when = bool(re.search(r"##\s+Done\s+when\b", body, re.IGNORECASE))
    has_dont_touch = bool(re.search(r"##\s+Don['’]?t\s+touch\b", body, re.IGNORECASE))
    return has_goal and has_done_when and has_dont_touch


def create_issue(title: str, body: str, is_epic: bool = False, dry_run: bool = False) -> Dict[str, Any]:
    """Create a new GitHub issue with standard labels."""
    if not validate_task_card(body):
        return {
            "status": "error",
            "reason": "Task card failed validation: missing Goal, Done when, or Don't touch.",
        }

    labels = ["agent"]
    if is_epic:
        labels.append("epic")
    labels.append("enhancement")

    label_arg = ",".join(labels)

    if dry_run:
        return {
            "status": "issue_created",
            "issue": 9999,
            "title": title,
            "dry_run": True,
            "labels": labels,
        }

    cmd = [
        "gh", "issue", "create",
        "--title", title,
        "--body", body,
        "--label", label_arg
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        output = res.stdout.strip()
        # Parse issue number from URL e.g. https://github.com/.../issues/123
        m = re.search(r"/issues/(\d+)$", output)
        if m:
            issue_num = int(m.group(1))
            return {
                "status": "issue_created",
                "issue": issue_num,
                "title": title,
                "url": output,
                "labels": labels,
            }
        return {
            "status": "error",
            "reason": f"Could not parse issue number from gh output: {output}",
        }
    except subprocess.CalledProcessError as e:
        return {
            "status": "error",
            "reason": f"gh issue create failed: {e.stderr.strip()}",
        }


def resolve_epic_request(
    query: str,
    is_epic: bool = False,
    dry_run: bool = False,
    open_issues: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Main resolution logic for $run-epic inputs."""
    # 1. Check if input is an explicit issue number (#N, issue N, N)
    explicit_num = parse_explicit_issue(query)
    if explicit_num is not None:
        return {
            "status": "explicit_issue",
            "issue": explicit_num,
            "message": f"Using explicit issue #{explicit_num}.",
        }

    # 2. Check for unclear request
    unclear, reason = is_unclear_request(query)
    if unclear:
        return {
            "status": "unclear",
            "reason": reason,
            "query": query,
        }

    # 3. Search open issues
    issues = open_issues if open_issues is not None else query_open_issues()
    search_result = search_matching_issues(query, issues)

    if search_result["status"] == "match_found":
        return search_result

    if search_result["status"] == "multiple_matches":
        return search_result

    # 4. No match: create new issue with task card
    title, body = generate_task_card(query, is_epic=is_epic)
    create_result = create_issue(title, body, is_epic=is_epic, dry_run=dry_run)
    return create_result


def main():
    parser = argparse.ArgumentParser(description="Find or create an issue for $run-epic.")
    parser.add_argument("query", nargs="*", help="Issue number (#N) or free text request")
    parser.add_argument("--query", dest="query_flag", help="Alternative query input")
    parser.add_argument("--epic", action="store_true", help="Apply 'epic' label if creating a new issue")
    parser.add_argument("--dry-run", action="store_true", help="Simulate creation without calling GitHub")
    parser.add_argument("--json", action="store_true", help="Output JSON format")

    args = parser.parse_args()

    query_parts = args.query or []
    if args.query_flag:
        query_parts.append(args.query_flag)

    query = " ".join(query_parts).strip()
    if not query:
        err = {"status": "unclear", "reason": "No issue number or request text provided."}
        if args.json:
            print(json.dumps(err, indent=2))
        else:
            print("Error: No input provided. Usage: find_or_create_issue.py <#N | request text>")
        sys.exit(1)

    result = resolve_epic_request(query, is_epic=args.epic, dry_run=args.dry_run)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        status = result.get("status")
        if status in ("explicit_issue", "match_found"):
            print(f"Issue #{result['issue']}: {result.get('title', '')}")
        elif status == "issue_created":
            print(f"Created Issue #{result['issue']}: {result.get('title', '')}")
        elif status == "multiple_matches":
            print(f"Multiple matches found for '{query}':")
            for m in result.get("matches", []):
                print(f"  - #{m['number']} ({m.get('score', 0)}%): {m['title']}")
            print("Stopping: please specify the exact issue number.")
            sys.exit(2)
        elif status == "unclear":
            print(f"Unclear request '{query}': {result.get('reason')}")
            print("Stopping: please provide more detail or an issue number.")
            sys.exit(3)
        else:
            print(f"Error: {result.get('reason')}")
            sys.exit(1)


if __name__ == "__main__":
    main()
