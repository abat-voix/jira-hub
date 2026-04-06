"""
Обёртка для Groq API — генерация задач через LLM
"""
import os
import json
from groq import Groq

PROMPT_FILE = os.path.join(os.path.dirname(__file__), "prompts", "task_generator.txt")

_client = None


def _get_client() -> Groq:
    global _client
    if _client is None:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY не задан в .env")
        _client = Groq(api_key=api_key)
    return _client


def generate_tasks_json(
    messages: list[dict],
    model: str = "llama-3.3-70b-versatile",
) -> dict:
    """
    Отправляет сообщения в Groq и возвращает structured JSON.

    Args:
        messages: список сообщений [{"role": "system"|"user"|"assistant", "content": "..."}]
        model: модель Groq

    Returns:
        {"success": True, "content": "json string"} или {"success": False, "error": "..."}
    """
    try:
        client = _get_client()
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.3,
        )
        content = response.choices[0].message.content
        # Валидируем что это корректный JSON
        parsed = json.loads(content)
        return {"success": True, "content": json.dumps(parsed, ensure_ascii=False, indent=2)}
    except ValueError as e:
        return {"success": False, "error": str(e)}
    except json.JSONDecodeError:
        return {"success": True, "content": content}
    except Exception as e:
        return {"success": False, "error": str(e)}
