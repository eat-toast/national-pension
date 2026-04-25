from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.export.combined_html_writer import export_combined_html


class CombinedHtmlWriterTest(unittest.TestCase):
    def test_exports_tabbed_single_html(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "combined.html"
            export_combined_html(
                output,
                dashboard_html="<html><body>dashboard</body></html>",
                sector_trends_html="<html><body>sector</body></html>",
                strategy_html="<html><body>strategy</body></html>",
            )

            html = output.read_text(encoding="utf-8")
            self.assertIn("포트폴리오", html)
            self.assertIn("섹터 변화", html)
            self.assertIn("전략", html)
            self.assertIn("srcdoc", html)
            self.assertIn("dashboard", html)
            self.assertIn("sector", html)
            self.assertIn("strategy", html)


if __name__ == "__main__":
    unittest.main()
