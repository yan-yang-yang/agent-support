from __future__ import annotations

import asyncio
from pathlib import Path

from app.agent.runner import AgentRunner
from app.evals.runner import SupportEvalRunner, load_eval_cases
from app.tools.executor import ToolExecutor
from app.tools.repository import ToolCallRepository


class EvalBusinessGateway:
    async def get_active_rental(self, user_id: str):
        return {
            "id": "rental-eval",
            "order_id": "ORDER-EVAL",
            "station_id": "station-full",
            "started_at": "2026-11-17T08:30:00+08:00",
            "status": "active",
        }

    async def list_recent_orders(self, user_id: str, limit: int = 10):
        return [
            {
                "id": "ORDER-EVAL",
                "status": "active",
                "duration_minutes": 38,
                "total_amount": 9.0,
            }
        ][:limit]

    async def get_order_billing(self, order_id: str):
        return {
            "order_id": order_id,
            "items": [
                {"code": "base_fee", "label": "基础使用费", "amount": 6.0},
                {"code": "overtime_fee", "label": "超时费", "amount": 3.0},
            ],
            "total_amount": 9.0,
        }

    async def get_station_status(self, station_id: str):
        return {
            "id": station_id,
            "name": "评测满桩网点",
            "lat": 30.2741,
            "lng": 120.1551,
            "online": True,
            "available_umbrellas": 8,
            "available_docks": 0,
            "updated_at": "2026-11-17T09:00:00+08:00",
        }

    async def find_nearby_stations(
        self,
        *,
        lat: float,
        lng: float,
        purpose: str,
        radius_m: int = 3000,
    ):
        return [
            {
                "id": "station-nearby",
                "name": "评测可用网点",
                "lat": 30.2748,
                "lng": 120.1568,
                "online": True,
                "available_umbrellas": 6,
                "available_docks": 4,
                "distance_m": 181,
                "updated_at": "2026-11-17T09:00:00+08:00",
            }
        ]

    async def create_support_ticket(self, payload: dict[str, object]):
        return {
            "id": "TKT-EVAL",
            "category": payload["category"],
            "status": "open",
            "references": payload["references"],
            "summary": payload["summary"],
        }


def test_support_eval_dataset_passes_against_agent_graph(tmp_path) -> None:
    async def scenario():
        repository = ToolCallRepository(tmp_path / "evals.db")
        await repository.initialize()
        executor = ToolExecutor(gateway=EvalBusinessGateway(), repository=repository)
        agent_runner = AgentRunner(executor=executor)
        cases_path = Path(__file__).resolve().parents[2] / "evals" / "support_cases.json"
        cases = load_eval_cases(cases_path)
        return await SupportEvalRunner(agent_runner).run(cases)

    report = asyncio.run(scenario())

    assert report.total == 6
    assert report.passed == 6
    assert report.pass_rate == 1.0
    assert all(not result.failures for result in report.results)
