# crews/archivist_crew.py

import logging
import concurrent.futures
from ollama import Client

# --- ARCHITECTURAL DECISION ---
# The Archivist Crew will use DeepSeek-Coder-v2 for all its sub-tasks.
# This model has a massive context window and is an expert at code and data analysis,
# making it the ideal choice for compressing and analyzing conversation data.
TECHNICAL_MODEL = "deepseek-coder-v2:16b-lite-instruct-q4_0"
SYNTHESIS_MODEL = "deepseek-coder-v2:16b-lite-instruct-q4_0"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def run_technical_analyst(ollama: Client, prompt: str) -> str:
    """
    A specialized agent that provides a technical summary of a conversation.
    """
    try:
        response = ollama.generate(model=TECHNICAL_MODEL, prompt=prompt)
        return response['response']
    except Exception as e:
        logging.error(f"Archivist Crew: Failed to run technical analyst: {e}")
        raise

def run_emotional_analyst(ollama: Client, prompt: str) -> str:
    """
    A specialized agent that analyzes the emotional subtext of a conversation.
    """
    try:
        response = ollama.generate(model=SYNTHESIS_MODEL, prompt=prompt)
        return response['response']
    except Exception as e:
        logging.error(f"Archivist Crew: Failed to run emotional analyst: {e}")
        raise

def run_archivist_crew(text_to_analyze: str) -> str:
    """
    Orchestrates a crew of specialized agents to analyze a text.
    """
    logging.info("Archivist Crew: Beginning parallel analysis...")
    ollama = Client(host='http://127.0.0.1:11434')
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        future_tech = executor.submit(run_technical_analyst, ollama, f"Analyze this text for technical keywords, code references, and project milestones. Be concise. Text: {text_to_analyze}")
        future_emo = executor.submit(run_emotional_analyst, ollama, f"Analyze this text for emotional subtext, user sentiment, and conversational dynamics. Be concise. Text: {text_to_analyze}")

        try:
            technical_summary = future_tech.result()
            emotional_summary = future_emo.result()
        except Exception as e:
            logging.error(f"Error executing tool 'run_archivist_crew': {e}")
            raise

    return f"Technical Summary: {technical_summary}\nEmotional Subtext: {emotional_summary}"

if __name__ == '__main__':
    # This is an example of how to use the tool in a script.
    example_text = "Rob: I have a bug in the code. Sybil: I see. Did you try reverting the commit? Rob: No, I didn't think of that. I will try it now. Sybil: Good plan. Let me know when you're done. Rob: Ok, it's fixed now! What's next? Sybil: Great job. Now we can test the new feature."
    print(run_archivist_crew(example_text))