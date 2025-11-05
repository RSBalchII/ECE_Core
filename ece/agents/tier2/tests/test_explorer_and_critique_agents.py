"""
Tests for the ExplorerAgent and CritiqueAgent.

This module tests the agents used in the Exploratory Problem-Solving workflow.
"""

import sys
import os
import unittest

# Add the project root to the Python path
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
)

from ece.agents.tier2.explorer_agent import ExplorerAgent
from ece.agents.tier2.critique_agent import CritiqueAgent


class TestExplorerAgent(unittest.TestCase):
    """Test cases for the ExplorerAgent."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.explorer_agent = ExplorerAgent()

    def test_propose_solution(self):
        """Test that the ExplorerAgent can propose a solution."""
        problem_poml = "<poml><problem>Solve for x in 2x + 5 = 15</problem></poml>"

        # Get a solution proposal
        solution_poml = self.explorer_agent.propose_solution(problem_poml)

        # Verify that we got a response
        self.assertIsInstance(solution_poml, str)
        self.assertGreater(len(solution_poml), 0)

        # Verify that the response contains expected elements
        self.assertIn("<poml>", solution_poml)
        self.assertIn("<solution", solution_poml)
        self.assertIn("<steps>", solution_poml)
        self.assertIn("<code>", solution_poml)


class TestCritiqueAgent(unittest.TestCase):
    """Test cases for the CritiqueAgent."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.critique_agent = CritiqueAgent()

    def test_score_result(self):
        """Test that the CritiqueAgent can score a result."""
        # Create a sample solution POML
        solution_poml = """<poml>
    <solution>
        <steps>
            <step>Subtract 5 from both sides: 2x = 10</step>
            <step>Divide both sides by 2: x = 5</step>
        </steps>
        <code>
print("Solving 2x + 5 = 15")
x = (15 - 5) / 2
print(f"x = {x}")
        </code>
    </solution>
</poml>"""

        # Create a result POML that includes the solution
        result_poml = f"""<poml>
    <solution_evaluation>
        <solution>
            {solution_poml}
        </solution>
        <execution_result>
            <success>True</success>
            <output>x = 5.0</output>
            <errors>None</errors>
        </execution_result>
    </solution_evaluation>
</poml>"""

        # Get a critique
        critique_poml = self.critique_agent.score_result(result_poml)

        # Verify that we got a response
        self.assertIsInstance(critique_poml, str)
        self.assertGreater(len(critique_poml), 0)

        # Verify that the response contains expected elements
        self.assertIn("<poml>", critique_poml)
        self.assertIn("<critique>", critique_poml)
        self.assertIn("<score>", critique_poml)
        self.assertIn("<rationale>", critique_poml)


if __name__ == "__main__":
    unittest.main()
