import os
import sys
import networkx as nx

# Add the project root to the sys.path to allow for absolute imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from injector.data_loader import load_combined_text
from injector.entity_extractor import EntityExtractor
from graph_injector.graph_builder import GraphBuilder

class GraphInjector:
    """
    Orchestrates the entire process of creating a knowledge graph from a single text file.
    """
    def __init__(self, text_file_path: str):
        self.text_path = text_file_path
        self.entity_extractor = EntityExtractor()
        self.graph_builder = GraphBuilder()

    def run_pipeline(self) -> nx.DiGraph:
        """
        Executes the full data loading, entity extraction, and graph building pipeline.

        Returns:
            nx.DiGraph: The final, populated knowledge graph.
        """
        print("--- Starting Graph Injection Pipeline ---")

        # 1. Load Data
        print(f"Step 1: Loading combined text from {self.text_path}...")
        content = load_combined_text(self.text_path)
        if not content:
            print("Pipeline halted: No content found in the text file.")
            return nx.DiGraph()
        print(f"Loaded {len(content)} characters.")

        # 2. Extract Entities
        print("Step 2: Extracting entities...")
        entities = self.entity_extractor.extract_entities_from_text(content)
        print(f"Extracted {len(entities)} unique entities.")

        # 3. Build Graph
        print("Step 3: Building co-occurrence graph...")
        knowledge_graph = self.graph_builder.build_cooccurrence_graph(content, entities)
        print("Graph built successfully.")
        print(f"Final Graph: {knowledge_graph.number_of_nodes()} nodes, {knowledge_graph.number_of_edges()} edges.")
        
        print("--- Pipeline Complete ---")
        return knowledge_graph

if __name__ == '__main__':
    PATH_TO_TEXT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'combined_text.txt'))
    
    injector = GraphInjector(PATH_TO_TEXT)
    final_graph = injector.run_pipeline()

    if final_graph.number_of_nodes() > 0:
        print("\nPipeline successful. The knowledge graph is ready for the agent.")
