#!/usr/bin/env python3
"""
LLM Client - Unified LLM access for RLM system
===============================================

Architecture:
- BRAIN: Claude Opus 4.5 via claude CLI (heavy analysis)
- WIGGUM: MiniMax M2.1 via opencode (code generation)
- SUB-AGENTS: Qwen3-30B-A3B local via llama-cpp (fast iteration)

Usage:
    from llm_client import LLMClient
    
    client = LLMClient()
    response = await client.query("prompt", model="brain")
"""

import asyncio
import subprocess
import aiohttp
from typing import Optional
from datetime import datetime


def log(msg: str, level: str = "INFO"):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] [LLM] [{level}] {msg}", flush=True)


class LLMClient:
    """
    Unified LLM client for RLM system.
    
    Models:
    - "brain": Claude Opus 4.5 via claude CLI (heavy analysis, vision, LEAN)
    - "wiggum": MiniMax M2.1 via opencode (code generation, TDD)
    - "sub": Qwen3-30B-A3B local via llama-cpp port 8080 (fast iteration)
    """
    
    QWEN_PORT = 8080  # llama-cpp server port
    QWEN_TIMEOUT = 300  # 5 min timeout
    
    async def query(
        self, 
        prompt: str, 
        model: str = "wiggum",
        max_tokens: int = 4096,
        temperature: float = 0.3
    ) -> str:
        """
        Query LLM with routing based on model type.
        
        Args:
            prompt: The prompt to send
            model: "brain" | "wiggum" | "sub"
            max_tokens: Max tokens for response
            temperature: Sampling temperature
            
        Returns:
            LLM response text
        """
        if model == "brain":
            return await self._call_claude_opus(prompt)
        elif model == "wiggum":
            return await self._call_minimax(prompt)
        elif model == "sub":
            return await self._call_qwen_local(prompt, max_tokens, temperature)
        else:
            log(f"Unknown model {model}, defaulting to wiggum", "WARN")
            return await self._call_minimax(prompt)
    
    async def _call_claude_opus(self, prompt: str) -> str:
        """
        Call Claude Opus 4.5 via claude CLI.
        Used for: Brain analysis, vision, LEAN reasoning
        """
        log("Calling Claude Opus 4.5...")
        try:
            proc = await asyncio.create_subprocess_exec(
                "claude",
                "-p",  # Print mode (headless)
                "--model", "claude-opus-4-5-20251101",
                "--max-turns", "3",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                stdin=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(input=prompt.encode()),
                timeout=600,  # 10 min timeout for heavy analysis
            )
            
            if proc.returncode == 0:
                response = stdout.decode().strip()
                log(f"Claude Opus response: {len(response)} chars")
                return response
            else:
                error = stderr.decode()[:500]
                log(f"Claude Opus error: {error}", "ERROR")
                # Fallback to MiniMax
                return await self._call_minimax(prompt)
        except asyncio.TimeoutError:
            log("Claude Opus timeout (10min)", "ERROR")
            return await self._call_minimax(prompt)
        except Exception as e:
            log(f"Claude Opus exception: {e}", "ERROR")
            return await self._call_minimax(prompt)
    
    async def _call_minimax(self, prompt: str) -> str:
        """
        Call MiniMax M2.1 via direct API.
        Used for: Wiggum code generation, TDD iterations
        
        API: https://api.minimax.io/anthropic/v1/messages
        Key: Coding Plan API key
        """
        log("Calling MiniMax M2.1 via API...")
        import aiohttp
        
        MINIMAX_API_KEY = "sk-cp-eD0Qnhts0hNvqLx2jBX84TRB2dXYguPKDqUwtQbYFg01sRrlR2oYJGZ85zoPOXQH4b2sWVSfslcB3S-OFigNAYcDDJT6LA31vLwfijWiPmwWQpSmojeMVvw"
        MINIMAX_BASE_URL = "https://api.minimax.io/anthropic/v1"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{MINIMAX_BASE_URL}/messages",
                    headers={
                        "Content-Type": "application/json",
                        "x-api-key": MINIMAX_API_KEY,
                        "anthropic-version": "2023-06-01"
                    },
                    json={
                        "model": "MiniMax-M2.1",
                        "max_tokens": 4096,
                        "messages": [{"role": "user", "content": prompt}]
                    },
                    timeout=aiohttp.ClientTimeout(total=180),  # 3 min
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        # MiniMax format: content[0]=thinking, content[1]=text
                        content = data.get("content", [])
                        for item in content:
                            if item.get("type") == "text":
                                text = item.get("text", "")
                                if text:
                                    log(f"MiniMax M2.1 response: {len(text)} chars")
                                    return text
                        log("MiniMax no text in response", "WARN")
                        return await self._call_qwen_local(prompt)
                    else:
                        error_text = await resp.text()
                        log(f"MiniMax HTTP {resp.status}: {error_text[:200]}", "WARN")
                        return await self._call_qwen_local(prompt)
        except asyncio.TimeoutError:
            log("MiniMax timeout (3min), fallback to Qwen", "WARN")
            return await self._call_qwen_local(prompt)
        except Exception as e:
            log(f"MiniMax exception: {e}, fallback to Qwen", "WARN")
            return await self._call_qwen_local(prompt)
    
    async def _call_qwen_local(
        self, 
        prompt: str,
        max_tokens: int = 4096,
        temperature: float = 0.3
    ) -> str:
        """
        Call Qwen3-30B-A3B local via llama-cpp HTTP API.
        Used for: Sub-agents, fast iterations, fallback
        
        Server: llama-server on port 8080
        Context: 32768 tokens
        """
        log("Calling Qwen3-30B-A3B local...")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"http://localhost:{self.QWEN_PORT}/v1/chat/completions",
                    json={
                        "model": "local/qwen3-30b-a3b",
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": max_tokens,
                        "temperature": temperature,
                    },
                    timeout=aiohttp.ClientTimeout(total=self.QWEN_TIMEOUT),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        content = (
                            data.get("choices", [{}])[0]
                            .get("message", {})
                            .get("content", "")
                        )
                        if content:
                            log(f"Qwen3 response: {len(content)} chars")
                            return content
                        log("Qwen3 empty response", "WARN")
                        return "Error: Empty response from Qwen3"
                    else:
                        log(f"Qwen3 HTTP {resp.status}", "ERROR")
                        return f"Error: Qwen3 returned {resp.status}"
        except Exception as e:
            log(f"Qwen3 exception: {e}", "ERROR")
            return f"Error: Qwen3 unavailable - {e}"


# Singleton instance
_client: Optional[LLMClient] = None

def get_client() -> LLMClient:
    global _client
    if _client is None:
        _client = LLMClient()
    return _client


async def query(prompt: str, model: str = "wiggum", **kwargs) -> str:
    """Convenience function for quick queries"""
    return await get_client().query(prompt, model, **kwargs)


# Test
if __name__ == "__main__":
    async def test():
        client = LLMClient()
        
        print("\n=== Test MiniMax M2.1 (wiggum) ===")
        response = await client.query("Say hello in one word", model="wiggum")
        print(f"Response: {response[:200]}")
        
        print("\n=== Test Qwen3 local (sub) ===")
        response = await client.query("Say hello in one word", model="sub")
        print(f"Response: {response[:200]}")
        
        print("\n✅ LLM Client ready")
    
    asyncio.run(test())
