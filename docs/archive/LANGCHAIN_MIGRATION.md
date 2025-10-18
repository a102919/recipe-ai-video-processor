# LangChain Multi-Provider Migration Guide

## Overview

The video processor has been upgraded to support multiple LLM providers with automatic failover and API key rotation.

### What Changed

**Before:**
- Single provider: Gemini only
- Single API key
- Failure = complete service outage
- Rate limits = blocked requests

**After:**
- Multiple providers: Gemini → Grok → OpenAI
- Multiple API keys per provider
- Automatic failover between providers
- Round-robin key rotation to avoid rate limits
- Zero-downtime upgrades

## Features

### 1. Multi-Provider Support

Supports 3 LLM providers with automatic fallback:

| Provider | Model | Use Case | Priority |
|----------|-------|----------|----------|
| **Gemini** (Google) | gemini-2.0-flash-exp | Primary (cost-effective) | 1 |
| **Grok** (xAI) | grok-2-vision-1212 | Secondary (quality) | 2 |
| **OpenAI** | gpt-4o | Backup (highest quality) | 3 |

### 2. API Key Rotation

- Configure multiple API keys per provider (comma-separated)
- Automatic round-robin rotation
- Avoids rate limits and quota exhaustion
- Example: `GEMINI_API_KEYS=key1,key2,key3`

### 3. Automatic Failover

If Gemini fails → automatically tries Grok → then OpenAI
- No manual intervention needed
- Service remains available even if one provider is down
- Logged for monitoring and debugging

## Configuration

### Environment Variables

**Option 1: Single Key (Backward Compatible)**
```bash
# Old configuration still works
GEMINI_API_KEY=your_gemini_api_key_here
```

**Option 2: Multiple Keys (Recommended)**
```bash
# Multiple keys for automatic rotation
GEMINI_API_KEYS=key1,key2,key3
GROK_API_KEYS=xai-key1,xai-key2
OPENAI_API_KEYS=sk-xxx,sk-yyy

# Optional: customize provider priority
LLM_PROVIDER_PRIORITY=gemini,grok,openai
```

### Getting API Keys

- **Gemini**: https://aistudio.google.com/app/apikey
- **Grok**: https://console.x.ai/
- **OpenAI**: https://platform.openai.com/api-keys

## Code Changes

### Files Modified

1. **src/config.py** - Added LLM provider configurations
2. **src/analyzer.py** - Migrated to LangChain
3. **.env.example** - Updated with multi-provider documentation

### Files Created

1. **src/llm_config.py** - LLM provider manager and key rotator
2. **requirements.txt** - Added LangChain dependencies
3. **test_integration.py** - Integration tests

### Dependencies Added

```txt
langchain-core>=0.3.29
langchain-google-genai>=2.0.8
langchain-openai>=0.3.0
```

## Backward Compatibility

✅ **100% Backward Compatible**

- Existing code continues to work without changes
- `GEMINI_API_KEY` environment variable still supported
- `RecipeAnalyzer` API unchanged
- `analyze_recipe_from_frames()` function unchanged
- No breaking changes to main.py or other modules

### Deprecation Warnings

The following parameters are deprecated but still accepted:

```python
# Legacy usage (still works, logs warning)
analyzer = RecipeAnalyzer(api_key='xxx', model_name='xxx')

# Modern usage (recommended)
analyzer = RecipeAnalyzer()  # Uses env vars automatically
```

## Usage Examples

### Example 1: Gemini Only (Backward Compatible)

```bash
# .env
GEMINI_API_KEY=your_key_here
```

### Example 2: Multiple Gemini Keys

```bash
# .env
GEMINI_API_KEYS=key1,key2,key3
```

Behavior: Rotates through keys on each request

### Example 3: Multi-Provider with Failover

```bash
# .env
GEMINI_API_KEYS=gemini_key1,gemini_key2
GROK_API_KEYS=grok_key1
OPENAI_API_KEYS=openai_key1
```

Behavior:
1. Try Gemini key1
2. If fails → Try Gemini key2
3. If fails → Try Grok key1
4. If fails → Try OpenAI key1

### Example 4: Custom Provider Priority

```bash
# .env
GEMINI_API_KEYS=key1
OPENAI_API_KEYS=key2
LLM_PROVIDER_PRIORITY=openai,gemini  # Try OpenAI first
```

## Testing

### Run Integration Tests

```bash
cd video-processor
python3 test_integration.py
```

### Expected Output

```
✅ PASS: Imports
✅ PASS: APIKeyRotator
✅ PASS: LLMProviderManager
✅ PASS: Backward Compatibility

✅ All tests passed!
```

## Monitoring

### Logs

The system logs provider usage for monitoring:

```
INFO: LLMProviderManager initialized with 3 provider(s)
INFO: Primary model: gemini (key index: 0)
INFO: Fallback model: grok (key index: 0)
INFO: Fallback model: openai (key index: 0)
INFO: LLM API call succeeded in 2.34s (provider: gemini)
```

### Metadata in Response

Each analysis includes provider metadata:

```python
{
    'recipe': {...},
    'metadata': {
        'provider': 'gemini',
        'provider_metadata': {
            'primary_provider': 'gemini',
            'primary_key_index': 0,
            'total_providers': 3,
            'provider_chain': ['gemini', 'grok', 'openai']
        }
    }
}
```

## Troubleshooting

### Issue: "No LLM providers available"

**Cause:** No API keys configured

**Solution:** Set at least one of:
```bash
GEMINI_API_KEYS=xxx
GROK_API_KEYS=xxx
OPENAI_API_KEYS=xxx
```

### Issue: Import errors

**Cause:** Missing dependencies

**Solution:**
```bash
pip install -r requirements.txt
```

### Issue: Gemini API key version mismatch warning

**Cause:** LangChain requires newer google-ai-generativelanguage

**Solution:** This warning is harmless and doesn't affect functionality

## Architecture

### Class Diagram

```
RecipeAnalyzer
    ↓ uses
LLMProviderManager
    ↓ manages
[GeminiProvider, GrokProvider, OpenAIProvider]
    ↓ each has
APIKeyRotator (round-robin keys)
```

### Flow Diagram

```
Request
  ↓
RecipeAnalyzer.analyze_frames()
  ↓
LLMProviderManager.get_primary_model()
  ↓
Try Gemini (key1) → Success ✅
  ↓ (if fails)
Try Gemini (key2) → Fail ❌
  ↓
Try Grok (key1) → Fail ❌
  ↓
Try OpenAI (key1) → Success ✅
  ↓
Return Result
```

## Migration Checklist

For production deployment:

- [ ] Install new dependencies: `pip install -r requirements.txt`
- [ ] Configure at least one provider's API keys
- [ ] (Optional) Configure multiple keys per provider for rotation
- [ ] (Optional) Configure backup providers (Grok, OpenAI)
- [ ] Run integration tests: `python3 test_integration.py`
- [ ] Deploy to production
- [ ] Monitor logs for provider usage and failovers

## Cost Optimization

### Recommended Configuration

For cost-effective operation:

```bash
# Primary: Gemini (cheapest, multiple keys for high throughput)
GEMINI_API_KEYS=key1,key2,key3,key4,key5

# Backup: Grok (medium cost, single key for failover only)
GROK_API_KEYS=backup_key1

# Last resort: OpenAI (expensive, only if others fail)
OPENAI_API_KEYS=emergency_key1
```

This configuration:
- Uses cheap Gemini for 99% of requests
- Falls back to Grok/OpenAI only when needed
- Minimizes costs while maximizing availability

## Future Enhancements

Potential improvements:

1. **Dynamic provider selection** based on cost/quality/latency
2. **Health checks** to skip known-broken providers
3. **Usage analytics** to track costs per provider
4. **Rate limit detection** and automatic throttling
5. **Provider-specific retry strategies**

## Support

For issues or questions:
- Check logs for provider usage and errors
- Run integration tests: `python3 test_integration.py`
- Review .env.example for configuration examples
- Check this document for troubleshooting

---

**Last Updated:** 2025-10-15
**Version:** 2.0.0
**Status:** ✅ Production Ready
