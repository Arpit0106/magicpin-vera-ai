"""
LLM Client
Production-ready OpenAI wrapper for Vera AI Challenge.

Features:
- Singleton client
- Retry with exponential backoff
- Timeout
- JSON output
- Provider abstraction
"""

from __future__ import annotations

import json
import logging
import os
import time
from abc import ABC, abstractmethod
from typing import Any, Dict

from openai import APITimeoutError, OpenAI, RateLimitError

logger = logging.getLogger(__name__)

DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
DEFAULT_TIMEOUT = 20
DEFAULT_RETRIES = 3


class BaseLLM(ABC):
    """Abstract interface for all LLM providers."""

    @abstractmethod
    def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
    ) -> Dict[str, Any]:
        pass


class OpenAIProvider(BaseLLM):
    """OpenAI implementation."""

    def __init__(self):

        api_key = os.getenv("OPENAI_API_KEY")

        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY environment variable not found."
            )

        self.client = OpenAI(api_key=api_key)

        self.model = DEFAULT_MODEL

    def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
    ) -> Dict[str, Any]:

        last_error = None

        for retry in range(DEFAULT_RETRIES):

            try:

                response = self.client.chat.completions.create(

                    model=self.model,

                    temperature=temperature,

                    timeout=DEFAULT_TIMEOUT,

                    response_format={
                        "type": "json_object"
                    },

                    messages=[

                        {
                            "role": "system",
                            "content": system_prompt,
                        },

                        {
                            "role": "user",
                            "content": user_prompt,
                        },

                    ],

                )

                text = response.choices[0].message.content

                if not text:
                    raise RuntimeError("Empty response from model.")

                return json.loads(text)

            except (
                APITimeoutError,
                RateLimitError,
                json.JSONDecodeError,
                RuntimeError,
            ) as e:

                last_error = e

                logger.warning(
                    "Retry %s/%s because: %s",
                    retry + 1,
                    DEFAULT_RETRIES,
                    str(e),
                )

                time.sleep(2 ** retry)

            except Exception as e:

                logger.exception(e)

                raise

        raise RuntimeError(
            f"OpenAI failed after retries: {last_error}"
        )


class MockLLM(BaseLLM):
    """
    Useful if API key is missing.
    Allows local development.
    """

    def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
    ) -> Dict[str, Any]:

        return {
            "body": "Hello from Mock LLM.",
            "cta": "Reply YES",
            "rationale": "Mock response.",
            "template_name": None,
            "template_params": [],
        }


class LLMFactory:

    @staticmethod
    def create() -> BaseLLM:

        provider = os.getenv(
            "LLM_PROVIDER",
            "openai",
        ).lower()

        if provider == "mock":
            return MockLLM()

        return OpenAIProvider()


_llm_instance: BaseLLM | None = None


def get_llm() -> BaseLLM:
    """
    Singleton accessor.
    """

    global _llm_instance

    if _llm_instance is None:
        _llm_instance = LLMFactory.create()

    return _llm_instance