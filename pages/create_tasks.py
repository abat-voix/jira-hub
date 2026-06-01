"""
Страница создания задач с AI-чатом.
"""
import json
import streamlit as st
import pandas as pd
from jira_client import JiraClient, JiraTaskCreator
from groq_client import (
    PROMPT_FILE,
    generate_tasks_json,
    get_backend_label,
    supports_audio_transcription,
    transcribe_audio,
)


def _init_chat_state():
    """Инициализация session state для чата"""
    if 'chat_messages' not in st.session_state:
        st.session_state.chat_messages = []
    if 'generated_json' not in st.session_state:
        st.session_state.generated_json = ""


def _load_system_prompt() -> str:
    """Загрузка системного промпта из файла"""
    try:
        with open(PROMPT_FILE, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "Ты помощник для создания задач в Jira. Возвращай JSON."


def _render_ai_chat(container):
    """AI-чат для генерации задач из текста."""
    with container:
        st.markdown("### 🤖 AI-чат")
        st.caption(f"Активный LLM: {get_backend_label()}")

        _init_chat_state()

        # Редактируемый системный промпт
        with st.expander("⚙️ Системный промпт", expanded=False):
            system_prompt = st.text_area(
                "Системный промпт",
                value=_load_system_prompt(),
                height=200,
                key="system_prompt",
                label_visibility="collapsed"
            )

        # Контейнер чата с фиксированной высотой
        chat_container = st.container(height=400)
        with chat_container:
            for msg in st.session_state.chat_messages:
                with st.chat_message(msg["role"]):
                    if msg["role"] == "assistant":
                        st.code(msg["content"], language="json")
                    else:
                        st.markdown(msg["content"])

        if supports_audio_transcription():
            audio_value = st.audio_input("🎤 Голосовой ввод", key="voice_input")

            if audio_value is not None:
                # Проверяем не обработали ли уже этот аудиофайл
                audio_id = id(audio_value)
                if st.session_state.get('_last_audio_id') != audio_id:
                    with st.spinner("Распознавание речи..."):
                        audio_bytes = audio_value.read()
                        result = transcribe_audio(audio_bytes)

                    if result["success"]:
                        transcribed = result["text"]
                        st.session_state._last_audio_id = audio_id
                        st.session_state._transcribed_text = transcribed
                    else:
                        st.error(f"Ошибка распознавания: {result['error']}")
        else:
            st.caption("Голосовой ввод отключён: локальный режим использует Ollama без Whisper.")

        # Показываем распознанный текст если есть
        transcribed_text = st.session_state.get('_transcribed_text', '')
        if transcribed_text:
            st.info(f"🎤 Распознано: {transcribed_text}")
            if st.button("📨 Отправить голосовое", use_container_width=True):
                st.session_state.chat_messages.append({"role": "user", "content": transcribed_text})
                st.session_state._transcribed_text = ''

                with st.spinner("Генерация задач..."):
                    messages = [{"role": "system", "content": system_prompt}]
                    messages.extend(st.session_state.chat_messages)
                    result = generate_tasks_json(messages)

                if result["success"]:
                    st.session_state.chat_messages.append({"role": "assistant", "content": result["content"]})
                    st.session_state.generated_json = result["content"]
                else:
                    st.session_state.chat_messages.append({"role": "assistant", "content": f"Ошибка: {result['error']}"})

                st.rerun()

        # Текстовый ввод + кнопка отправки
        user_input = st.text_area(
            "Сообщение",
            placeholder="Опишите задачи текстом...",
            height=100,
            key="chat_user_input",
            label_visibility="collapsed"
        )

        btn_col1, btn_col2 = st.columns(2)
        with btn_col1:
            send_clicked = st.button("📨 Отправить", use_container_width=True, type="primary")
        with btn_col2:
            if st.button("🗑️ Очистить чат", use_container_width=True):
                st.session_state.chat_messages = []
                st.session_state.generated_json = ""
                st.session_state._transcribed_text = ''
                st.rerun()

        if send_clicked and user_input.strip():
            st.session_state.chat_messages.append({"role": "user", "content": user_input.strip()})

            with st.spinner("Генерация задач..."):
                messages = [{"role": "system", "content": system_prompt}]
                messages.extend(st.session_state.chat_messages)
                result = generate_tasks_json(messages)

            if result["success"]:
                json_str = result["content"]
                st.session_state.chat_messages.append({"role": "assistant", "content": json_str})
                st.session_state.generated_json = json_str
            else:
                error_msg = f"Ошибка: {result['error']}"
                st.session_state.chat_messages.append({"role": "assistant", "content": error_msg})

            st.rerun()

        # Кнопка вставки в редактор
        if st.session_state.generated_json:
            if st.button("📋 Вставить в редактор", use_container_width=True):
                st.session_state.task_json_input = st.session_state.generated_json
                st.rerun()


def _render_task_editor(container):
    """Редактор JSON + создание задач в Jira"""
    with container:
        st.markdown("### 📝 Редактор задач")

        with st.expander("📖 Формат JSON"):
            st.code('''{
  "jira_config": {
    "project_key": "TEST"
  },
  "tasks": [
    {
      "summary": "Название задачи",
      "description": "Описание задачи",
      "issuetype": "Task",
      "priority": "Medium",
      "labels": ["label1"],
      "assignee": "username",
      "epic_link": "EPIC-1",
      "components": ["Backend"]
    }
  ]
}''', language='json')

        # Используем значение из чата если есть
        default_json = st.session_state.get('task_json_input', '')

        json_input = st.text_area(
            "JSON с задачами",
            value=default_json,
            height=400,
            placeholder='{"jira_config": {"project_key": "TEST"}, "tasks": [...]}',
            label_visibility="collapsed",
            key="json_editor"
        )

        if st.button("🚀 Создать задачи", type="primary", use_container_width=True):
            if not json_input.strip():
                st.error("Введите JSON")
                return
            try:
                data = json.loads(json_input)
            except json.JSONDecodeError as e:
                st.error(f"Ошибка в JSON: {e}")
                return

            tasks = data.get('tasks', [])
            if not tasks:
                st.error('В JSON нет поля "tasks" или список пуст')
                return
            project_key = data.get('jira_config', {}).get('project_key', '')
            if not project_key:
                st.error('В JSON нет поля "jira_config.project_key"')
                return

            client: JiraClient = st.session_state.jira_client
            creator = JiraTaskCreator(client.base_url, client.api_token, client.email)

            with st.spinner(f"Создание {len(tasks)} задач в проекте {project_key}..."):
                results = creator.create_tasks_from_data(data)

            total = len(results['successful']) + len(results['failed'])
            st.markdown(f"### Результат: {len(results['successful'])}/{total} задач создано")

            if results['successful']:
                st.success(f"✅ Успешно создано: {len(results['successful'])}")
                rows = [{'Ключ': r['key'], 'Название': r['summary'], 'Ссылка': r['url']}
                        for r in results['successful']]
                df = pd.DataFrame(rows)
                st.dataframe(df, use_container_width=True, hide_index=True, column_config={
                    'Ключ': st.column_config.TextColumn('Ключ', width='small'),
                    'Название': st.column_config.TextColumn('Название', width='large'),
                    'Ссылка': st.column_config.LinkColumn('Ссылка', width='medium'),
                })

            if results['failed']:
                st.error(f"❌ Ошибки: {len(results['failed'])}")
                for fail in results['failed']:
                    st.markdown(f"- **{fail['summary']}**: `{fail['error']}`")


def render_task_creator():
    st.markdown("## ➕ Создание задач в Jira")

    if not st.session_state.connected or not st.session_state.jira_client:
        st.warning("👈 Сначала подключитесь к Jira через боковую панель")
        return

    # Две колонки: слева редактор, справа чат
    col_editor, col_chat = st.columns([1, 1])

    _render_task_editor(col_editor)
    _render_ai_chat(col_chat)
