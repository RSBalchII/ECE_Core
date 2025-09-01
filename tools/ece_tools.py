# tools/ece_tools.py
# This file contains the implementation of the core tools for the
# External Context Engine (ECE), used by the OrchestraAgent.

from youtu_agent.tool import Tool
from pydantic import BaseModel, Field
import json

# === Input Schemas for Tools ===
# Using Pydantic models to define clear, validated input schemas for each tool.

class DistillInput(BaseModel):
    """Input schema for the DistillerAgent tool."""
    raw_text: str = Field(description="The raw, unstructured text from a session log or document to be distilled.")

class ArchiveInput(BaseModel):
    """Input schema for the ArchivistAgent tool."""
    structured_summary: str = Field(description="A structured summary (ideally in JSON format) containing insights and relationships to be saved to the knowledge graph.")

# === Tool Implementations ===

class DistillerAgent(Tool):
    """
    A tool that embodies the DistillerAgent. It takes a large block of raw text
    and uses an LLM to distill it into a structured summary of high-coherency
    insights and key conceptual relationships.
    """
    def __init__(self, llm):
        super().__init__()
        self.llm = llm  # The tool is initialized with an LLM instance by the framework
        self.name = "DistillerAgent"
        self.description = (
            "Analyzes raw text (e.g., session logs) to identify and summarize key insights, "
            "decisions, and conceptual relationships. Use this to process unstructured data."
        )
        self.input_model = DistillInput

    def _run(self, tool_input: DistillInput) -> str:
        """
        The core logic for the DistillerAgent tool.
        This function will be executed when the OrchestraAgent calls this tool.
        """
        print(f"🕵️  DistillerAgent activated. Analyzing text...")
        
        # We instruct the LLM to return a JSON string for easy parsing downstream.
        prompt = f"""
        You are an expert data distiller. Analyze the following text and extract the most
        critical insights, key decisions, and conceptual relationships.
        Present the output as a structured JSON object with keys like "key_concepts",
        "decisions_made", and "relationships".

        Raw Text:
        ---
        {tool_input.raw_text}
        ---

        Respond with only the JSON object.
        Distilled JSON:
        """

        try:
            response = self.llm.invoke(prompt)
            print("✅ Distillation complete.")
            return response
        except Exception as e:
            print(f"❌ ERROR in DistillerAgent: {e}")
            return f"An error occurred during distillation: {e}"


class ArchivistAgent(Tool):
    """
    A tool that embodies the ArchivistAgent. It takes a structured summary and
    persists it into the Neo4j knowledge graph by generating and executing
    Cypher queries.
    """
    def __init__(self, llm):
        super().__init__()
        self.llm = llm
        self.name = "ArchivistAgent"
        self.description = (
            "Takes a structured summary of insights and relationships and saves it to the "
            "long-term Neo4j knowledge graph. Use this to persist important information."
        )
        self.input_model = ArchiveInput

    def _run(self, tool_input: ArchiveInput) -> str:
        """
        The core logic for the ArchivistAgent tool.
        """
        print(f"🗄️  ArchivistAgent activated. Preparing to write to knowledge graph...")

        # In a real implementation, this is where you would connect to Neo4j.
        # For now, we will simulate the process.
        print("   (Simulating Neo4j connection...)")

        try:
            # For now, we'll just confirm that we received the data.
            # Later, this will involve generating Cypher queries from the JSON.
            summary_data = json.loads(tool_input.structured_summary)
            nodes_created = len(summary_data.get("key_concepts", []))
            rels_created = len(summary_data.get("relationships", []))
            
            success_message = f"✅ Archive complete. (Simulated) Persisted {nodes_created} nodes and {rels_created} relationships to the graph."
            print(success_message)
            return success_message
        except json.JSONDecodeError:
            error_message = "❌ ERROR in ArchivistAgent: Input was not valid JSON."
            print(error_message)
            return error_message
        except Exception as e:
            error_message = f"❌ ERROR in ArchivistAgent: {e}"
            print(error_message)
            return error_message

# We will add the ExtractorAgent and InjectorAgent classes here next.