from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import install_claude_code as installer  # noqa: E402


class InstallClaudeCodeTests(unittest.TestCase):
    def test_skill_is_rendered_without_placeholders_or_personal_paths(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "route-subagents"
            installer.install_skill(target, "/usr/bin/python3")
            skill = (target / "SKILL.md").read_text(encoding="utf-8")
            self.assertTrue((target / "profiles.json").is_file())
        self.assertNotIn("{{", skill)
        self.assertIn(str(installer.ROOT / "server" / "main.py"), skill)
        self.assertIn("/usr/bin/python3", skill)
        self.assertNotIn("/Users/habib", skill.replace(str(installer.ROOT), ""))

    def test_existing_skill_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "route-subagents"
            target.mkdir()
            marker = target / "SKILL.md"
            marker.write_text("mine", encoding="utf-8")
            code = installer.main(["--claude", "/bin/true", "--skills-dir", temporary])
            self.assertEqual(code, 1)
            self.assertEqual(marker.read_text(encoding="utf-8"), "mine")


if __name__ == "__main__":
    unittest.main()
