# Task Creator Tab Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a top-level "Создать задачи" tab to the Sprint Analyzer Streamlit app with a JSON form that creates Jira tasks.

**Architecture:** Add `JiraTaskCreator` class to `jira_client.py` (ported from user's standalone script, adapted to work with dict instead of file). Wrap `app.py` main content in two top-level tabs: existing sprint analysis and new task creator. The task creator tab requires an active Jira connection (same session state) but is independent of sprint data loading.

**Tech Stack:** Python, Streamlit, requests (already installed)

---

### Task 1: Add JiraTaskCreator class to jira_client.py

**Files:**
- Modify: `jira_client.py` (append after existing JiraClient class)

**Step 1: Add the class at the end of `jira_client.py`**

Append this code after the `JiraClient` class (after line 240):

```python


class JiraTaskCreator:
    """Создание задач в Jira из JSON-данных"""

    def __init__(self, base_url: str, api_token: str, email: Optional[str] = None):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()

        if email:
            self.session.auth = (email, api_token)
        else:
            self.session.headers.update({
                'Authorization': f'Bearer {api_token}'
            })

        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })

    def get_epic_field_id(self) -> Optional[str]:
        """Поиск ID поля Epic Link"""
        try:
            response = self.session.get(f'{self.base_url}/rest/api/2/field')
            if response.status_code == 200:
                for field in response.json():
                    if 'epic link' in field['name'].lower():
                        return field['id']
        except Exception:
            pass
        return None

    def create_task(self, task_data: dict, project_key: str, epic_field_id: Optional[str] = None) -> dict:
        """Создание одной задачи. Возвращает {'success': bool, 'key': str, 'url': str, 'error': str}"""
        payload = {
            'fields': {
                'project': {'key': project_key},
                'summary': task_data['summary'],
                'description': task_data.get('description', ''),
                'issuetype': {'name': task_data.get('issuetype', 'Task')}
            }
        }

        if 'priority' in task_data:
            payload['fields']['priority'] = {'name': task_data['priority']}

        if 'labels' in task_data:
            payload['fields']['labels'] = task_data['labels']

        if 'assignee' in task_data:
            payload['fields']['assignee'] = {'name': task_data['assignee']}

        if 'epic_link' in task_data and epic_field_id:
            payload['fields'][epic_field_id] = task_data['epic_link']

        if 'components' in task_data:
            payload['fields']['components'] = [{'name': c} for c in task_data['components']]

        try:
            response = self.session.post(
                f'{self.base_url}/rest/api/2/issue/',
                json=payload
            )
            if response.status_code == 201:
                info = response.json()
                return {
                    'success': True,
                    'key': info['key'],
                    'url': f"{self.base_url}/browse/{info['key']}",
                    'summary': task_data['summary']
                }
            else:
                return {
                    'success': False,
                    'summary': task_data['summary'],
                    'error': f"{response.status_code}: {response.text}"
                }
        except Exception as e:
            return {
                'success': False,
                'summary': task_data['summary'],
                'error': str(e)
            }

    def create_tasks_from_data(self, data: dict) -> dict:
        """Создание задач из словаря (распаршенный JSON).
        Возвращает {'successful': [...], 'failed': [...], 'project_key': str}
        """
        config = data.get('jira_config', {})
        tasks = data.get('tasks', [])
        project_key = config.get('project_key', '')

        epic_field_id = self.get_epic_field_id()

        results = {'successful': [], 'failed': [], 'project_key': project_key}

        for task_data in tasks:
            result = self.create_task(task_data, project_key, epic_field_id)
            if result['success']:
                results['successful'].append(result)
            else:
                results['failed'].append(result)

        return results
```

**Step 2: Verify the file is syntactically correct**

```bash
cd /Users/igor/develop/sprint-analyzer && python -c "from jira_client import JiraClient, JiraTaskCreator, SprintData; print('OK')"
```

Expected output: `OK`

**Step 3: Commit**

```bash
cd /Users/igor/develop/sprint-analyzer
git add jira_client.py
git commit -m "feat: add JiraTaskCreator class to jira_client"
```

---

### Task 2: Add render_task_creator() function to app.py

**Files:**
- Modify: `app.py` (add new function before `main()`)

**Step 1: Add the import for JiraTaskCreator at the top of app.py**

In `app.py` line 10, change:
```python
from jira_client import JiraClient, SprintData
```
to:
```python
from jira_client import JiraClient, JiraTaskCreator, SprintData
```

**Step 2: Add render_task_creator() function before the main() function (before line 474)**

```python
def render_task_creator():
    """Вкладка создания задач через JSON"""
    st.markdown("## ➕ Создание задач в Jira")

    if not st.session_state.connected or not st.session_state.jira_client:
        st.warning("👈 Сначала подключитесь к Jira через боковую панель")
        return

    st.markdown("Вставьте JSON с задачами и нажмите **Создать задачи**.")

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

    json_input = st.text_area(
        "JSON с задачами",
        height=300,
        placeholder='{"jira_config": {"project_key": "TEST"}, "tasks": [...]}',
        label_visibility="collapsed"
    )

    if st.button("🚀 Создать задачи", type="primary", use_container_width=False):
        if not json_input.strip():
            st.error("Введите JSON")
            return

        # Валидация JSON
        try:
            import json
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

        # Создаём задачи
        client: JiraClient = st.session_state.jira_client
        creator = JiraTaskCreator(client.base_url, client.api_token, client.email)

        with st.spinner(f"Создание {len(tasks)} задач в проекте {project_key}..."):
            results = creator.create_tasks_from_data(data)

        # Итоги
        total = len(results['successful']) + len(results['failed'])
        st.markdown(f"### Результат: {len(results['successful'])}/{total} задач создано")

        if results['successful']:
            st.success(f"✅ Успешно создано: {len(results['successful'])}")
            rows = [{'Ключ': r['key'], 'Название': r['summary'], 'Ссылка': r['url']}
                    for r in results['successful']]
            import pandas as pd
            df = pd.DataFrame(rows)
            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    'Ключ': st.column_config.TextColumn('Ключ', width='small'),
                    'Название': st.column_config.TextColumn('Название', width='large'),
                    'Ссылка': st.column_config.LinkColumn('Ссылка', width='medium'),
                }
            )

        if results['failed']:
            st.error(f"❌ Ошибки: {len(results['failed'])}")
            for fail in results['failed']:
                st.markdown(f"- **{fail['summary']}**: `{fail['error']}`")
```

**Step 3: Verify syntax**

```bash
cd /Users/igor/develop/sprint-analyzer && python -c "import app; print('OK')"
```

Expected output: `OK`

**Step 4: Commit**

```bash
cd /Users/igor/develop/sprint-analyzer
git add app.py
git commit -m "feat: add render_task_creator function to app"
```

---

### Task 3: Wrap main() with top-level tabs

**Files:**
- Modify: `app.py` — the `main()` function

**Step 1: Replace the content of main() after `init_session_state()` and the sidebar calls**

The current `main()` function (lines 474–546) renders everything in a single view. We need to:
1. Keep the title and `init_session_state()` at the top
2. Keep the sidebar calls (they render to sidebar, always visible)
3. Wrap main content in two top-level tabs

Find this block in `main()`:

```python
    # Отображаем данные спринта
    if st.session_state.sprint_data:
        sprint_data: SprintData = st.session_state.sprint_data

        st.markdown("---")
        render_sprint_header(sprint_data)

        st.markdown("---")
        render_metrics(sprint_data)

        # Табы
        tab1, tab2, tab3, tab4 = st.tabs([
            "📊 По статусам",
            "👥 По исполнителям",
            "📋 Сводная",
            "📁 Все задачи"
        ])

        with tab1:
            render_status_breakdown(sprint_data)

        with tab2:
            render_assignee_stats(sprint_data)

        with tab3:
            render_summary_table(sprint_data)

        with tab4:
            render_all_issues_table(sprint_data)

        # Информация о последнем обновлении
        st.sidebar.markdown("---")
        st.sidebar.caption(f"🕐 Загружено: {datetime.now().strftime('%d.%m.%Y %H:%M')}")

    else:
        # Начальный экран
        if not st.session_state.connected:
            st.info("👈 Подключитесь к Jira через боковую панель")
        else:
            st.info("👈 Выберите спринт и нажмите 'Загрузить данные'")

        with st.expander("📖 Как использовать"):
            st.markdown("""
            1. **Подключитесь к Jira** — введите URL вашего Jira сервера и API токен
            2. **Выберите спринт** из списка доступных
            3. **Нажмите "Загрузить данные"** для получения задач
            4. **Анализируйте** — используйте вкладки для разных представлений

            **Типы токенов:**
            - **Bearer Token** — Personal Access Token (PAT), email не нужен
            - **Basic Auth** — API ключ + email пользователя
            """)
```

Replace it with:

```python
    # Верхние табы
    main_tab1, main_tab2 = st.tabs(["🏃 Анализ спринта", "➕ Создать задачи"])

    with main_tab1:
        # Отображаем данные спринта
        if st.session_state.sprint_data:
            sprint_data: SprintData = st.session_state.sprint_data

            st.markdown("---")
            render_sprint_header(sprint_data)

            st.markdown("---")
            render_metrics(sprint_data)

            # Табы
            tab1, tab2, tab3, tab4 = st.tabs([
                "📊 По статусам",
                "👥 По исполнителям",
                "📋 Сводная",
                "📁 Все задачи"
            ])

            with tab1:
                render_status_breakdown(sprint_data)

            with tab2:
                render_assignee_stats(sprint_data)

            with tab3:
                render_summary_table(sprint_data)

            with tab4:
                render_all_issues_table(sprint_data)

            # Информация о последнем обновлении
            st.sidebar.markdown("---")
            st.sidebar.caption(f"🕐 Загружено: {datetime.now().strftime('%d.%m.%Y %H:%M')}")

        else:
            # Начальный экран
            if not st.session_state.connected:
                st.info("👈 Подключитесь к Jira через боковую панель")
            else:
                st.info("👈 Выберите спринт и нажмите 'Загрузить данные'")

            with st.expander("📖 Как использовать"):
                st.markdown("""
                1. **Подключитесь к Jira** — введите URL вашего Jira сервера и API токен
                2. **Выберите спринт** из списка доступных
                3. **Нажмите "Загрузить данные"** для получения задач
                4. **Анализируйте** — используйте вкладки для разных представлений

                **Типы токенов:**
                - **Bearer Token** — Personal Access Token (PAT), email не нужен
                - **Basic Auth** — API ключ + email пользователя
                """)

    with main_tab2:
        render_task_creator()
```

**Step 2: Verify syntax**

```bash
cd /Users/igor/develop/sprint-analyzer && python -c "import app; print('OK')"
```

Expected output: `OK`

**Step 3: Smoke test — launch the app**

```bash
cd /Users/igor/develop/sprint-analyzer && streamlit run app.py
```

Check that:
- Both top-level tabs appear
- "Создать задачи" tab shows the warning if not connected
- Existing sprint analysis still works normally

**Step 4: Commit**

```bash
cd /Users/igor/develop/sprint-analyzer
git add app.py
git commit -m "feat: add top-level tabs and task creator tab"
```

---

### Task 4: Expose api_token and email on JiraClient

**Context:** `render_task_creator()` accesses `client.api_token` and `client.email`, but `JiraClient.__init__` stores them as `self.api_token` and `self.email` — verify these attributes exist.

**Step 1: Check jira_client.py JiraClient.__init__**

Open `jira_client.py` lines 61–78. Confirm that `self.api_token = api_token` and `self.email = email` are present.

If missing, add them after line 63 (`self.base_url = ...`):

```python
        self.api_token = api_token
        self.email = email
```

**Step 2: Verify**

```bash
cd /Users/igor/develop/sprint-analyzer && python -c "
from jira_client import JiraClient
c = JiraClient('http://x', 'tok')
print(c.api_token, c.email)
"
```

Expected: `tok None`

**Step 3: Commit if changed**

```bash
cd /Users/igor/develop/sprint-analyzer
git add jira_client.py
git commit -m "fix: expose api_token and email as JiraClient attributes"
```