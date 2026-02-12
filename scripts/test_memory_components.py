import sys
import os
import time

# Add src to path
sys.path.append(os.path.join(os.getcwd(), "src"))

from cradle.utils.logger import logger

def test_memory_vessel():
    print(">>> Testing MemoryVessel Initialization (expecting CPU load)...")
    try:
        from cradle.selrena.soul.memory.vector_store import global_memory_vessel
        
        # Test 1: Embedding Generation
        text = "Test memory phrase."
        logger.info(f"Generating embedding for: '{text}'")
        emb = global_memory_vessel._generate_embedding(text)
        print(f"Embedding length: {len(emb)}")
        if len(emb) > 0:
            print(">>> Embedding generation successful.")
        else:
            print(">>> Embedding generation FAILED.")
            
        # Test 2: Storage
        print(">>> Testing Storage (Episodic)...")
        global_memory_vessel.memorize_episode(
            "Selrena likes strawberry cake.",
            {"timestamp": str(time.time()), "topic": "preferences"}
        )
        
        # Test 3: Retrieval
        print(">>> Testing Retrieval...")
        results = global_memory_vessel.recall_episode("What does she like to eat?")
        print(f"Retrieved: {results}")
        
        if results and "strawberry cake" in results[0]:
            print(">>> Retrieval logic successful!")
        else:
            print(">>> Retrieval logic might be weak or failed.")
            
    except Exception as e:
        logger.error(f"Memory test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_memory_vessel()
