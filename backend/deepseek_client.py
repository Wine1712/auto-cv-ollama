from openai import OpenAI
import os

DEEPSEEK_API_KEY = os.getenv("sk-d4a94cab23334b30b6f53866a4a74f31")

client = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com"
)


def deepseek_generate(prompt: str, model: str = "deepseek-chat", temperature: float = 0.2):

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "user", "content": prompt}
        ],
        temperature=temperature
    )

    return response.choices[0].message.content.strip()