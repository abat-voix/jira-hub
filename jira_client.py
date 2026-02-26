"""
Модуль для получения данных из Jira по спринтам
"""
import requests
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SprintInfo:
    """Информация о спринте"""
    id: int
    name: str
    state: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    board_id: Optional[int] = None
    board_name: Optional[str] = None


@dataclass
class Issue:
    """Задача Jira"""
    key: str
    summary: str
    issue_type: str
    status: str
    priority: str
    assignee: str
    estimated_hours: Optional[float] = None
    spent_hours: Optional[float] = None
    remaining_hours: Optional[float] = None
    created: Optional[str] = None
    updated: Optional[str] = None
    description: Optional[str] = None
    labels: list = field(default_factory=list)
    components: list = field(default_factory=list)
    parent_key: Optional[str] = None
    parent_summary: Optional[str] = None
    url: str = ""


@dataclass
class SprintData:
    """Полные данные по спринту"""
    sprint_info: Optional[SprintInfo]
    issues: list[Issue]
    total_estimated: float = 0
    total_spent: float = 0
    total_remaining: float = 0

    def __post_init__(self):
        self.total_estimated = sum(i.estimated_hours or 0 for i in self.issues)
        self.total_spent = sum(i.spent_hours or 0 for i in self.issues)
        self.total_remaining = self.total_estimated - self.total_spent


class JiraClient:
    """Клиент для работы с Jira API"""

    def __init__(self, base_url: str, api_token: str,
                 email: Optional[str] = None):
        self.base_url = base_url.rstrip('/')
        self.api_token = api_token
        self.email = email
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

    def test_connection(self) -> tuple[bool, str]:
        """Проверка подключения к Jira"""
        try:
            response = self.session.get(f'{self.base_url}/rest/api/2/myself')
            if response.status_code == 200:
                user = response.json()
                return True, f"Подключено как: {user.get('displayName', 'Unknown')}"
            return False, f"Ошибка авторизации: {response.status_code}"
        except Exception as e:
            return False, f"Ошибка подключения: {str(e)}"

    def get_all_sprints(self) -> list[SprintInfo]:
        """Получение списка всех спринтов"""
        sprints = []

        try:
            response = self.session.get(
                f'{self.base_url}/rest/agile/1.0/board',
                params={'maxResults': 100}
            )

            if response.status_code != 200:
                return sprints

            boards = response.json().get('values', [])

            for board in boards:
                sprints_response = self.session.get(
                    f'{self.base_url}/rest/agile/1.0/board/{board["id"]}/sprint',
                    params={'maxResults': 100, 'state': 'active'}
                )

                if sprints_response.status_code == 200:
                    for sprint in sprints_response.json().get('values', []):
                        sprints.append(SprintInfo(
                            id=sprint['id'],
                            name=sprint['name'],
                            state=sprint.get('state', 'unknown'),
                            start_date=sprint.get('startDate'),
                            end_date=sprint.get('endDate'),
                            board_id=board['id'],
                            board_name=board['name']
                        ))

            return sprints

        except Exception as e:
            print(f"Ошибка при получении спринтов: {e}")
            return sprints

    def find_sprint_by_name(self, sprint_name: str) -> Optional[SprintInfo]:
        """Поиск спринта по названию"""
        sprints = self.get_all_sprints()

        for sprint in sprints:
            if sprint_name.lower() in sprint.name.lower():
                return sprint

        return None

    def get_sprint_issues(self, sprint_name: str) -> Optional[SprintData]:
        """Получение всех задач спринта"""
        try:
            jql = f'Sprint = "{sprint_name}"'

            params = {
                'jql': jql,
                'maxResults': 100,
                'startAt': 0,
                'fields': 'summary,status,assignee,priority,issuetype,created,updated,'
                          'description,labels,components,timetracking,timeoriginalestimate,'
                          'timespent,parent'
            }

            all_issues = []

            while True:
                response = self.session.get(
                    f'{self.base_url}/rest/api/2/search',
                    params=params
                )

                if response.status_code != 200:
                    return None

                data = response.json()
                issues = data.get('issues', [])
                all_issues.extend(issues)

                total = data.get('total', 0)
                if len(all_issues) >= total:
                    break

                params['startAt'] += params['maxResults']

            formatted_issues = self._format_issues(all_issues)
            sprint_info = self.find_sprint_by_name(sprint_name)

            return SprintData(
                sprint_info=sprint_info,
                issues=formatted_issues
            )

        except Exception as e:
            print(f"Ошибка при получении задач спринта: {e}")
            return None

    def _format_issues(self, issues: list) -> list[Issue]:
        """Форматирование задач из API ответа"""
        formatted = []

        for issue in issues:
            fields = issue['fields']

            # Время
            time_estimate_seconds = fields.get('timeoriginalestimate')
            estimated_hours = round(time_estimate_seconds / 3600,
                                    2) if time_estimate_seconds else None

            time_tracking = fields.get('timetracking', {}) or {}
            time_spent_seconds = time_tracking.get('timeSpentSeconds', 0)
            spent_hours = round(time_spent_seconds / 3600,
                                2) if time_spent_seconds else None

            remaining_hours = None
            if estimated_hours is not None:
                remaining_hours = estimated_hours - (spent_hours or 0)

            # Родительская задача
            parent_key = None
            parent_summary = None
            if fields.get('parent'):
                parent_key = fields['parent'].get('key')
                if 'fields' in fields['parent']:
                    parent_summary = fields['parent']['fields'].get('summary')

            formatted.append(Issue(
                key=issue['key'],
                summary=fields['summary'],
                issue_type=fields['issuetype']['name'],
                status=fields['status']['name'],
                priority=fields.get('priority', {}).get('name',
                                                        'None') if fields.get(
                    'priority') else 'None',
                assignee=fields.get('assignee', {}).get('displayName',
                                                        'Не назначен') if fields.get(
                    'assignee') else 'Не назначен',
                estimated_hours=estimated_hours,
                spent_hours=spent_hours,
                remaining_hours=remaining_hours,
                created=fields.get('created'),
                updated=fields.get('updated'),
                description=fields.get('description', ''),
                labels=fields.get('labels', []),
                components=[comp['name'] for comp in
                            fields.get('components', [])],
                parent_key=parent_key,
                parent_summary=parent_summary,
                url=f"{self.base_url}/browse/{issue['key']}"
            ))

        return formatted


class JiraTaskCreator(JiraClient):
    """Создание задач в Jira из JSON-данных"""

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
        if 'summary' not in task_data:
            return {'success': False, 'summary': '', 'error': 'Missing required field: summary'}

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
                f'{self.base_url}/rest/api/2/issue',
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

        if not project_key:
            return {'successful': [], 'failed': [], 'project_key': ''}

        epic_field_id = self.get_epic_field_id()

        results = {'successful': [], 'failed': [], 'project_key': project_key}

        for task_data in tasks:
            result = self.create_task(task_data, project_key, epic_field_id)
            if result['success']:
                results['successful'].append(result)
            else:
                results['failed'].append(result)

        return results