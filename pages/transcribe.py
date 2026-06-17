"""
Самостоятельная страница транскрипции аудио в текст.
"""
import html
import tempfile
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from audio_utils import extract_audio_from_webm
from groq_client import supports_audio_transcription, transcribe_audio

SUPPORTED_AUDIO_TYPES = ["m4a", "mp3", "wav", "ogg", "flac", "webm"]
WHISPER_MODEL_SIZES = ["tiny", "base", "small", "medium", "large"]
GROQ_FILE_LIMIT_BYTES = 25 * 1024 * 1024


def _has_local_whisper() -> bool:
    try:
        import whisper  # noqa: F401
        return True
    except ImportError:
        return False


@st.cache_resource(show_spinner=False)
def _load_local_whisper_model(model_size: str):
    import whisper
    return whisper.load_model(model_size)


def _transcribe_locally(audio_bytes: bytes, audio_name: str, model_size: str) -> str:
    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = Path(tmpdir) / audio_name
        input_path.write_bytes(audio_bytes)
        model = _load_local_whisper_model(model_size)
        result = model.transcribe(str(input_path), fp16=False)
    return result["text"]


def _render_copy_button(text: str) -> None:
    escaped = html.escape(text).replace("`", "\\`").replace("\n", "\\n")
    components.html(
        f"""
        <button onclick="navigator.clipboard.writeText(`{escaped}`).then(
            () => this.innerText = 'Скопировано!',
            () => this.innerText = 'Ошибка'
        )" style="
            width:100%; padding:0.5rem 1rem; cursor:pointer;
            background:#f0f2f6; border:1px solid #d1d5db;
            border-radius:0.5rem; font-size:16px; font-family:inherit;
        ">Копировать текст</button>
        """,
        height=50,
    )


def render_transcribe_page():
    st.markdown("## 📝 Аудио → текст")
    st.caption("Транскрипция одного аудиофайла через Groq Whisper или локальный openai-whisper.")

    groq_available = supports_audio_transcription()
    local_available = _has_local_whisper()

    if not groq_available and not local_available:
        st.info(
            "Сейчас ни один движок не доступен. Для облачного режима включите `LLM_MODE=cloud` "
            "и задайте `GROQ_API_KEY`. Для локального режима установите `openai-whisper` и `ffmpeg`."
        )
        st.code("poetry add openai-whisper\nbrew install ffmpeg", language="bash")
        return

    if "transcribe_engine" not in st.session_state:
        st.session_state.transcribe_engine = "groq" if groq_available else "local"

    if st.session_state.transcribe_engine == "groq" and not groq_available:
        st.session_state.transcribe_engine = "local"
    if st.session_state.transcribe_engine == "local" and not local_available:
        st.session_state.transcribe_engine = "groq"

    st.radio(
        "Движок",
        options=["groq", "local"],
        format_func=lambda value: "Groq (быстро, облако)" if value == "groq" else "Локально (openai-whisper)",
        horizontal=True,
        disabled=not (groq_available and local_available),
        key="transcribe_engine",
        captions=[
            None if groq_available else "Недоступно: нужен cloud-режим и `GROQ_API_KEY`.",
            None if local_available else "Недоступно: пакет `openai-whisper` не установлен.",
        ],
    )

    engine = st.session_state.transcribe_engine

    if engine == "groq":
        st.caption("Язык: `ru`")
        model_size = None
    else:
        model_size = st.selectbox(
            "Модель Whisper",
            WHISPER_MODEL_SIZES,
            index=2,
            help="Чем больше модель, тем точнее результат, но дольше обработка.",
        )
        st.caption("Первая загрузка модели может занять время: Whisper скачает её в `~/.cache/whisper`.")

    audio_file = st.file_uploader(
        "Загрузите аудиофайл",
        type=SUPPORTED_AUDIO_TYPES,
        accept_multiple_files=False,
        key="transcribe_upload",
    )

    if engine == "groq" and audio_file is not None and audio_file.size > GROQ_FILE_LIMIT_BYTES:
        st.warning("Файл больше 25 MB. Groq Whisper обычно принимает файлы до 25 MB, запрос может завершиться ошибкой.")

    transcribe_clicked = st.button(
        "Транскрибировать",
        type="primary",
        use_container_width=True,
        disabled=audio_file is None,
        key="transcribe_audio_page",
    )

    if transcribe_clicked and audio_file is not None:
        audio_bytes = audio_file.getvalue()
        audio_name = audio_file.name

        if Path(audio_name).suffix.lower() == ".webm":
            try:
                with st.spinner("Извлекаю аудио из webm..."):
                    audio_bytes, audio_name = extract_audio_from_webm(audio_bytes, audio_name)
            except RuntimeError as exc:
                st.error(str(exc))
                return
            st.session_state.transcribe_extracted_audio = audio_bytes
            st.session_state.transcribe_extracted_name = audio_name
        else:
            st.session_state.pop("transcribe_extracted_audio", None)
            st.session_state.pop("transcribe_extracted_name", None)

        try:
            if engine == "groq":
                with st.spinner("Отправляю файл в Groq Whisper..."):
                    result = transcribe_audio(audio_bytes, filename=audio_name)
                if not result["success"]:
                    st.error(f"Ошибка транскрипции: {result['error']}")
                    return
                text = result["text"]
            else:
                with st.spinner(
                    f"Загрузка модели `{model_size}` и транскрипция... "
                    "На первом запуске модель может скачиваться несколько минут."
                ):
                    text = _transcribe_locally(audio_bytes, audio_name, model_size)
        except Exception as exc:
            st.error(f"Ошибка транскрипции: {exc}")
            return

        st.session_state.transcribe_result_text = text
        st.session_state.transcribe_result_name = Path(audio_file.name).stem + ".txt"

    text = st.session_state.get("transcribe_result_text", "")
    if text:
        st.subheader("Результат")
        st.text_area("Текст", value=text, height=320, key="transcribe_result")

        col_copy, col_download = st.columns(2)
        with col_copy:
            _render_copy_button(text)
        with col_download:
            st.download_button(
                "Скачать .txt",
                data=text.encode("utf-8"),
                file_name=st.session_state.get("transcribe_result_name", "transcript.txt"),
                mime="text/plain",
                use_container_width=True,
                key="download_transcript_text",
            )

        extracted_audio = st.session_state.get("transcribe_extracted_audio")
        extracted_name = st.session_state.get("transcribe_extracted_name")
        if extracted_audio and extracted_name:
            st.download_button(
                "Скачать MP3",
                data=extracted_audio,
                file_name=extracted_name,
                mime="audio/mpeg",
                use_container_width=True,
                key="download_extracted_mp3",
            )
