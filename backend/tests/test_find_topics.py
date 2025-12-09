import asyncio
from src.memory import TieredMemory

async def find_good_test_topics():
    """Find topics that have substantial memory content"""
    memory = TieredMemory()
    await memory.initialize()
    
    # Get some sample memories to see what topics exist
    print("Sampling database for topics with substantial content...")
    print("=" * 80)
    
    # Get recent memories from each category
    categories = ['event', 'idea', 'task', 'person', 'code', 'general']
    
    for category in categories:
        recent = await memory.get_recent_by_category(category, limit=3)
        if recent:
            print(f"\n{category.upper()} - {len(recent)} recent memories")
            print("-" * 40)
            for mem in recent:
                content_preview = mem.get('content', '')[:200].replace('\n', ' ')
                print(f"  • {content_preview}...")
    
    await memory.close()

if __name__ == "__main__":
    asyncio.run(find_good_test_topics())
