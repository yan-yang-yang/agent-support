from __future__ import annotations

import json
from pathlib import Path

from pydantic import TypeAdapter

from ..agent.runner import AgentRunner
from .types import EvalCase, EvalCaseResult, EvalReport


def load_eval_cases(path: Path) -> list[EvalCase]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return TypeAdapter(list[EvalCase]).validate_python(payload)


class SupportEvalRunner:
    def __init__(self, agent_runner: AgentRunner) -> None:
        self._agent_runner = agent_runner

    async def run(self, cases: list[EvalCase]) -> EvalReport:
        results: list[EvalCaseResult] = []
        for case in cases:
            result = await self._agent_runner.run_turn(
                user_id=case.user_id,
                conversation_id=f"eval-conversation-{case.id}",
                request_id=f"eval-request-{case.id}",
                content=case.input,
            )
            failures: list[str] = []
            if result.scenario != case.expected_scenario:
                failures.append(
                    f"scenario expected {case.expected_scenario}, got {result.scenario}"
                )
            if result.safe_fallback != case.expected_safe_fallback:
                failures.append(
                    f"safe_fallback expected {case.expected_safe_fallback}, got {result.safe_fallback}"
                )
            executed = set(result.executed_tools)
            for tool in case.required_tools:
                if tool not in executed:
                    failures.append(f"required tool missing: {tool}")
            for tool in case.forbidden_tools:
                if tool in executed:
                    failures.append(f"forbidden tool executed: {tool}")
            for text in case.response_contains:
                if text not in result.verified_response:
                    failures.append(f"response missing: {text}")
            results.append(
                EvalCaseResult(
                    case_id=case.id,
                    passed=not failures,
                    actual_scenario=result.scenario,
                    executed_tools=list(result.executed_tools),
                    failures=failures,
                )
            )
        return EvalReport(results=results)
