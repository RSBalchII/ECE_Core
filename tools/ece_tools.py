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

class ExtractInput(BaseModel):
    """Input schema for the ExtractorAgent tool."""
    question: str = Field(description="A natural language question about a topic that may be in the knowledge graph.")

class InjectInput(BaseModel):
    """Input schema for the InjectorAgent tool."""
    analysis_depth: str = Field(description="The level of effort for the analysis, e.g., 'shallow' or 'deep'.", default="shallow")


# === Tool Implementations ===

class DistillerAgent(Tool):
    """
    A tool that embodies the DistillerAgent. It takes a large block of raw text
    and uses an LLM to distill it into a structured summary of high-coherency
    insights and key conceptual relationships.
    """
    def __init__(self, llm):
        super().__init__()
        self.llm = llm
        self.name = "DistillerAgent"
        self.description = (
            "Analyzes raw text (e.g., session logs) to identify and summarize key insights, "
            "decisions, and conceptual relationships. Use this to process unstructured data."
        )
        self.input_model = DistillInput

    def _run(self, tool_input: DistillInput) -> str:
        """The core logic for the DistillerAgent tool."""
        print(f"🕵️  DistillerAgent activated. Analyzing text...")
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
        """The core logic for the ArchivistAgent tool."""
        print(f"🗄️  ArchivistAgent activated. Preparing to write to knowledge graph...")
        print("   (Simulating Neo4j connection...)")
        try:
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

class ExtractorAgent(Tool):
    """
    A tool that embodies the ExtractorAgent. It takes a natural language question,
    translates it into a Cypher query, executes it against the Neo4j knowledge
    graph, and returns the result as a context string.
    """
    def __init__(self, llm):
        super().__init__()
        self.llm = llm
        self.name = "ExtractorAgent"
        self.description = (
            "Answers a user's question by searching for relevant information in the "
            "long-term Neo4j knowledge graph. Use this to retrieve persisted memories."
        )
        self.input_model = ExtractInput

    def _run(self, tool_input: ExtractInput) -> str:
        """The core logic for the ExtractorAgent tool."""
        print(f"🔎 ExtractorAgent activated. Querying knowledge graph for: '{tool_input.question}'")
        print("   (Simulating NL to Cypher translation...)")
        simulated_cypher_query = f"MATCH (n) WHERE n.name CONTAINS '{tool_input.question}' RETURN n.summary"
        print(f"   Simulated Cypher Query: {simulated_cypher_query}")
        print("   (Simulating Neo4j connection and query execution...)")
        simulated_result = "Based on the knowledge graph, the refactor to the Youtu-agent framework was initiated to increase long-term velocity and adopt a more scalable foundation."
        print("✅ Extraction complete.")
        return simulated_result

class InjectorAgent(Tool):
    """
    A tool that embodies the InjectorAgent. It uses reinforcement learning to
    analyze and optimize the knowledge graph, inferring new connections and
    refining existing relationships.
    """
    def __init__(self, llm):
        super().__init__()
        self.llm = llm
        self.name = "InjectorAgent"
        self.description = (
            "Triggers a deep analysis of the knowledge graph to optimize it and infer "
            "new relationships. This is a long-running, asynchronous task."
        )
        self.input_model = InjectInput

    def _run(self, tool_input: InjectInput) -> str:
        """The core logic for the InjectorAgent tool."""
        print(f"🧠 InjectorAgent activated. Beginning graph optimization (Depth: {tool_input.analysis_depth})...")
        # The actual Q-learning or graph analysis logic is highly complex and
        # will be implemented here in the future.
        # For now, we simulate the initiation of this process.
        result = f"✅ (Simulated) Asynchronous graph optimization process initiated with depth '{tool_input.analysis_depth}'. The graph will be improved over time."
        print(result)
        return result