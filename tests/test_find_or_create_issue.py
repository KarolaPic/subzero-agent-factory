import unittest
from unittest.mock import patch, MagicMock

from scripts.find_or_create_issue import (
    parse_explicit_issue,
    normalize_request,
    extract_keywords,
    is_unclear_request,
    search_matching_issues,
    generate_task_card,
    validate_task_card,
    create_issue,
    resolve_epic_request,
)


class TestFindOrCreateIssue(unittest.TestCase):
    def test_parse_explicit_issue(self):
        self.assertEqual(parse_explicit_issue("#89"), 89)
        self.assertEqual(parse_explicit_issue("# 89"), 89)
        self.assertEqual(parse_explicit_issue("issue 89"), 89)
        self.assertEqual(parse_explicit_issue("issue #89"), 89)
        self.assertEqual(parse_explicit_issue("89"), 89)
        self.assertIsNone(parse_explicit_issue("add dark mode toggle"))
        self.assertIsNone(parse_explicit_issue("fix issue with login"))

    def test_normalize_request(self):
        self.assertEqual(
            normalize_request("  Add  a   Dark  Mode  Toggle!  "),
            "add a dark mode toggle!"
        )

    def test_extract_keywords(self):
        keywords = extract_keywords("Please add a dark mode toggle for the settings page")
        self.assertIn("dark", keywords)
        self.assertIn("mode", keywords)
        self.assertIn("toggle", keywords)
        self.assertIn("settings", keywords)
        self.assertIn("page", keywords)
        self.assertNotIn("the", keywords)
        self.assertNotIn("for", keywords)
        self.assertNotIn("a", keywords)

    def test_is_unclear_request(self):
        # Empty or too short
        unclear, reason = is_unclear_request("")
        self.assertTrue(unclear)
        self.assertIn("empty", reason.lower())

        unclear, reason = is_unclear_request("hi")
        self.assertTrue(unclear)

        # Stop words only
        unclear, reason = is_unclear_request("can you please do this for me")
        self.assertTrue(unclear)
        self.assertIn("stop words", reason.lower())

        # Single generic word
        unclear, reason = is_unclear_request("fix")
        self.assertTrue(unclear)
        self.assertIn("too vague", reason.lower())

        unclear, reason = is_unclear_request("update")
        self.assertTrue(unclear)

        # Two generic words without context
        unclear, reason = is_unclear_request("fix bug")
        self.assertTrue(unclear)
        self.assertIn("generic keywords", reason.lower())

        # Clear request
        unclear, reason = is_unclear_request("add dark mode toggle")
        self.assertFalse(unclear)
        self.assertEqual(reason, "")

        unclear, reason = is_unclear_request("export telemetry run logs to s3 bucket")
        self.assertFalse(unclear)

    def test_search_match_by_hidden_marker(self):
        request = "add dark mode toggle"
        marker = f"<!-- run-epic-request: {normalize_request(request)} -->"
        open_issues = [
            {
                "number": 101,
                "title": "feat: UI theme switcher",
                "body": f"Theme work.\n\n{marker}\n\n## Goal\nTheme toggle.",
                "labels": [{"name": "agent"}]
            },
            {
                "number": 102,
                "title": "Unrelated issue",
                "body": "Something else",
                "labels": []
            }
        ]

        result = search_matching_issues(request, open_issues)
        self.assertEqual(result["status"], "match_found")
        self.assertEqual(result["match_type"], "marker")
        self.assertEqual(result["issue"], 101)

    def test_search_match_by_exact_title(self):
        request = "add dark mode toggle"
        open_issues = [
            {
                "number": 105,
                "title": "feat: add dark mode toggle",
                "body": "Enable theme switching.",
                "labels": [{"name": "agent"}]
            }
        ]

        result = search_matching_issues(request, open_issues)
        self.assertEqual(result["status"], "match_found")
        self.assertEqual(result["match_type"], "exact_title")
        self.assertEqual(result["issue"], 105)

    def test_search_match_by_clear_keyword_overlap(self):
        request = "stripe payment webhook handler"
        open_issues = [
            {
                "number": 110,
                "title": "feat: stripe payment webhook handler",
                "body": "Handle invoice.paid and customer.subscription.updated",
                "labels": []
            },
            {
                "number": 111,
                "title": "fix: update documentation navbar",
                "body": "Fix typo in header link",
                "labels": []
            }
        ]

        result = search_matching_issues(request, open_issues)
        self.assertEqual(result["status"], "match_found")
        self.assertEqual(result["issue"], 110)

    def test_search_multiple_ambiguous_matches(self):
        request = "database connection pool"
        open_issues = [
            {
                "number": 120,
                "title": "chore: database connection pool timeouts",
                "body": "Pool tuning",
                "labels": []
            },
            {
                "number": 121,
                "title": "fix: database connection pool leak on reconnect",
                "body": "Leak resolution",
                "labels": []
            }
        ]

        result = search_matching_issues(request, open_issues)
        self.assertEqual(result["status"], "multiple_matches")
        self.assertIn("matches", result)
        self.assertGreaterEqual(len(result["matches"]), 2)

    def test_task_card_generation_and_validation(self):
        request = "integrate sentry error telemetry"
        title, body = generate_task_card(request)

        self.assertIn("integrate sentry error telemetry", title.lower())
        self.assertTrue(validate_task_card(body))
        self.assertIn("## Goal", body)
        self.assertIn("## Done when", body)
        self.assertIn("## Don't touch", body)
        self.assertIn("<!-- run-epic-request: integrate sentry error telemetry -->", body)

    def test_task_card_validation_fails_on_missing_section(self):
        invalid_body_1 = "## Goal\nDo something\n\n## Done when\n- [ ] done"
        self.assertFalse(validate_task_card(invalid_body_1))

        invalid_body_2 = "## Done when\n- [ ] done\n\n## Don't touch\nNone"
        self.assertFalse(validate_task_card(invalid_body_2))

    def test_resolve_explicit_issue(self):
        res = resolve_epic_request("#89")
        self.assertEqual(res["status"], "explicit_issue")
        self.assertEqual(res["issue"], 89)

        res2 = resolve_epic_request("issue 43")
        self.assertEqual(res2["status"], "explicit_issue")
        self.assertEqual(res2["issue"], 43)

    def test_resolve_unclear_request(self):
        res = resolve_epic_request("fix bug")
        self.assertEqual(res["status"], "unclear")
        self.assertIn("reason", res)

    def test_resolve_match_found(self):
        open_issues = [
            {
                "number": 43,
                "title": "feat: $run-epic skill - run the whole epic loop from one command",
                "body": "Goal: run-epic skill",
                "labels": []
            }
        ]
        res = resolve_epic_request(
            "$run-epic skill run whole epic loop",
            open_issues=open_issues
        )
        self.assertEqual(res["status"], "match_found")
        self.assertEqual(res["issue"], 43)

    def test_resolve_no_match_creates_issue_dry_run(self):
        open_issues = [
            {"number": 1, "title": "Other", "body": "...", "labels": []}
        ]
        res = resolve_epic_request(
            "add customer billing receipt email notification",
            dry_run=True,
            open_issues=open_issues
        )
        self.assertEqual(res["status"], "issue_created")
        self.assertEqual(res["issue"], 9999)
        self.assertIn("billing receipt", res["title"])

    def test_idempotent_duplicate_prevention(self):
        """Simulate creating an issue and re-running with the exact same request."""
        request = "add webhook signature verification"
        title, body = generate_task_card(request)

        # Simulated state where issue has been created in GitHub
        mock_github_state = [
            {
                "number": 200,
                "title": title,
                "body": body,
                "labels": [{"name": "agent"}]
            }
        ]

        # First query finds it via marker
        res = resolve_epic_request(request, open_issues=mock_github_state)
        self.assertEqual(res["status"], "match_found")
        self.assertEqual(res["issue"], 200)
        self.assertEqual(res["match_type"], "marker")


if __name__ == "__main__":
    unittest.main()
