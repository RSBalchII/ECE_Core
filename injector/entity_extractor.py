import spacy
from typing import Set

class EntityExtractor:
    """
    Extracts key concepts (entities) from a single block of text using spaCy.
    """
    def __init__(self):
        """Initializes the spaCy model."""
        try:
            self.nlp = spacy.load("en_core_web_sm")
            self.nlp.max_length = 60000000
        except OSError:
            print("Downloading 'en_core_web_sm' model. This may take a moment.")
            from spacy.cli import download
            download("en_core_web_sm")
            self.nlp = spacy.load("en_core_web_sm")
            self.nlp.max_length = 60000000

    def extract_entities_from_text(self, text: str) -> Set[str]:
        """
        Processes a block of text and extracts unique noun chunks.

        Args:
            text (str): The combined text content.

        Returns:
            Set[str]: A set of unique entities (as strings).
        """
        all_entities = set()
        doc = self.nlp(text)
        for chunk in doc.noun_chunks:
            entity = chunk.text.lower().strip()
            all_entities.add(entity)
        return all_entities

if __name__ == '__main__':
    from data_loader import load_combined_text

    path_to_text = '../../combined_text.txt'
    content = load_combined_text(path_to_text)
    
    if content:
        extractor = EntityExtractor()
        entities = extractor.extract_entities_from_text(content)
        print(f"Extracted {len(entities)} unique entities.")
        print("Sample entities:", list(entities)[:15])