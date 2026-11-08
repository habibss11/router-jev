import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import run_codex_task as runner  # noqa: E402


class CodexRunnerTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.task = self.root / "task.md"
        self.task.write_text("Add a test.", encoding="utf-8")
        self.report = self.root / "out" / "report.md"

    def args(self, **changes):
        values = {"--model": "gpt-6.1-terra", "--effort": "medium", "--sandbox": "read-only",
                  "--task-file": str(self.task), "--cwd": str(self.root), "--report": str(self.report)}
        values.update(changes)
        return [item for pair in values.items() for item in pair]

    def run_main(self, argv):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout), mock.patch.object(
                runner.shutil, "which", return_value="/bin/codex"):
            code = runner.main(argv)
        return code, json.loads(stdout.getvalue())

    def write_report(self, *args, **kwargs):
        self.report.write_text("done", encoding="utf-8")
        return subprocess.CompletedProcess(args, 0)

    def test_command_passes_model_and_effort_explicitly(self):
        command = runner.build_command("codex", "gpt-6.1-sol", "high", "read-only", "/w", "/r")
        self.assertEqual(command[:3], ["codex", "exec", "-m"])
        self.assertIn("gpt-6.1-sol", command)
        self.assertIn('model_reasoning_effort="high"', command)
        self.assertEqual(command[-1], "-")

    def test_rejects_full_access_ultra_and_unknown_model(self):
        for change in ({"--sandbox": "danger-full-access"}, {"--effort": "ultra"}, {"--model": "gpt-x"}):
            with self.subTest(change), self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
                runner.parse_args(self.args(**change))

    def test_success_sends_guardrails_and_task(self):
        with mock.patch.object(runner.subprocess, "run", side_effect=self.write_report) as run:
            code, result = self.run_main(self.args())
        self.assertEqual((code, result["status"]), (0, "completed"))
        prompt = run.call_args.kwargs["input"]
        self.assertIn("Do not commit", prompt)
        self.assertTrue(prompt.endswith("Add a test."))

    def test_empty_report_is_failure(self):
        completed = subprocess.CompletedProcess([], 0)
        with mock.patch.object(runner.subprocess, "run", return_value=completed):
            code, result = self.run_main(self.args())
        self.assertEqual((code, result["error"]), (1, "empty_report"))

    def test_stale_report_is_not_treated_as_result(self):
        self.report.parent.mkdir(parents=True)
        self.report.write_text("old", encoding="utf-8")
        failed = subprocess.CompletedProcess([], 3)
        with mock.patch.object(runner.subprocess, "run", return_value=failed):
            code, result = self.run_main(self.args())
        self.assertEqual((code, result["status"]), (3, "failed"))
        self.assertFalse(self.report.exists())

    def test_timeout_is_reported(self):
        timeout = subprocess.TimeoutExpired("codex", 5)
        with mock.patch.object(runner.subprocess, "run", side_effect=timeout):
            code, result = self.run_main(self.args())
        self.assertEqual((code, result["status"]), (124, "timeout"))

    def test_missing_task_file_does_not_start_codex(self):
        with mock.patch.object(runner.subprocess, "run") as run:
            code, result = self.run_main(self.args(**{"--task-file": str(self.root / "none.md")}))
        run.assert_not_called()
        self.assertEqual((code, result["error"]), (1, "task_file_unreadable"))


if __name__ == "__main__":
    unittest.main()
