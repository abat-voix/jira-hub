"""
Страница анализа спринтов
"""
import streamlit as st
import pandas as pd
from jira_client import JiraClient, SprintData


def render_sprint_selector():
    """Блок выбора спринта (отображается на странице анализа)"""
    client: JiraClient = st.session_state.jira_client

    st.markdown("### 🏃 Выбор спринта")

    input_mode = st.radio(
        "Способ выбора",
        options=["📋 Из списка", "✏️ Ввести название"],
        horizontal=True,
        label_visibility="collapsed"
    )

    sprint_name_to_load = None

    if input_mode == "✏️ Ввести название":
        col_input, col_btn = st.columns([3, 1])
        with col_input:
            manual_sprint = st.text_input(
                "Название спринта",
                placeholder="Например: 2026.2",
                help="Введите точное название спринта",
                label_visibility="collapsed"
            )
        with col_btn:
            if st.button("📊 Загрузить", use_container_width=True, key="load_manual"):
                if manual_sprint.strip():
                    sprint_name_to_load = manual_sprint.strip()
                else:
                    st.warning("Введите название спринта")

    else:
        with st.spinner("Загрузка спринтов..."):
            sprints = client.get_all_sprints()

        if not sprints:
            st.warning("Спринты не найдены")
            return

        active_sprints = [s for s in sprints if s.state == 'active']
        future_sprints = [s for s in sprints if s.state == 'future']
        closed_sprints = [s for s in sprints if s.state == 'closed']

        sprint_options = []
        sprint_map = {}

        for s in active_sprints:
            label = f"🟢 {s.name}"
            sprint_options.append(label)
            sprint_map[label] = s

        for s in future_sprints:
            label = f"🔵 {s.name}"
            sprint_options.append(label)
            sprint_map[label] = s

        for s in sorted(closed_sprints, key=lambda x: x.name, reverse=True)[:20]:
            label = f"⚪ {s.name}"
            sprint_options.append(label)
            sprint_map[label] = s

        col_select, col_btn = st.columns([3, 1])
        with col_select:
            selected = st.selectbox(
                "Спринт",
                options=sprint_options,
                help="🟢 Активный | 🔵 Будущий | ⚪ Завершённый",
                label_visibility="collapsed"
            )
        with col_btn:
            if st.button("📊 Загрузить", use_container_width=True, key="load_list"):
                if selected:
                    sprint_name_to_load = sprint_map[selected].name

    # Загрузка данных
    if sprint_name_to_load:
        with st.spinner(f"Загрузка задач спринта «{sprint_name_to_load}»..."):
            sprint_data = client.get_sprint_issues(sprint_name_to_load)
            if sprint_data:
                st.session_state.sprint_data = sprint_data
                st.rerun()
            else:
                st.error("Не удалось загрузить данные. Проверьте название спринта.")


def render_sprint_header(sprint_data: SprintData):
    info = sprint_data.sprint_info
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown(f"## 🏃 {info.name if info else 'Спринт'}")
        if info:
            st.caption(f"📋 Доска: {info.board_name or 'Неизвестно'}")
    with col2:
        if info:
            state_class = {
                'active': 'sprint-active', 'future': 'sprint-future', 'closed': 'sprint-closed'
            }.get(info.state, 'sprint-closed')
            state_label = {
                'active': '🟢 Активный', 'future': '🔵 Будущий', 'closed': '⚪ Завершён'
            }.get(info.state, info.state)
            st.markdown(f'<span class="{state_class}">{state_label}</span>', unsafe_allow_html=True)
    if info and (info.start_date or info.end_date):
        start = info.start_date[:10] if info.start_date else "?"
        end = info.end_date[:10] if info.end_date else "?"
        st.caption(f"📅 {start} → {end}")


def render_metrics(sprint_data: SprintData):
    issues = sprint_data.issues
    col1, col2, col3, col4, col5, col6 = st.columns(6)

    total_tasks = len(issues)
    unassigned = sum(1 for i in issues if i.assignee == 'Не назначен')

    done_statuses = ['Выполнено', 'Done', 'Closed', 'Resolved']
    in_progress_statuses = ['В работе', 'In Progress', 'Тестирование', 'Testing', 'Создан MR', 'Review']

    done_count = sum(1 for i in issues if any(s in i.status for s in done_statuses))
    in_progress_count = sum(1 for i in issues if any(s in i.status for s in in_progress_statuses))

    done_hours = sum(i.estimated_hours or 0 for i in issues if any(s in i.status for s in done_statuses))
    progress_pct = (done_hours / sprint_data.total_estimated * 100) if sprint_data.total_estimated > 0 else 0

    col1.metric("📋 Всего задач", total_tasks)
    col2.metric("✅ Выполнено", done_count)
    col3.metric("🔄 В работе", in_progress_count)
    col4.metric("⏱️ Оценка", f"{sprint_data.total_estimated:.0f} ч")
    col5.metric("📝 Залогировано", f"{sprint_data.total_spent:.1f} ч")
    col6.metric("⚠️ Без исполнителя", unassigned, delta_color="inverse")

    st.progress(min(progress_pct / 100, 1.0))
    st.caption(f"Прогресс по выполненным задачам: {progress_pct:.0f}% ({done_hours:.0f} из {sprint_data.total_estimated:.0f} ч)")


def render_status_breakdown(sprint_data: SprintData):
    st.markdown("### 📊 По статусам")
    by_status = {}
    for issue in sprint_data.issues:
        status = issue.status
        if status not in by_status:
            by_status[status] = {'count': 0, 'estimated': 0, 'spent': 0, 'issues': []}
        by_status[status]['count'] += 1
        by_status[status]['estimated'] += issue.estimated_hours or 0
        by_status[status]['spent'] += issue.spent_hours or 0
        by_status[status]['issues'].append(issue)

    status_order = ['Выполнено', 'Done', 'Финальное тестирование', 'Создан MR',
                    'Тестирование', 'Testing', 'Review', 'В работе', 'In Progress',
                    'Создан', 'Open', 'Необходимо сделать', 'To Do']
    status_icons = {
        'Выполнено': '✅', 'Done': '✅', 'Closed': '✅',
        'Финальное тестирование': '🔵', 'Создан MR': '🟣', 'Review': '🟣',
        'Тестирование': '🟡', 'Testing': '🟡',
        'В работе': '🟠', 'In Progress': '🟠',
        'Создан': '🔷', 'Open': '🔷',
        'Необходимо сделать': '⚪', 'To Do': '⚪'
    }

    sorted_statuses = [s for s in status_order if s in by_status]
    for s in by_status:
        if s not in sorted_statuses:
            sorted_statuses.append(s)

    for status in sorted_statuses:
        data = by_status[status]
        icon = status_icons.get(status, '📌')
        with st.expander(
            f"{icon} **{status}** — {data['count']} задач ({data['estimated']:.0f} ч)",
            expanded=(status in ['В работе', 'In Progress', 'Тестирование', 'Testing'])
        ):
            for issue in data['issues']:
                c1, c2, c3, c4 = st.columns([1, 3, 2, 2])
                with c1:
                    st.markdown(f"[`{issue.key}`]({issue.url})")
                with c2:
                    summary = issue.summary[:70] + ('...' if len(issue.summary) > 70 else '')
                    t = {'Bug': '🐛', 'Story': '📖', 'Task': '✔️', 'Epic': '🎯'}.get(issue.issue_type, '📋')
                    st.markdown(f"{t} {summary}")
                with c3:
                    hours_info = f"⏱️ {issue.estimated_hours:.0f}ч" if issue.estimated_hours else "⏱️ —"
                    if issue.spent_hours:
                        over = issue.spent_hours > (issue.estimated_hours or 0)
                        hours_info += f" / {'🔴' if over else ''}{issue.spent_hours:.1f}ч"
                    assignee = issue.assignee
                    if assignee == 'Не назначен':
                        st.markdown(f"{hours_info}<br>🚫 *Не назначен*", unsafe_allow_html=True)
                    else:
                        st.markdown(f"{hours_info}<br>👤 {assignee}", unsafe_allow_html=True)
                with c4:
                    comp = ', '.join(issue.components) if issue.components else '—'
                    st.markdown(f"🧩 {comp}")


def render_assignee_stats(sprint_data: SprintData):
    st.markdown("### 👥 По исполнителям")
    by_assignee = {}
    for issue in sprint_data.issues:
        a = issue.assignee
        if a not in by_assignee:
            by_assignee[a] = {'count': 0, 'estimated': 0, 'spent': 0, 'statuses': {}, 'components': set()}
        by_assignee[a]['count'] += 1
        by_assignee[a]['estimated'] += issue.estimated_hours or 0
        by_assignee[a]['spent'] += issue.spent_hours or 0
        s = issue.status
        if s not in by_assignee[a]['statuses']:
            by_assignee[a]['statuses'][s] = 0
        by_assignee[a]['statuses'][s] += 1
        by_assignee[a]['components'].update(issue.components)

    rows = []
    for assignee, data in by_assignee.items():
        status_str = ', '.join([f"{k}: {v}" for k, v in data['statuses'].items()])
        comp_str = ', '.join(sorted(data['components'])) if data['components'] else '—'
        rows.append({
            'Исполнитель': assignee,
            'Задач': data['count'],
            'Оценка (ч)': f"{data['estimated']:.0f}",
            'Залогировано (ч)': f"{data['spent']:.1f}",
            'Остаток (ч)': f"{data['estimated'] - data['spent']:.1f}",
            'Компоненты': comp_str,
            'Статусы': status_str
        })

    df = pd.DataFrame(rows).sort_values('Задач', ascending=False)
    st.dataframe(df, use_container_width=True, hide_index=True, column_config={
        'Исполнитель': st.column_config.TextColumn('Исполнитель', width='medium'),
        'Задач': st.column_config.NumberColumn('Задач', width='small'),
        'Оценка (ч)': st.column_config.TextColumn('Оценка', width='small'),
        'Залогировано (ч)': st.column_config.TextColumn('Залог.', width='small'),
        'Остаток (ч)': st.column_config.TextColumn('Остаток', width='small'),
        'Компоненты': st.column_config.TextColumn('Компоненты', width='medium'),
        'Статусы': st.column_config.TextColumn('Статусы', width='large'),
    })


def _format_in_progress_since(iso_str: str) -> str:
    """ISO timestamp ('2026-06-08T14:30:00.000+0300') → 'DD.MM.YYYY HH:MM'."""
    if not iso_str:
        return ''
    try:
        date_part, _, time_part = iso_str.partition('T')
        for i, ch in enumerate(time_part):
            if ch in '+-':
                time_part = time_part[:i]
                break
        time_part = time_part.split('.')[0]
        hh, mm = time_part.split(':')[:2]
        yyyy, mo, dd = date_part.split('-')
        return f"{dd}.{mo}.{yyyy} {hh}:{mm}"
    except Exception:
        return ''


def render_all_issues_table(sprint_data: SprintData):
    st.markdown("### 📁 Все задачи")
    issues = sprint_data.issues

    fcol1, fcol2, fcol3, fcol4 = st.columns(4)
    statuses = sorted(set(i.status for i in issues))
    assignees = sorted(set(i.assignee for i in issues))
    types = sorted(set(i.issue_type for i in issues))
    all_comps = sorted(set(c for i in issues for c in i.components) | ({'—'} if any(not i.components for i in issues) else set()))

    with fcol1:
        status_filter = st.multiselect("Статус", options=statuses, default=statuses)
    with fcol2:
        assignee_filter = st.multiselect("Исполнитель", options=assignees, default=assignees)
    with fcol3:
        type_filter = st.multiselect("Тип", options=types, default=types)
    with fcol4:
        component_filter = st.multiselect("Компонент", options=all_comps, default=all_comps)

    def comp_matches(issue):
        if not issue.components:
            return '—' in component_filter
        return any(c in component_filter for c in issue.components)

    filtered = [i for i in issues
                if i.status in status_filter and i.assignee in assignee_filter
                and i.issue_type in type_filter and comp_matches(i)]

    in_progress_statuses = {'В работе', 'In Progress'}

    def status_display(issue):
        if issue.status in in_progress_statuses and issue.in_progress_since:
            formatted = _format_in_progress_since(issue.in_progress_since)
            if formatted:
                return f"{issue.status} (с {formatted})"
        return issue.status

    rows = [{
        'Ключ': i.url, 'Тип': i.issue_type, 'Название': i.summary,
        'Статус': status_display(i), 'Исполнитель': i.assignee,
        'Компонент': ', '.join(i.components) if i.components else '—',
        'Оценка (ч)': i.estimated_hours or 0, 'Залогировано (ч)': i.spent_hours or 0,
        'Приоритет': i.priority
    } for i in filtered]

    df = pd.DataFrame(rows)
    event = st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        selection_mode="multi-row",
        on_select="rerun",
        key="all_issues_table",
        column_config={
            'Ключ': st.column_config.LinkColumn(
                'Ключ', width='small', display_text=r".*/browse/(.+)$"
            ),
            'Тип': st.column_config.TextColumn('Тип', width='small'),
            'Название': st.column_config.TextColumn('Название', width='large'),
            'Статус': st.column_config.TextColumn('Статус', width='large'),
            'Исполнитель': st.column_config.TextColumn('Исполнитель', width='medium'),
            'Компонент': st.column_config.TextColumn('Компонент', width='medium'),
            'Оценка (ч)': st.column_config.NumberColumn('Оценка', format="%.0f", width='small'),
            'Залогировано (ч)': st.column_config.NumberColumn('Залог.', format="%.1f", width='small'),
            'Приоритет': st.column_config.TextColumn('Приоритет', width='small'),
        },
    )
    st.caption(f"Показано {len(filtered)} из {len(issues)} задач")

    selected_rows = event.selection.rows if event and event.selection else []
    if selected_rows:
        selected_df = df.iloc[selected_rows]
        sum_estimated = selected_df['Оценка (ч)'].sum()
        sum_spent = selected_df['Залогировано (ч)'].sum()
        m1, m2, m3 = st.columns(3)
        m1.metric("☑️ Выбрано задач", len(selected_rows))
        m2.metric("⏱️ Сумма оценки", f"{sum_estimated:.0f} ч")
        m3.metric("📝 Сумма залогированного", f"{sum_spent:.1f} ч")

        selected_keys = [url.rsplit('/', 1)[-1] for url in selected_df['Ключ'].tolist()]
        _render_move_issues_block(sprint_data, selected_keys)
    else:
        st.caption("☑️ Отметьте задачи в таблице — снизу появится сумма «Оценки» и «Залогированного»")


def _render_move_issues_block(sprint_data: SprintData, selected_keys: list[str]):
    """Блок перемещения выбранных задач в другой спринт или в бэклог."""
    client: JiraClient = st.session_state.jira_client
    current_sprint_name = sprint_data.sprint_info.name if sprint_data.sprint_info else None

    with st.expander(f"🔄 Переместить выбранные задачи ({len(selected_keys)})", expanded=False):
        pending = st.session_state.get('move_pending')

        if not pending:
            with st.spinner("Загрузка списка спринтов..."):
                sprints = client.get_all_sprints()

            BACKLOG = '— Бэклог —'
            options = [BACKLOG] + [
                s.name for s in sprints if s.name != current_sprint_name
            ]
            target_map = {BACKLOG: ('backlog', None)}
            for s in sprints:
                if s.name != current_sprint_name:
                    target_map[s.name] = ('sprint', s.id)

            col_sel, col_btn = st.columns([3, 1])
            with col_sel:
                target_label = st.selectbox(
                    "Куда переместить",
                    options=options,
                    key='move_target_select',
                    label_visibility='collapsed'
                )
            with col_btn:
                if st.button("Подготовить", use_container_width=True, key='move_prepare'):
                    kind, sprint_id = target_map[target_label]
                    st.session_state.move_pending = {
                        'keys': selected_keys,
                        'kind': kind,
                        'sprint_id': sprint_id,
                        'label': target_label,
                    }
                    st.rerun()
        else:
            st.warning(
                f"Переместить **{len(pending['keys'])}** задач "
                f"({', '.join(pending['keys'][:5])}{'…' if len(pending['keys']) > 5 else ''}) "
                f"в **{pending['label']}**?"
            )
            confirm = st.checkbox("Подтверждаю перемещение", key='move_confirm')
            col_go, col_cancel = st.columns([1, 1])
            with col_go:
                if st.button("Переместить", disabled=not confirm, type='primary',
                             use_container_width=True, key='move_go'):
                    if pending['kind'] == 'backlog':
                        result = client.move_issues_to_backlog(pending['keys'])
                    else:
                        result = client.move_issues_to_sprint(pending['sprint_id'], pending['keys'])

                    if result['success']:
                        st.toast(f"✅ Перемещено {len(result['moved'])} задач в «{pending['label']}»", icon='✅')
                        del st.session_state.move_pending
                        if current_sprint_name:
                            refreshed = client.get_sprint_issues(current_sprint_name)
                            if refreshed:
                                st.session_state.sprint_data = refreshed
                        st.rerun()
                    else:
                        st.error(f"Ошибка перемещения: {result['error']}")
            with col_cancel:
                if st.button("Отмена", use_container_width=True, key='move_cancel'):
                    del st.session_state.move_pending
                    st.rerun()


def render_summary_table(sprint_data: SprintData):
    st.markdown("### 📋 Сводная таблица")
    summary = {}
    for issue in sprint_data.issues:
        key = (issue.issue_type, issue.status)
        if key not in summary:
            summary[key] = {'count': 0, 'estimated': 0, 'spent': 0}
        summary[key]['count'] += 1
        summary[key]['estimated'] += issue.estimated_hours or 0
        summary[key]['spent'] += issue.spent_hours or 0

    rows = [{
        'Тип': k[0], 'Статус': k[1], 'Задач': v['count'],
        'Оценка (ч)': v['estimated'], 'Залогировано (ч)': v['spent'],
        'Остаток (ч)': v['estimated'] - v['spent']
    } for k, v in summary.items()]

    df = pd.DataFrame(rows).sort_values(['Тип', 'Статус'])
    st.dataframe(df, use_container_width=True, hide_index=True, column_config={
        'Тип': st.column_config.TextColumn('Тип', width='small'),
        'Статус': st.column_config.TextColumn('Статус', width='medium'),
        'Задач': st.column_config.NumberColumn('Задач', width='small'),
        'Оценка (ч)': st.column_config.NumberColumn('Оценка', format="%.0f", width='small'),
        'Залогировано (ч)': st.column_config.NumberColumn('Залог.', format="%.1f", width='small'),
        'Остаток (ч)': st.column_config.NumberColumn('Остаток', format="%.1f", width='small'),
    })


def render_analysis_page():
    st.markdown("## 🏃 Анализ спринта")

    if not st.session_state.connected or not st.session_state.jira_client:
        st.info("👈 Подключитесь к Jira через боковую панель")
        with st.expander("📖 Как использовать"):
            st.markdown("""
            1. **Подключитесь к Jira** — убедитесь, что URL и API токен указаны в .env
            2. **Выберите спринт** из списка доступных или введите название
            3. **Нажмите "Загрузить"** для получения задач
            4. **Анализируйте** — используйте вкладки для разных представлений
            """)
        return

    render_sprint_selector()

    if st.session_state.sprint_data:
        sprint_data: SprintData = st.session_state.sprint_data

        st.markdown("---")
        render_sprint_header(sprint_data)

        st.markdown("---")
        render_metrics(sprint_data)

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
    else:
        st.info("☝️ Выберите спринт и нажмите «Загрузить»")
