import json
import os
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional

class LLMClient:
    def __init__(self):
        self.api_key = os.environ.get("OPENAI_API_KEY", "")
        self.model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        self.endpoint = "https://api.openai.com/v1/chat/completions"
        self.provider = os.environ.get("LLM_PROVIDER", "openai").lower()

    def complete(self, messages: List[Dict[str, str]], temperature: float = 0.0, max_tokens: int = 800) -> Optional[str]:
        """
        Sends a chat completion request.
        Tries OpenAI first if provider is 'openai' and key exists, otherwise falls back to local Ollama.
        """
        if self.provider == "openai" and self.api_key:
            body = json.dumps({
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "response_format": {"type": "json_object"} if "json" in str(messages[-1].get("content", "")).lower() else {"type": "text"}
            }).encode("utf-8")

            req = urllib.request.Request(
                self.endpoint,
                data=body,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }
            )

            try:
                # Use 20 seconds timeout for OpenAI
                with urllib.request.urlopen(req, timeout=20) as response:
                    resp_data = json.loads(response.read().decode("utf-8"))
                    return resp_data["choices"][0]["message"]["content"]
            except urllib.error.HTTPError as e:
                error_msg = e.read().decode("utf-8")
                print(f"[LLMClient Error] OpenAI HTTP Error {e.code}: {error_msg}")
                # If 429 or other, fall through to Ollama
            except Exception as e:
                print(f"[LLMClient Error] OpenAI exception: {e}")
                # Fall through to Ollama

        # Fallback to local Ollama
        print("[LLMClient] Invoking local Ollama (llama3)...")
        try:
            ollama_url = os.environ.get("OLLAMA_URL", "http://localhost:11434/api/chat")
            ollama_model = os.environ.get("OLLAMA_MODEL", "llama3")
            
            # Format system prompt inline if needed
            ollama_messages = []
            for msg in messages:
                ollama_messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })

            body = json.dumps({
                "model": ollama_model,
                "messages": ollama_messages,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens
                }
            }).encode("utf-8")

            req = urllib.request.Request(
                ollama_url,
                data=body,
                headers={"Content-Type": "application/json"}
            )
            
            with urllib.request.urlopen(req, timeout=25) as response:
                resp_data = json.loads(response.read().decode("utf-8"))
                return resp_data["message"]["content"]
        except Exception as ex:
            print(f"[LLMClient Error] Ollama fallback failed: {ex}")
            return None

llm_client = LLMClient()