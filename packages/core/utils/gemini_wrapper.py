"""
Gemini LLM Wrapper

Provides a LangChain-compatible interface for the new google-genai SDK.
This allows using gemini-3-flash-preview and other newer models.
"""

from google import genai
from typing import Any, Dict, List, Optional
import asyncio


class GeminiLLMResponse:
    """Response object that mimics LangChain's response structure"""

    def __init__(self, text: str):
        self.content = text
        self.text = text


class GeminiLLMWrapper:
    """
    Wrapper for google-genai SDK that provides LangChain-compatible interface.

    This allows using newer Gemini models like gemini-3-flash-preview
    while maintaining compatibility with existing code.
    """

    def __init__(
        self,
        model: str = "gemini-3-flash-preview",
        api_key: str = None,
        temperature: float = 0.7,
        **kwargs
    ):
        """
        Initialize Gemini LLM wrapper.

        Args:
            model: Model name (e.g., "gemini-3-flash-preview")
            api_key: Google API key
            temperature: Temperature for generation (0.0 to 1.0)
            **kwargs: Additional arguments (for compatibility)
        """
        self.model = model
        self.temperature = temperature
        self.client = genai.Client(api_key=api_key)

    async def ainvoke(self, prompt: str, **kwargs) -> GeminiLLMResponse:
        """
        Async invoke method (LangChain-compatible).

        Args:
            prompt: The prompt to send to the model
            **kwargs: Additional generation arguments

        Returns:
            GeminiLLMResponse with .content and .text attributes
        """
        # Run the sync generate_content in a thread pool to make it async
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=genai.types.GenerateContentConfig(
                    temperature=self.temperature,
                    **kwargs
                )
            )
        )

        return GeminiLLMResponse(response.text)

    def invoke(self, prompt: str, **kwargs) -> GeminiLLMResponse:
        """
        Sync invoke method (LangChain-compatible).

        Args:
            prompt: The prompt to send to the model
            **kwargs: Additional generation arguments

        Returns:
            GeminiLLMResponse with .content and .text attributes
        """
        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=genai.types.GenerateContentConfig(
                temperature=self.temperature,
                **kwargs
            )
        )

        return GeminiLLMResponse(response.text)
