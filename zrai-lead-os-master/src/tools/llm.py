"""
LLM client for multi-provider support.
Requirements: Pluggable LLM (OpenAI/Anthropic/Gemini)
"""

from typing import Dict, Any, List, Optional, Union
from abc import ABC, abstractmethod
import logging
import json

from src.config import load_config, LLMProvider


logger = logging.getLogger(__name__)


class BaseLLMClient(ABC):
    """Base class for LLM clients."""
    
    @abstractmethod
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> str:
        """Generate text from prompt."""
        pass
    
    @abstractmethod
    def generate_structured(
        self,
        prompt: str,
        schema: Dict[str, Any],
        system_prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate structured output matching schema."""
        pass


class GoogleLLMClient(BaseLLMClient):
    """Google Gemini LLM client."""
    
    def __init__(self, api_key: str, model: str = "gemini-2.5-flash"):
        self._api_key = api_key
        self._model = model
        self._base_url = "https://generativelanguage.googleapis.com/v1beta"
    
    def _make_request(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Make request to Gemini API."""
        import urllib.request
        
        url = f"{self._base_url}{endpoint}"
        
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self._api_key,
        }
        
        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode(),
            headers=headers,
            method="POST",
        )
        
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode())
    
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> str:
        """Generate text using Gemini."""
        contents = []
        
        if system_prompt:
            contents.append({
                "role": "user",
                "parts": [{"text": f"System: {system_prompt}"}]
            })
            contents.append({
                "role": "model",
                "parts": [{"text": "Understood. I will follow these instructions."}]
            })
        
        contents.append({
            "role": "user",
            "parts": [{"text": prompt}]
        })
        
        data = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            }
        }
        
        result = self._make_request(
            f"/models/{self._model}:generateContent",
            data,
        )
        
        if "candidates" in result and result["candidates"]:
            return result["candidates"][0]["content"]["parts"][0]["text"]
        
        return ""
    
    def generate_structured(
        self,
        prompt: str,
        schema: Dict[str, Any],
        system_prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate structured output using Gemini."""
        schema_str = json.dumps(schema, indent=2)
        
        full_prompt = f"""
{prompt}

You MUST respond with valid JSON matching this schema:
{schema_str}

Respond ONLY with the JSON, no other text.
"""
        
        response = self.generate(
            full_prompt,
            system_prompt=system_prompt,
            temperature=0.3,  # Lower temperature for structured output
        )
        
        # Parse JSON from response
        try:
            # Try to extract JSON from response
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.startswith("```"):
                response = response[3:]
            if response.endswith("```"):
                response = response[:-3]
            
            return json.loads(response.strip())
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.debug(f"Response was: {response}")
            return {}


class OpenAILLMClient(BaseLLMClient):
    """OpenAI LLM client."""
    
    def __init__(self, api_key: str, model: str = "gpt-4o"):
        self._api_key = api_key
        self._model = model
        self._base_url = "https://api.openai.com/v1"
    
    def _make_request(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Make request to OpenAI API."""
        import urllib.request
        
        url = f"{self._base_url}{endpoint}"
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }
        
        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode(),
            headers=headers,
            method="POST",
        )
        
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode())
    
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> str:
        """Generate text using OpenAI."""
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.append({"role": "user", "content": prompt})
        
        data = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        
        result = self._make_request("/chat/completions", data)
        
        if "choices" in result and result["choices"]:
            return result["choices"][0]["message"]["content"]
        
        return ""
    
    def generate_structured(
        self,
        prompt: str,
        schema: Dict[str, Any],
        system_prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate structured output using OpenAI."""
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.append({"role": "user", "content": prompt})
        
        data = {
            "model": self._model,
            "messages": messages,
            "temperature": 0.3,
            "response_format": {"type": "json_object"},
        }
        
        result = self._make_request("/chat/completions", data)
        
        if "choices" in result and result["choices"]:
            content = result["choices"][0]["message"]["content"]
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                return {}
        
        return {}


class AnthropicLLMClient(BaseLLMClient):
    """Anthropic Claude LLM client."""
    
    def __init__(self, api_key: str, model: str = "claude-3-5-sonnet-20241022"):
        self._api_key = api_key
        self._model = model
        self._base_url = "https://api.anthropic.com/v1"
    
    def _make_request(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Make request to Anthropic API."""
        import urllib.request
        
        url = f"{self._base_url}{endpoint}"
        
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self._api_key,
            "anthropic-version": "2023-06-01",
        }
        
        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode(),
            headers=headers,
            method="POST",
        )
        
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode())
    
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> str:
        """Generate text using Claude."""
        data = {
            "model": self._model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        
        if system_prompt:
            data["system"] = system_prompt
        
        result = self._make_request("/messages", data)
        
        if "content" in result and result["content"]:
            return result["content"][0]["text"]
        
        return ""
    
    def generate_structured(
        self,
        prompt: str,
        schema: Dict[str, Any],
        system_prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate structured output using Claude."""
        schema_str = json.dumps(schema, indent=2)
        
        full_prompt = f"""
{prompt}

You MUST respond with valid JSON matching this schema:
{schema_str}

Respond ONLY with the JSON, no other text.
"""
        
        response = self.generate(
            full_prompt,
            system_prompt=system_prompt,
            temperature=0.3,
        )
        
        try:
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.startswith("```"):
                response = response[3:]
            if response.endswith("```"):
                response = response[:-3]
            
            return json.loads(response.strip())
        except json.JSONDecodeError:
            return {}


class MiniMaxLLMClient(BaseLLMClient):
    """MiniMax M2.1 LLM client (Official API)."""
    
    def __init__(self, api_key: str, model: str = "MiniMax-M2.1"):
        self._api_key = api_key
        self._model = model
        self._base_url = "https://api.minimax.io/v1"
    
    def _make_request(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Make request to MiniMax API."""
        import urllib.request
        
        url = f"{self._base_url}{endpoint}"
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }
        
        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode(),
            headers=headers,
            method="POST",
        )
        
        try:
            with urllib.request.urlopen(req) as response:
                return json.loads(response.read().decode())
        except urllib.error.HTTPError as e:
            error_body = e.read().decode()
            logger.error(f"MiniMax API error: {e.code} - {error_body}")
            raise
    
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> str:
        """Generate text using MiniMax M2.1."""
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.append({"role": "user", "content": prompt})
        
        data = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        
        result = self._make_request("/text/chatcompletion_v2", data)
        
        if "choices" in result and result["choices"]:
            return result["choices"][0]["message"]["content"]
        
        return ""
    
    def generate_structured(
        self,
        prompt: str,
        schema: Dict[str, Any],
        system_prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate structured output using MiniMax M2.1."""
        schema_str = json.dumps(schema, indent=2)
        
        full_prompt = f"""
{prompt}

You MUST respond with valid JSON matching this schema:
{schema_str}

Respond ONLY with the JSON, no other text.
"""
        
        response = self.generate(
            full_prompt,
            system_prompt=system_prompt,
            temperature=0.3,  # Lower temperature for structured output
        )
        
        # Parse JSON from response
        try:
            # Try to extract JSON from response
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.startswith("```"):
                response = response[3:]
            if response.endswith("```"):
                response = response[:-3]
            
            return json.loads(response.strip())
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.debug(f"Response was: {response}")
            return {}


class OpenRouterLLMClient(BaseLLMClient):
    """OpenRouter LLM client."""
    
    def __init__(self, api_key: str, model: str = "nex-agi/deepseek-v3.1-nex-n1:free"):
        self._api_key = api_key
        self._model = model
        self._base_url = "https://openrouter.ai/api/v1"
    
    def _make_request(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Make request to OpenRouter API."""
        import urllib.request
        
        url = f"{self._base_url}{endpoint}"
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
            "HTTP-Referer": "https://zrai-lead-os.com",
            "X-Title": "ZRAI Lead OS",
        }
        
        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode(),
            headers=headers,
            method="POST",
        )
        
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode())
    
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> str:
        """Generate text using OpenRouter."""
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.append({"role": "user", "content": prompt})
        
        data = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        
        result = self._make_request("/chat/completions", data)
        
        if "choices" in result and result["choices"]:
            return result["choices"][0]["message"]["content"]
        
        return ""
    
    def generate_structured(
        self,
        prompt: str,
        schema: Dict[str, Any],
        system_prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate structured output using OpenRouter."""
        schema_str = json.dumps(schema, indent=2)
        
        full_prompt = f"""
{prompt}

You MUST respond with valid JSON matching this schema:
{schema_str}

Respond ONLY with the JSON, no other text.
"""
        
        response = self.generate(
            full_prompt,
            system_prompt=system_prompt,
            temperature=0.3,  # Lower temperature for structured output
        )
        
        # Parse JSON from response
        try:
            # Try to extract JSON from response
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.startswith("```"):
                response = response[3:]
            if response.endswith("```"):
                response = response[:-3]
            
            return json.loads(response.strip())
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.debug(f"Response was: {response}")
            return {}


class LLMClient:
    """
    Unified LLM client with provider routing.
    """
    
    def __init__(
        self,
        provider: Optional[LLMProvider] = None,
        model: Optional[str] = None,
    ):
        config = load_config()
        
        self._provider = provider or config.llm.provider
        self._model = model or config.llm.model
        
        # Initialize the appropriate client
        if self._provider == LLMProvider.GOOGLE or self._provider == "google":
            if not config.llm.google_api_key:
                raise ValueError("Google API key not configured")
            self._client = GoogleLLMClient(config.llm.google_api_key, self._model)
        
        elif self._provider == LLMProvider.OPENAI or self._provider == "openai":
            if not config.llm.openai_api_key:
                raise ValueError("OpenAI API key not configured")
            self._client = OpenAILLMClient(config.llm.openai_api_key, self._model)
        
        elif self._provider == LLMProvider.ANTHROPIC or self._provider == "anthropic":
            if not config.llm.anthropic_api_key:
                raise ValueError("Anthropic API key not configured")
            self._client = AnthropicLLMClient(config.llm.anthropic_api_key, self._model)
        
        elif self._provider == LLMProvider.OPENROUTER or self._provider == "openrouter":
            if not config.llm.openrouter_api_key:
                raise ValueError("OpenRouter API key not configured")
            self._client = OpenRouterLLMClient(config.llm.openrouter_api_key, self._model)
        
        elif self._provider == LLMProvider.MINIMAX or self._provider == "minimax":
            if not config.llm.minimax_api_key:
                raise ValueError("MiniMax API key not configured")
            self._client = MiniMaxLLMClient(config.llm.minimax_api_key, self._model)
        
        else:
            raise ValueError(f"Unknown LLM provider: {self._provider}")
    
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> str:
        """Generate text."""
        return self._client.generate(prompt, system_prompt, temperature, max_tokens)
    
    def generate_structured(
        self,
        prompt: str,
        schema: Dict[str, Any],
        system_prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate structured output."""
        return self._client.generate_structured(prompt, schema, system_prompt)


# Global client instance
_llm_client: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    """Get the global LLM client instance."""
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client
