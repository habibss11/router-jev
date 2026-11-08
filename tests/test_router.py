import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))
from router import MODELS, CALL_LIMIT, PRIMARY_MODEL, BACKUP_MODEL, Router, RouterError, validate
from credentials import key_file, load_key, save_key, credential_status


def example():
    return json.loads((ROOT / "examples" / "architecture-code-research.json").read_text())


def response(payload, key):
    return {"model": payload["model"], "answers": {
        task: {"type": "choice", "choice": next(iter(question["criteria"])),
               "probabilities": {k: 0.9 if i == 0 else 0.1 / (len(question["criteria"]) - 1)
                                 for i, k in enumerate(question["criteria"])}}
        for task, question in payload["questions"].items()},
        "usage": {"input_tokens": 2000, "output_tokens": 40, "cost": 0.00012}}


class RoutingTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {"OPENROUTER_API_KEY": "synthetic-test-value"})
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_all_five_models_preserved_on_wire(self):
        for model in MODELS:
            raw = example()
            raw["decision_model"] = model
            plan = Router(response).route(raw)
            self.assertEqual(plan["reported_decision_model"], model)
            self.assertEqual(plan["status"], "planned")
            self.assertFalse(plan["executed"])

    def test_user_selected_primary_and_backup_are_defaults(self):
        raw = example()
        raw.pop("decision_model", None)
        value = validate(raw)
        self.assertEqual(value["decision_model"], PRIMARY_MODEL)
        self.assertEqual(value["fallback_decision_model"], BACKUP_MODEL)

    def test_dependency_waves_and_source(self):
        plan = Router(response).route(example())
        self.assertEqual(plan["execution_waves"], [["read"], ["design"], ["code"], ["review"]])
        self.assertTrue(all(t["decision"]["source"] == "decision_model" for t in plan["assignments"]))
        self.assertEqual(plan["assignments"][0]["model"], "gpt-6-luna")

    def test_hard_candidates_reject_unknown_model_answer(self):
        def wrong(payload, key):
            data = response(payload, key)
            data["answers"]["read"]["choice"] = "invented"
            return data
        plan = Router(wrong).route(example())
        task = plan["assignments"][0]
        self.assertEqual(task["profile_id"], "coder")
        self.assertEqual(task["decision"]["reason"], "invalid_choice")

    def test_uncertain_selects_explicit_fallback(self):
        def uncertain(payload, key):
            data = response(payload, key)
            data["answers"]["read"]["probabilities"] = {"reader": .51, "coder": .49}
            return data
        task = Router(uncertain).route(example())["assignments"][0]
        self.assertEqual(task["profile_id"], "coder")
        self.assertEqual(task["decision"]["reason"], "uncertain_decision")

    def test_malformed_probabilities_cannot_select_agent(self):
        for probabilities in ({"reader": float("nan"), "coder": 0.1},
                              {"reader": True, "coder": 0.1},
                              {"reader": .9, "coder": .9},
                              {"reader": .9}, {"reader": .1, "coder": .9}):
            def malformed(payload, key):
                data = response(payload, key)
                data["answers"]["read"]["probabilities"] = probabilities
                return data
            task = Router(malformed).route(example())["assignments"][0]
            self.assertEqual(task["decision"]["source"], "fallback")

    def test_graph_validation_before_api(self):
        for corruption in ("cycle", "unknown", "duplicate"):
            raw = example()
            if corruption == "cycle":
                raw["tasks"][0]["depends_on"] = ["review"]
            elif corruption == "unknown":
                raw["tasks"][0]["depends_on"] = ["missing"]
            else:
                raw["tasks"][1]["id"] = "read"
            with self.assertRaises(RouterError):
                Router(lambda *_: self.fail("Must not call API")).route(raw)

    def test_bad_fallback_rejected(self):
        raw = example()
        raw["tasks"][0]["fallback_profile"] = "architect"
        with self.assertRaises(RouterError):
            validate(raw)

    def test_fixed_tasks_do_not_call_api(self):
        raw = example()
        for task in raw["tasks"]:
            task["allowed_profiles"] = [task["fallback_profile"]]
        plan = Router(lambda *_: self.fail("Must not call API")).route(raw)
        self.assertFalse(plan["api_called"])
        self.assertTrue(all(t["decision"]["source"] == "fixed_by_caller" for t in plan["assignments"]))

    def test_missing_key_is_explicit_and_not_a_jev_result(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {
                "OPENROUTER_API_KEY": "", "CODEX_DECISION_ROUTER_KEY_FILE": str(Path(tmp) / "key.json")}):
            plan = Router(lambda *_: self.fail("Must not call API")).route(example())
        self.assertEqual(plan["status"], "fallback_plan")
        self.assertEqual(plan["api_error"], "missing_openrouter_api_key")
        self.assertFalse(plan["api_called"])

    def test_cache_no_new_billing_and_model_switch_misses(self):
        router = Router(response)
        raw = example()
        first = router.route(raw)
        cached = router.route(raw)
        self.assertTrue(cached["cache_hit"])
        self.assertEqual(cached["api_cost_usd_this_call"], 0)
        self.assertEqual(first["api_cost_usd_this_call"], .00012)
        raw["decision_model"] = "typesafe/jev-1.14"
        self.assertFalse(router.route(raw)["cache_hit"])
        self.assertEqual(router.calls, 2)

    def test_changed_context_invalidates_cache(self):
        router = Router(response)
        raw = example()
        router.route(raw)
        raw["tasks"][0]["context"] = "A previously missing API is now available."
        self.assertFalse(router.route(raw)["cache_hit"])

    def test_network_error_tries_only_two_models_and_cost_remains_unknown(self):
        def fail(*_):
            raise RouterError("openrouter_network_or_timeout")
        router = Router(fail)
        plan = router.route(example())
        self.assertEqual(router.calls, 2)
        self.assertIsNone(plan["api_cost_usd_this_call"])
        self.assertEqual(plan["status"], "fallback_plan")

    def test_process_call_cap(self):
        router = Router(response)
        for i in range(CALL_LIMIT):
            raw = example()
            raw["objective"] += str(i)
            router.route(raw)
        plan = router.route(example())
        self.assertEqual(router.calls, CALL_LIMIT)
        self.assertFalse(plan["api_called"])
        self.assertEqual(plan["api_error"], "process_call_limit_reached")

    def test_preview_no_network_and_bounded_payload(self):
        router = Router(lambda *_: self.fail("Must not call API"))
        view = router.preview(example())
        self.assertFalse(view["api_called"])
        self.assertEqual(len(view["request"]["questions"]), 4)
        self.assertLess(view["request_bytes"], 48000)

    def test_parallelism_cap(self):
        raw = example()
        for task in raw["tasks"]:
            task["depends_on"] = []
        self.assertEqual(Router(response).route(raw)["execution_waves"],
                         [["read", "design"], ["code", "review"]])

    def test_drex_outage_uses_jev_and_reports_unknown_primary_cost(self):
        calls = []
        def transport(payload, key):
            calls.append(payload["model"])
            if payload["model"] == PRIMARY_MODEL:
                raise RouterError("openrouter_http_503")
            return response(payload, key)
        result = Router(transport).route(example())
        self.assertEqual(calls, [PRIMARY_MODEL, BACKUP_MODEL])
        self.assertEqual(result["status"], "planned")
        self.assertTrue(result["backup_used"])
        self.assertIsNone(result["api_error"])
        self.assertIsNone(result["api_cost_usd_this_call"])
        self.assertTrue(all(a["decision"]["decision_model"] == BACKUP_MODEL for a in result["assignments"]))

    def test_jev_receives_only_uncertain_questions(self):
        calls = []
        def transport(payload, key):
            calls.append(copy.deepcopy(payload))
            data = response(payload, key)
            if payload["model"] == PRIMARY_MODEL:
                data["answers"]["read"]["probabilities"] = {"reader": .51, "coder": .49}
            return data
        result = Router(transport).route(example())
        self.assertEqual(set(calls[1]["questions"]), {"read"})
        self.assertEqual(result["assignments"][0]["decision"]["decision_model"], BACKUP_MODEL)
        self.assertEqual(result["assignments"][1]["decision"]["decision_model"], PRIMARY_MODEL)
        self.assertAlmostEqual(result["api_cost_usd_this_call"], .00024)
        self.assertEqual(result["original_api_usage"]["input_tokens"], 4000)

    def test_shared_auth_or_credit_error_does_not_bill_second_attempt(self):
        for code in (401, 402, 403):
            def fail(*_):
                raise RouterError(f"openrouter_http_{code}")
            router = Router(fail)
            result = router.route(example())
            self.assertEqual(router.calls, 1)
            self.assertFalse(result["backup_used"])
            self.assertEqual(result["status"], "fallback_plan")

    def test_explicit_null_disables_reserve(self):
        raw = example()
        raw["fallback_decision_model"] = None
        def fail(*_):
            raise RouterError("openrouter_http_503")
        router = Router(fail)
        result = router.route(raw)
        self.assertEqual(router.calls, 1)
        self.assertEqual(result["status"], "fallback_plan")

    def test_malformed_primary_response_gets_one_backup_attempt(self):
        def transport(payload, key):
            return [] if payload["model"] == PRIMARY_MODEL else response(payload, key)
        result = Router(transport).route(example())
        self.assertEqual(result["status"], "planned")
        self.assertEqual(result["attempts"][0]["error"], "invalid_decisions_response")

    def test_backup_is_not_called_for_fixed_or_confident_tasks(self):
        router = Router(response)
        result = router.route(example())
        self.assertEqual(router.calls, 1)
        self.assertFalse(result["backup_used"])

    def test_successful_backup_is_cached(self):
        def transport(payload, key):
            if payload["model"] == PRIMARY_MODEL:
                raise RouterError("openrouter_http_503")
            return response(payload, key)
        router = Router(transport)
        router.route(example())
        cached = router.route(example())
        self.assertTrue(cached["cache_hit"])
        self.assertEqual(cached["api_cost_usd_this_call"], 0)
        self.assertEqual(router.calls, 2)

    def test_stdio_initialize_discovery_preview_and_no_secret_leak(self):
        messages = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-11-25"}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "router_status"}},
            {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "preview_routing", "arguments": example()}},
            {"jsonrpc": "2.0", "id": 5, "method": "tools/call", "params": {"name": "route_tasks", "arguments": {"objective": "bad"}}},
        ]
        proc = subprocess.run([sys.executable, str(ROOT / "server" / "main.py")],
            input="".join(json.dumps(x) + "\n" for x in messages),
            capture_output=True, text=True, timeout=5)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn("synthetic-test-value", proc.stdout + proc.stderr)
        results = [json.loads(line) for line in proc.stdout.splitlines()]
        self.assertEqual(len(results), 5)
        self.assertEqual(len(results[1]["result"]["tools"]), 3)
        self.assertFalse(results[3]["result"]["structuredContent"]["api_called"])
        self.assertTrue(results[4]["result"]["isError"])


class CredentialTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "settings" / "credentials.json"
        self.env = patch.dict(os.environ, {"OPENROUTER_API_KEY": "", "CODEX_DECISION_ROUTER_KEY_FILE": str(self.path)})
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_blank_template_preserves_existing_key(self):
        save_key(None, initialize_only=True)
        self.assertEqual(load_key()[2], "missing_openrouter_api_key")
        save_key("sk-or-synthetic-unit-test")
        save_key(None, initialize_only=True)
        self.assertEqual(load_key()[0], "sk-or-synthetic-unit-test")
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)

    def test_file_key_is_loaded_on_each_call_without_restart(self):
        save_key(None, initialize_only=True)
        self.assertFalse(credential_status()["api_key_configured"])
        save_key("sk-or-synthetic-unit-test")
        self.assertTrue(credential_status()["api_key_configured"])
        self.assertNotIn("sk-or-synthetic-unit-test", json.dumps(credential_status()))

    def test_environment_takes_precedence(self):
        save_key("sk-or-synthetic-unit-test")
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "sk-or-synthetic-environment"}):
            self.assertEqual(load_key()[:2], ("sk-or-synthetic-environment", "environment"))

    def test_invalid_credential_never_echoes_file_contents(self):
        self.path.parent.mkdir()
        self.path.write_text('{"OPENROUTER_API_KEY": "secret with newline\\n"}')
        status = credential_status()
        self.assertFalse(status["api_key_configured"])
        self.assertEqual(status["credential_error"], "invalid_credential_file")
        self.assertNotIn("secret", json.dumps(status))

    def test_nonterminal_setup_refuses_to_capture_secret(self):
        proc = subprocess.run([sys.executable, str(ROOT / "scripts/setup_key.py")],
                              input="sk-or-do-not-record", text=True, capture_output=True, timeout=5)
        self.assertEqual(proc.returncode, 1)
        self.assertFalse(self.path.exists())
        self.assertNotIn("sk-or-do-not-record", proc.stdout + proc.stderr)


if __name__ == "__main__":
    unittest.main()
