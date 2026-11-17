from __future__ import annotations

import argparse
import asyncio
import os
import tempfile
from pathlib import Path

from ..agent.runner import AgentRunner
from ..business import HttpUmbrellaBusinessGateway
from ..tools.executor import ToolExecutor
from ..tools.repository import ToolCallRepository
from .runner import SupportEvalRunner, load_eval_cases


def parse_args() -> argparse.Namespace:
    default_cases = Path(__file__).resolve().parents[2] / "evals" / "support_cases.json"
    parser = argparse.ArgumentParser(description="Run public umbrella support Agent evaluations")
    parser.add_argument("--cases", type=Path, default=default_cases)
    parser.add_argument(
        "--business-base-url",
        default=os.getenv("APP_BUSINESS_BASE_URL", "http://127.0.0.1:8010"),
    )
    parser.add_argument(
        "--internal-token",
        default=os.getenv("APP_BUSINESS_INTERNAL_TOKEN", "dev-internal-token"),
    )
    parser.add_argument("--json", action="store_true", dest="as_json")
    return parser.parse_args()


async def run() -> int:
    args = parse_args()
    cases = load_eval_cases(args.cases)
    gateway = HttpUmbrellaBusinessGateway(
        base_url=args.business_base_url,
        internal_token=args.internal_token,
        timeout_seconds=3,
    )
    try:
        with tempfile.TemporaryDirectory(prefix="agent-support-evals-") as temporary_directory:
            repository = ToolCallRepository(Path(temporary_directory) / "evals.db")
            await repository.initialize()
            executor = ToolExecutor(gateway=gateway, repository=repository)
            report = await SupportEvalRunner(AgentRunner(executor=executor)).run(cases)
    finally:
        await gateway.close()

    if args.as_json:
        print(report.model_dump_json(indent=2))
    else:
        for result in report.results:
            marker = "PASS" if result.passed else "FAIL"
            print(f"[{marker}] {result.case_id}: {result.actual_scenario}")
            for failure in result.failures:
                print(f"  - {failure}")
        print(f"\n{report.passed}/{report.total} passed ({report.pass_rate:.0%})")
    return 0 if report.passed == report.total else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
