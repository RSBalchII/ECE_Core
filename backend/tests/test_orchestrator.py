import asyncio
import sys
from pathlib import Path

# Ensure ece-core/src is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from agents.orchestrator.orchestrator import CrossTeamOrchestrator


def test_orchestrator_run_sync():
    coro = CrossTeamOrchestrator(teams=3, config={}).run("Please design a small module")
    res = asyncio.get_event_loop().run_until_complete(coro)
    assert 'aggregated_plan' in res
    assert isinstance(res['aggregated_plan'], list)
