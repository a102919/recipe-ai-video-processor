"""
Simple integration test for LangChain multi-provider support
"""
import os
import sys

# Set test API keys
os.environ['GEMINI_API_KEY'] = 'test_key_1'
os.environ['GEMINI_API_KEYS'] = 'test_key_1,test_key_2,test_key_3'

# Add src to path
sys.path.insert(0, 'src')

def test_imports():
    """Test that all modules can be imported"""
    print("Testing imports...")

    try:
        from config import (
            GEMINI_API_KEYS,
            GROK_API_KEYS,
            OPENAI_API_KEYS,
            LLM_PROVIDER_PRIORITY
        )
        print(f"✅ config module imported")
        print(f"   GEMINI_API_KEYS: {GEMINI_API_KEYS[:20]}...")
        print(f"   LLM_PROVIDER_PRIORITY: {LLM_PROVIDER_PRIORITY}")
    except Exception as e:
        print(f"❌ Failed to import config: {e}")
        return False

    try:
        from llm_config import APIKeyRotator, LLMProviderManager
        print(f"✅ llm_config module imported")
    except Exception as e:
        print(f"❌ Failed to import llm_config: {e}")
        import traceback
        traceback.print_exc()
        return False

    try:
        from analyzer import RecipeAnalyzer
        print(f"✅ analyzer module imported")
    except Exception as e:
        print(f"❌ Failed to import analyzer: {e}")
        import traceback
        traceback.print_exc()
        return False

    return True


def test_key_rotator():
    """Test API key rotation logic"""
    print("\nTesting APIKeyRotator...")

    from llm_config import APIKeyRotator

    try:
        # Test with multiple keys
        rotator = APIKeyRotator(['key1', 'key2', 'key3'])

        key1 = rotator.get_next()
        assert key1 == 'key1', f"Expected key1, got {key1}"

        key2 = rotator.get_next()
        assert key2 == 'key2', f"Expected key2, got {key2}"

        key3 = rotator.get_next()
        assert key3 == 'key3', f"Expected key3, got {key3}"

        # Should wrap around
        key1_again = rotator.get_next()
        assert key1_again == 'key1', f"Expected key1 (wrap), got {key1_again}"

        print(f"✅ Key rotation working correctly")
        return True
    except Exception as e:
        print(f"❌ Key rotation test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_llm_manager_init():
    """Test LLM provider manager initialization"""
    print("\nTesting LLMProviderManager initialization...")

    from llm_config import LLMProviderManager

    try:
        # Should work with Gemini keys only
        manager = LLMProviderManager()

        metadata = manager.get_provider_metadata()
        print(f"✅ LLMProviderManager initialized")
        print(f"   Primary provider: {metadata['primary_provider']}")
        print(f"   Total providers: {metadata['total_providers']}")
        print(f"   Provider chain: {metadata['provider_chain']}")

        return True
    except Exception as e:
        print(f"❌ LLMProviderManager init failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_backward_compatibility():
    """Test that old API still works"""
    print("\nTesting backward compatibility...")

    from analyzer import RecipeAnalyzer

    try:
        # Old way: passing api_key (should log warning but work)
        analyzer = RecipeAnalyzer(api_key='test_key')
        print(f"✅ RecipeAnalyzer accepts legacy api_key parameter")

        # New way: no parameters
        analyzer2 = RecipeAnalyzer()
        print(f"✅ RecipeAnalyzer works without parameters")

        return True
    except Exception as e:
        print(f"❌ Backward compatibility test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    print("=" * 60)
    print("LangChain Multi-Provider Integration Test")
    print("=" * 60)

    results = []

    results.append(('Imports', test_imports()))
    results.append(('APIKeyRotator', test_key_rotator()))
    results.append(('LLMProviderManager', test_llm_manager_init()))
    results.append(('Backward Compatibility', test_backward_compatibility()))

    print("\n" + "=" * 60)
    print("Test Results:")
    print("=" * 60)

    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {name}")

    all_passed = all(passed for _, passed in results)

    if all_passed:
        print("\n✅ All tests passed!")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed!")
        sys.exit(1)
