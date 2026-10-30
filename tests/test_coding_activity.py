"""Offline checks for the public, aggregate-only coding activity generator."""
import collections
from datetime import datetime, timezone
import unittest
from xml.etree import ElementTree

from scripts.coding_activity import language_of, make_svg, since_twelve_months, collect


class FixtureAPI:
    def pages(self, path, params=None, **kwargs):
        if path == "/user/repos":
            return iter([
                {"owner": {"login": "haikalthrq"}, "name": "project",
                 "full_name": "haikalthrq/project", "size": 120, "fork": False},
            ])
        if path == "/repos/haikalthrq/project/branches":
            return iter([{"name": "main"}, {"name": "development"}])
        if path == "/repos/haikalthrq/project/commits":
            return iter([{"sha": "sharedsha"}, {"sha": "branchsha"}] if
                        params.get("sha") == "main" else [{"sha": "sharedsha"}])
        raise AssertionError("Unexpected page path: " + path)

    def get(self, path, params=None, **kwargs):
        if path.endswith("/commits/sharedsha"):
            return {"files": [
                {"filename": "app/server.py"},
                {"filename": "notebooks/analysis.ipynb"},
                {"filename": "README.md"},
                {"filename": "dist/bundle.js"},
            ]}
        if path.endswith("/commits/branchsha"):
            return {"files": [{"filename": "ui/client.tsx"}]}
        raise AssertionError("Unexpected get path: " + path)


class ActivityTests(unittest.TestCase):
    def test_language_mapping(self):
        self.assertEqual(language_of("notebooks/model.ipynb"), "Python (notebooks)")
        self.assertEqual(language_of("src/main.py"), "Python")
        self.assertEqual(language_of("src/app.tsx"), "TypeScript")
        self.assertEqual(language_of("src/main.luau"), "Lua / Luau")
        self.assertIsNone(language_of("node_modules/lib/index.js"))
        self.assertIsNone(language_of("README.md"))
        self.assertIsNone(language_of("dist/generated.js"))

    def test_twelve_calendar_months(self):
        now = datetime(2026, 10, 31, 13, 2, tzinfo=timezone.utc)
        self.assertEqual(since_twelve_months(now).date().isoformat(), "2025-10-31")
        leap = datetime(2024, 2, 29, tzinfo=timezone.utc)
        self.assertEqual(since_twelve_months(leap).date().isoformat(), "2023-02-28")

    def test_dedupe_branches_and_ignore_docs(self):
        counts, commits, repos = collect(
            FixtureAPI(), datetime(2026, 10, 31, tzinfo=timezone.utc))
        self.assertEqual(commits, 2)
        self.assertEqual(repos, 1)
        self.assertEqual(counts, collections.Counter({
            "Python": 1, "Python (notebooks)": 1, "TypeScript": 1,
        }))

    def test_aggregate_svg_privacy_and_valid_xml(self):
        svg = make_svg(
            collections.Counter({"Python": 3, "Python (notebooks)": 1}),
            datetime(2026, 10, 31, tzinfo=timezone.utc), 2)
        ElementTree.fromstring(svg)
        self.assertIn("75.0%", svg)
        self.assertIn("Python (notebooks)", svg)
        self.assertNotIn("haikalthrq/project", svg)
        self.assertNotIn("sharedsha", svg)

if __name__ == "__main__":
    unittest.main()
