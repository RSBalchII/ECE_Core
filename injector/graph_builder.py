import networkx as nx
from typing import Set
from itertools import combinations
import spacy

class GraphBuilder:
    """
    Builds a knowledge graph from a single text block and a set of extracted entities.
    """
    def __init__(self):
        self.nlp = spacy.load("en_core_web_sm")

    def build_cooccurrence_graph(self, full_text: str, entities: Set[str]) -> nx.Graph:
        """
        Builds a graph based on the co-occurrence of entities within the same sentence.

        Args:
            full_text (str): The entire text content from the combined file.
            entities (Set[str]): The set of unique entities to use as nodes.

        Returns:
            nx.DiGraph: The constructed knowledge graph.
        """
        G = nx.Graph()
        for entity in entities:
            G.add_node(entity, type='concept')

        doc = self.nlp(full_text.lower())
        for sent in doc.sents:
            sentence_text = sent.text
            present_entities = [e for e in entities if e in sentence_text]
            
            for entity1, entity2 in combinations(present_entities, 2):
                if G.has_edge(entity1, entity2):
                    G[entity1][entity2]['weight'] += 1
                else:
                    G.add_edge(entity1, entity2, weight=1)
        
        return G