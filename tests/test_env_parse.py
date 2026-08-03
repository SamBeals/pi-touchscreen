from __future__ import annotations

import unittest

from app.config import parse_env_file


class TestEnvParse(unittest.TestCase):
    def test_comments_blanks_whitespace_quotes(self):
        text = """
# comment line

MACHINE_ID=machine_002
CLOUD_BASE = "https://example.run.app"
TOKEN='CHANGE_ME'
EMPTY_SKIP=

# KEY without equals ignored
JUSTTEXT
SPACED_KEY = value with spaces
"""
        parsed = parse_env_file(text)
        self.assertEqual(parsed["MACHINE_ID"], "machine_002")
        self.assertEqual(parsed["CLOUD_BASE"], "https://example.run.app")
        self.assertEqual(parsed["TOKEN"], "CHANGE_ME")
        self.assertEqual(parsed["SPACED_KEY"], "value with spaces")
        self.assertNotIn("JUSTTEXT", parsed)

    def test_does_not_execute_shell(self):
        text = 'EVIL=$(rm -rf /)\nSAFE=ok\n'
        parsed = parse_env_file(text)
        self.assertEqual(parsed["EVIL"], "$(rm -rf /)")
        self.assertEqual(parsed["SAFE"], "ok")

    def test_no_variable_expansion(self):
        text = "A=one\nB=$A\n"
        parsed = parse_env_file(text)
        self.assertEqual(parsed["B"], "$A")


if __name__ == "__main__":
    unittest.main()
