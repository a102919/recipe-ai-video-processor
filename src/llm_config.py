"""
LLM Configuration and Provider Management
Manages multiple LLM providers (Gemini, Grok, OpenAI) with automatic fallback and API key rotation
"""
import os
import logging
from typing import List, Optional, Dict, Any
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langchain_core.language_models import BaseChatModel

try:
    from .config import (
        GEMINI_API_KEYS,
        GROK_API_KEYS,
        OPENAI_API_KEYS,
        LLM_PROVIDER_PRIORITY
    )
except ImportError:
    # Fallback for direct imports (e.g., testing)
    from config import (
        GEMINI_API_KEYS,
        GROK_API_KEYS,
        OPENAI_API_KEYS,
        LLM_PROVIDER_PRIORITY
    )

logger = logging.getLogger(__name__)


class APIKeyRotator:
    """Simple round-robin API key rotation"""

    def __init__(self, keys: List[str]):
        """
        Initialize key rotator

        Args:
            keys: List of API keys to rotate
        """
        # Filter out empty keys
        self.keys = [k.strip() for k in keys if k and k.strip()]
        self.index = 0

        if not self.keys:
            raise ValueError("No valid API keys provided")

        logger.info(f"APIKeyRotator initialized with {len(self.keys)} key(s)")

    def get_next(self) -> str:
        """Get next key in rotation"""
        if not self.keys:
            raise ValueError("No API keys available")

        key = self.keys[self.index]
        self.index = (self.index + 1) % len(self.keys)
        return key

    def get_current_index(self) -> int:
        """Get current key index (for logging)"""
        return (self.index - 1) % len(self.keys)


class LLMProviderManager:
    """Manages multiple LLM providers with automatic fallback"""

    def __init__(
        self,
        gemini_keys: Optional[str] = None,
        grok_keys: Optional[str] = None,
        openai_keys: Optional[str] = None,
        provider_priority: Optional[str] = None
    ):
        """
        Initialize LLM provider manager

        Args:
            gemini_keys: Comma-separated Gemini API keys
            grok_keys: Comma-separated Grok API keys
            openai_keys: Comma-separated OpenAI API keys
            provider_priority: Comma-separated provider priority (e.g., "gemini,grok,openai")
        """
        self.gemini_keys_str = gemini_keys or GEMINI_API_KEYS
        self.grok_keys_str = grok_keys or GROK_API_KEYS
        self.openai_keys_str = openai_keys or OPENAI_API_KEYS
        self.provider_priority = (provider_priority or LLM_PROVIDER_PRIORITY).split(',')

        # Initialize key rotators
        self.key_rotators: Dict[str, Optional[APIKeyRotator]] = {}
        self._init_key_rotators()

        # Build provider chain
        self.providers: List[Dict[str, Any]] = []
        self._build_provider_chain()

        logger.info(f"LLMProviderManager initialized with {len(self.providers)} provider(s)")

    def _init_key_rotators(self) -> None:
        """Initialize API key rotators for each provider"""
        # Gemini
        if self.gemini_keys_str:
            try:
                self.key_rotators['gemini'] = APIKeyRotator(
                    self.gemini_keys_str.split(',')
                )
            except ValueError as e:
                logger.warning(f"Failed to initialize Gemini key rotator: {e}")
                self.key_rotators['gemini'] = None
        else:
            self.key_rotators['gemini'] = None

        # Grok
        if self.grok_keys_str:
            try:
                self.key_rotators['grok'] = APIKeyRotator(
                    self.grok_keys_str.split(',')
                )
            except ValueError as e:
                logger.warning(f"Failed to initialize Grok key rotator: {e}")
                self.key_rotators['grok'] = None
        else:
            self.key_rotators['grok'] = None

        # OpenAI
        if self.openai_keys_str:
            try:
                self.key_rotators['openai'] = APIKeyRotator(
                    self.openai_keys_str.split(',')
                )
            except ValueError as e:
                logger.warning(f"Failed to initialize OpenAI key rotator: {e}")
                self.key_rotators['openai'] = None
        else:
            self.key_rotators['openai'] = None

    def _build_provider_chain(self) -> None:
        """Build provider chain based on priority and available keys"""
        for provider_name in self.provider_priority:
            provider_name = provider_name.strip().lower()

            if provider_name == 'gemini' and self.key_rotators['gemini']:
                self.providers.append({
                    'name': 'gemini',
                    'rotator': self.key_rotators['gemini'],
                    'factory': self._create_gemini_model
                })
            elif provider_name == 'grok' and self.key_rotators['grok']:
                self.providers.append({
                    'name': 'grok',
                    'rotator': self.key_rotators['grok'],
                    'factory': self._create_grok_model
                })
            elif provider_name == 'openai' and self.key_rotators['openai']:
                self.providers.append({
                    'name': 'openai',
                    'rotator': self.key_rotators['openai'],
                    'factory': self._create_openai_model
                })

        if not self.providers:
            raise ValueError(
                "No LLM providers available. Please configure at least one of: "
                "GEMINI_API_KEYS, GROK_API_KEYS, OPENAI_API_KEYS"
            )

    def _create_gemini_model(self, api_key: str) -> BaseChatModel:
        """Create Gemini model instance"""
        return ChatGoogleGenerativeAI(
            model="gemini-2.0-flash-exp",
            google_api_key=api_key,
            temperature=0.7
        )

    def _create_grok_model(self, api_key: str) -> BaseChatModel:
        """Create Grok model instance (via OpenAI-compatible API)"""
        return ChatOpenAI(
            model="grok-2-vision-1212",
            openai_api_key=api_key,
            openai_api_base="https://api.x.ai/v1",
            temperature=0.7
        )

    def _create_openai_model(self, api_key: str) -> BaseChatModel:
        """Create OpenAI GPT-4o model instance"""
        return ChatOpenAI(
            model="gpt-4o",
            openai_api_key=api_key,
            temperature=0.7
        )

    def get_primary_model(self) -> BaseChatModel:
        """
        Get primary LLM model with automatic fallback

        Returns:
            LangChain ChatModel with fallback chain
        """
        if not self.providers:
            raise ValueError("No LLM providers available")

        # Create primary model (first in priority)
        primary_provider = self.providers[0]
        primary_key = primary_provider['rotator'].get_next()
        primary_model = primary_provider['factory'](primary_key)

        logger.info(
            f"Primary model: {primary_provider['name']} "
            f"(key index: {primary_provider['rotator'].get_current_index()})"
        )

        # Create fallback models (rest of providers)
        fallback_models = []
        for provider in self.providers[1:]:
            try:
                key = provider['rotator'].get_next()
                model = provider['factory'](key)
                fallback_models.append(model)
                logger.info(
                    f"Fallback model: {provider['name']} "
                    f"(key index: {provider['rotator'].get_current_index()})"
                )
            except Exception as e:
                logger.warning(f"Failed to create fallback model {provider['name']}: {e}")

        # Build fallback chain
        if fallback_models:
            return primary_model.with_fallbacks(fallback_models)
        else:
            return primary_model

    def get_provider_metadata(self) -> Dict[str, Any]:
        """
        Get metadata about current provider configuration

        Returns:
            Dict with provider info for logging/monitoring
        """
        if not self.providers:
            return {'error': 'No providers available'}

        primary = self.providers[0]
        return {
            'primary_provider': primary['name'],
            'primary_key_index': primary['rotator'].get_current_index(),
            'total_providers': len(self.providers),
            'provider_chain': [p['name'] for p in self.providers]
        }


# Global instance (lazy initialization)
_manager: Optional[LLMProviderManager] = None


def get_llm_manager() -> LLMProviderManager:
    """Get or create global LLM provider manager"""
    global _manager
    if _manager is None:
        _manager = LLMProviderManager()
    return _manager
