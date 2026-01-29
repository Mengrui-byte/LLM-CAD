"""
LLM Client - 支持 OpenAI 兼容 API 的客户端
支持流式输出、重试、自定义端点
"""
import os
from typing import Optional, Generator
from openai import OpenAI
import httpx


class LLMClient:
    def __init__(self, base_url: str = None, api_key: str = None, model: str = None):
        """
        初始化 LLM 客户端
        优先级: 传入参数 > 环境变量 > 默认值
        """
        self.api_key = api_key or os.getenv("LLM_API_KEY") or "EMPTY"
        self.base_url = base_url or os.getenv("LLM_BASE_URL") or "http://localhost:8000/v1"
        self.model = model or os.getenv("LLM_MODEL") or "meta-llama/Meta-Llama-3-8B-Instruct"

        http_client = httpx.Client(
            timeout=120.0,
            transport=httpx.HTTPTransport(retries=3)
        )

        self.client = OpenAI(
            base_url=self.base_url,
            api_key=self.api_key,
            http_client=http_client,
            max_retries=3
        )
        
        print(f"[LLM] Initialized: model={self.model}, base_url={self.base_url}")

    def generate(
        self, 
        prompt: str, 
        system_prompt: str = "You are a helpful AI assistant for CAD modeling.",
        temperature: float = 0.1,
        max_tokens: int = 4096
    ) -> Optional[str]:
        """同步生成"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=temperature,
                max_tokens=max_tokens
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"[LLM] Error: {e}")
            return None

    def generate_stream(
        self,
        prompt: str,
        system_prompt: str = "You are a helpful AI assistant for CAD modeling.",
        temperature: float = 0.1,
        max_tokens: int = 4096
    ) -> Generator[str, None, None]:
        """流式生成"""
        try:
            stream = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True
            )
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            print(f"[LLM] Stream error: {e}")
            yield f"[ERROR] {e}"


# 默认客户端单例
default_client = LLMClient()
