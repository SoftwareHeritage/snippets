import gitlab
import os
from datetime import datetime

# product management group:
PM_GROUP = 858 
tasks_with_time_spent = []

gl = gitlab.Gitlab.from_config("prod", ["./python-gitlab.cfg"])
gl.auth()
swh_group = gl.groups.get(PM_GROUP)
projects = swh_group.projects.list(iterator=True)

class Task:
    def __init__(self, parent_id, spent):
        self.parent_id = parent_id
        self.spent = spent

def list_tasks():
    for gproject in projects:
        project = gl.projects.get(gproject.id)
        tasks = project.issues.list(iterator=True, type='TASK')

        for task in tasks:
            parent_issue = None
            if task.type == 'TASK':    
                spent = task.time_stats()['total_time_spent'] / 60 / 60 / 8               
                if spent > 0 :                
                    for note in task.notes.list():
                        issue_index = note.body.find('as parent issue')
                        if issue_index > -1 :
                            parent_iid = note.body[7:issue_index-1]
                            parent_issue = project.issues.get(int(parent_iid))
                            tasks_with_time_spent.append(Task(parent_issue.id, spent))
                            print(f'{task.title} - {spent} - {parent_issue.id}')

def process_issue(issue, project, output):
    if issue.type == 'ISSUE':
        priority = ''
        status = 'created'
        is_relevant = False
        type = 'other'

        for label in issue.labels:
            if label in ['roadmap 2024', 'MRO', 'off-roadmap'] :
                type = label
                is_relevant = True

            if label.startswith('priority::'):
                priority = label[10:]

            if label.startswith('status::'):
                status = label[8:]
            
        if is_relevant :
            print('.')
            # time spent on issue:
            spent = issue.time_stats()['total_time_spent'] / 60 / 60 / 8

            # search for time spent in subtasks (if any)
            for task in tasks_with_time_spent:
                if task.parent_id == issue.id:
                    spent += task.spent

            output.write(f"{project.name}|{issue.title}|{type}|{priority}|{status}|{spent}|{issue.web_url}\n")

def generate_csv(): 

    list_tasks()

    output = open(f"./docs/2024.csv", "w")

    output.write(f"project|issue|type|priority|status|spent(days)|url|\n")

    nb_issues = 0

    projects = projects = swh_group.projects.list(iterator=True)

    for gproject in projects:
        project = gl.projects.get(gproject.id)

        # type= issue
        issues = project.issues.list(iterator=True, type='ISSUE')

        for issue in issues:
            process_issue(issue, project, output)
            nb_issues += 1

    print(nb_issues, " issues")

    output.close()


generate_csv()
