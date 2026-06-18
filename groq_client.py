"""
LLM-клиент для генерации задач через облачный Groq или локальную Ollama.
"""
import json
import os

import requests
from groq import Groq

PROMPT_FILE = os.path.join(os.path.dirname(__file__), "prompts", "task_generator.txt")

_client = None
_ensured_ollama_models: set[str] = set()

DEFAULT_MODE = "cloud"
DEFAULT_GROQ_CHAT_MODEL = "llama-3.3-70b-versatile"
DEFAULT_GROQ_WHISPER_MODEL = "whisper-large-v3-turbo"
DEFAULT_OLLAMA_CHAT_MODEL = "gemma3:1b"
DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"


def get_llm_mode() -> str:
    """Возвращает режим работы LLM: cloud или local."""
    mode = os.getenv("LLM_MODE", DEFAULT_MODE).strip().lower()
    return mode if mode in {"cloud", "local"} else DEFAULT_MODE


def get_chat_model() -> str:
    """Возвращает модель чата с учетом выбранного режима."""
    explicit_model = os.getenv("LLM_CHAT_MODEL", "").strip()
    if explicit_model:
        return explicit_model

    if get_llm_mode() == "local":
        return os.getenv("OLLAMA_CHAT_MODEL", DEFAULT_OLLAMA_CHAT_MODEL)

    return os.getenv("GROQ_CHAT_MODEL", DEFAULT_GROQ_CHAT_MODEL)


def get_backend_label() -> str:
    """Человекочитаемое имя активного LLM-бэкенда."""
    if get_llm_mode() == "local":
        return f"Ollama ({get_chat_model()})"
    return f"Groq ({get_chat_model()})"


def supports_audio_transcription() -> bool:
    """Возвращает True, если доступна облачная транскрипция через Groq Whisper."""
    return get_llm_mode() == "cloud" and bool(os.getenv("GROQ_API_KEY", "").strip())


def _get_ollama_base_url() -> str:
    return os.getenv("OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL).rstrip("/")


def _is_truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _get_client() -> Groq:
    global _client
    if _client is None:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY не задан в .env")
        _client = Groq(api_key=api_key)
    return _client


def _ensure_ollama_model(model: str) -> None:
    """
    При OLLAMA_AUTO_PULL=true автоматически скачивает модель перед первым запросом.
    """
    global _ensured_ollama_models

    if model in _ensured_ollama_models or not _is_truthy(os.getenv("OLLAMA_AUTO_PULL")):
        return

    base_url = _get_ollama_base_url()

    try:
        response = requests.post(
            f"{base_url}/api/pull",
            json={"name": model, "stream": False},
            timeout=1800,
        )
        response.raise_for_status()
        _ensured_ollama_models.add(model)
    except requests.RequestException as exc:
        raise ValueError(
            "Не удалось скачать модель Ollama автоматически. "
            "Проверьте OLLAMA_BASE_URL или выключите OLLAMA_AUTO_PULL."
        ) from exc


def _generate_with_ollama(messages: list[dict]) -> dict:
    model = get_chat_model()
    _ensure_ollama_model(model)

    try:
        response = requests.post(
            f"{_get_ollama_base_url()}/api/chat",
            json={
                "model": model,
                "messages": messages,
                "stream": False,
                "format": "json",
                "options": {"temperature": 0.0},
            },
            timeout=600,
        )
        response.raise_for_status()
        payload = response.json()
        content = payload.get("message", {}).get("content", "")
        parsed = json.loads(content)
        return {"success": True, "content": json.dumps(parsed, ensure_ascii=False, indent=2)}
    except requests.RequestException as exc:
        return {"success": False, "error": f"Ошибка Ollama: {exc}"}
    except json.JSONDecodeError:
        return {
            "success": False,
            "error": "Ollama вернула ответ, который не удалось разобрать как JSON. "
                     "Попробуйте другую модель или уточните промпт."
        }


def generate_tasks_json(messages: list[dict]) -> dict:
    """
    Отправляет сообщения в выбранный LLM и возвращает structured JSON.

    Returns:
        {"success": True, "content": "json string"} или {"success": False, "error": "..."}
    """
    if get_llm_mode() == "local":
        return _generate_with_ollama(messages)

    try:
        client = _get_client()
        response = client.chat.completions.create(
            model=get_chat_model(),
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.0,
        )
        content = response.choices[0].message.content
        parsed = json.loads(content)
        return {"success": True, "content": json.dumps(parsed, ensure_ascii=False, indent=2)}
    except ValueError as e:
        return {"success": False, "error": str(e)}
    except json.JSONDecodeError:
        return {"success": True, "content": content}
    except Exception as e:
        return {"success": False, "error": str(e)}


def transcribe_audio(audio_bytes: bytes, filename: str = "audio.wav") -> dict:
    """
    Транскрибирует аудио через Groq Whisper API.

    Args:
        audio_bytes: байты аудиофайла
        filename: имя файла (для определения формата)

    Returns:
        {"success": True, "text": "распознанный текст"} или {"success": False, "error": "..."}
    """
    if not supports_audio_transcription():
        return {
            "success": False,
            "error": "Голосовой ввод доступен только в cloud-режиме с Groq Whisper."
        }

    try:
        client = _get_client()
        transcription = client.audio.transcriptions.create(
            file=(filename, audio_bytes),
            model=os.getenv("GROQ_WHISPER_MODEL", DEFAULT_GROQ_WHISPER_MODEL),
            language="ru",
            temperature=0.0,
        )
        return {"success": True, "text": transcription.text}
    except ValueError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        return {"success": False, "error": str(e)}
