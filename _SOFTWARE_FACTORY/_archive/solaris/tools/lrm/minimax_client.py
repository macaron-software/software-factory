#!/usr/bin/env python3
"""
LLM Client - Qwen3 Local (PRIMARY)
==================================
PRIMARY: Qwen3-30B-A3B local via llama-cpp (port 8080)

Usage:
    from minimax_client import LLMClient
    
    client = LLMClient()
    response = await client.chat("Hello!")
"""

import asyncio
import aiohttp


# Configuration
QWEN3_BASE_URL = "http://localhost:8002/v1"
QWEN3_MODEL = "Qwen3-30B-A3B-Instruct-Q4_K_S.gguf"


class LLMClient:
    """
    Client async pour Qwen3 local
    """
    
    def __init__(self):
        self.base_url = QWEN3_BASE_URL
        self.model = QWEN3_MODEL
    
    async def chat(self, prompt: str, max_tokens: int = 4096, temperature: float = 0.3) -> str:
        """
        Envoie un message via Qwen3 local
        """
        headers = {"Content-Type": "application/json"}
        
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": temperature
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=300)  # 5 min for long prompts
                ) as resp:
                    data = await resp.json()
                    
                    if resp.status == 200:
                        # OpenAI-compatible response format
                        choices = data.get("choices", [])
                        if choices:
                            return choices[0].get("message", {}).get("content", "")
                        return str(data)
                    else:
                        error = data.get("error", {}).get("message", str(data))
                        return f"Error: {error}"
        except asyncio.TimeoutError:
            return "Error: Qwen3 timeout (5min)"
        except aiohttp.ClientConnectorError:
            return "Error: Qwen3 server not running (port 8080)"
        except Exception as e:
            return f"Error: {e}"
    
    async def chat_with_retries(self, prompt: str, max_retries: int = 3) -> str:
        """Chat avec retries automatiques"""
        for attempt in range(max_retries):
            response = await self.chat(prompt)
            if not response.startswith("Error:"):
                return response
            await asyncio.sleep(2 ** attempt)  # Exponential backoff
        return response


async def test():
    """Test the client"""
    client = LLMClient()
    print("Testing Qwen3-30B-A3B local...")
    response = await client.chat("Say hello in French, in one word.")
    print(f"Response: {response}")
    return response


# Alias for backwards compatibility
MiniMaxClient = LLMClient


if __name__ == "__main__":
    asyncio.run(test())
