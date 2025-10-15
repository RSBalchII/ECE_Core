"""
Example script demonstrating usage of the optimized QLearning and Distiller agents
"""

def demonstrate_optimized_qlearning():
    """
    Demonstrates how to use the optimized QLearning agent
    """
    try:
        # Import the optimized QLearning module
        from ece.agents.tier3.qlearning.qlearning_cpp import PyQLearningCore
        
        print("Initializing optimized QLearning agent...")
        agent = PyQLearningCore(
            state_size=1000, 
            action_size=200, 
            learning_rate=0.1, 
            discount_factor=0.95, 
            epsilon=0.1
        )
        
        print("Testing optimized QLearning operations...")
        
        # Test single action selection
        action = agent.get_action(50)
        print(f"Selected action for state 50: {action}")
        
        # Test single Q-value update
        agent.update_q_value(10, 5, 1.0, 15)
        print("Successfully updated Q-value for state 10, action 5")
        
        # Test batch update
        states = [1, 2, 3, 4, 5]
        actions = [0, 1, 0, 1, 0]
        rewards = [1.0, 0.5, 1.5, 0.8, 1.2]
        next_states = [2, 3, 4, 5, 6]
        agent.batch_update_q_values(states, actions, rewards, next_states)
        print("Successfully performed batch Q-value update")
        
        # Test pathfinding
        path = agent.find_optimal_path(0, 99, max_steps=10)
        print(f"Found path from 0 to 99: {path}")
        
        print("QLearning optimization demonstration completed successfully!")
        
    except ImportError as e:
        print(f"Could not import optimized QLearning module: {e}")
        print("Make sure to build the Cython extensions first using: python setup.py build_ext --inplace")
    
def demonstrate_optimized_distiller():
    """
    Demonstrates how to use the optimized Distiller agent
    """
    try:
        # Import the optimized Distiller module
        from ece.agents.tier3.distiller.distiller_cpp import PyDistillerCore
        
        print("\nInitializing optimized Distiller agent...")
        agent = PyDistillerCore()
        
        print("Testing optimized Distiller operations...")
        
        # Sample text for processing
        sample_text = """
        John Smith works at Google in New York. He joined on January 15, 2020.
        His email is john.smith@google.com, and he can be reached at www.johnsmith.com.
        The company Google was founded in September 1998 by Larry Page and Sergey Brin.
        """
        
        # Test entity extraction
        entities = agent.extract_entities(sample_text)
        print(f"Extracted entities: {list(entities.keys())}")
        
        # Test relationship extraction
        relationships = agent.extract_relationships(sample_text, entities)
        print(f"Found {len(relationships)} relationships")
        
        # Test text summarization
        summary = agent.summarize_text(sample_text, max_length=20)
        print(f"Summary (first 20 tokens): {summary}")
        
        print("Distiller optimization demonstration completed successfully!")
        
    except ImportError as e:
        print(f"Could not import optimized Distiller module: {e}")
        print("Make sure to build the Cython extensions first using: python setup.py build_ext --inplace")

if __name__ == "__main__":
    print("Demonstrating ECE Optimized Modules")
    print("="*50)
    
    demonstrate_optimized_qlearning()
    demonstrate_optimized_distiller()
    
    print("\nTo build the optimized modules, run: python setup.py build_ext --inplace")
    print("Or use the batch script: build_extensions.bat")