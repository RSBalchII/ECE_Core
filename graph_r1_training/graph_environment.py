import networkx as nx

def create_simple_knowledge_graph():
    """
    Creates and returns a simple knowledge graph for agent training.

    The graph represents a small set of interconnected concepts
    to test basic navigation.

    Nodes:
    - 'A': Start Node
    - 'B': Intermediate Concept
    - 'C': Intermediate Concept
    - 'D': Target Node / Goal
    - 'E': Distractor Node

    Edges:
    - A -> B
    - B -> C
    - B -> D (Optimal Path)
    - A -> E
    - E -> C
    """
    G = nx.DiGraph()
    nodes = [
        ('A', {'description': 'Start Node'}),
        ('B', {'description': 'Intermediate Concept'}),
        ('C', {'description': 'Intermediate Concept'}),
        ('D', {'description': 'Target Node'}),
        ('E', {'description': 'Distractor Node'})
    ]
    edges = [('A', 'B'), ('B', 'C'), ('B', 'D'), ('A', 'E'), ('E', 'C')]

    G.add_nodes_from(nodes)
    G.add_edges_from(edges)

    return G

if __name__ == '__main__':
    # For testing purposes
    knowledge_graph = create_simple_knowledge_graph()
    print("Graph created successfully.")
    print(f"Nodes: {list(knowledge_graph.nodes(data=True))}")
    print(f"Edges: {list(knowledge_graph.edges())}")