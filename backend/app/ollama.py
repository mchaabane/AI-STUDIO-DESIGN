import httpx


OLLAMA_URL = "http://127.0.0.1:11434"
OLLAMA_MODEL = "qwen3:8b"


async def generate(prompt: str) -> str:
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": "/no_think\n" + prompt,
        "stream": False,
        "options": {
            "temperature": 0.2,
            "top_p": 0.8,
            "top_k": 20,
            "num_predict": 15000,
        },
    }

    timeout = httpx.Timeout(
        connect=10.0,
        read=600.0,
        write=30.0,
        pool=30.0,
    )

    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(
            f"{OLLAMA_URL}/api/generate",
            json=payload,
        )

        response.raise_for_status()

        data = response.json()

        return data["response"]
