import gitlab
import os
from datetime import datetime

# product management group:
PM_GROUP = 858 


gl = gitlab.Gitlab.from_config("prod", ["./python-gitlab.cfg"])
gl.auth()
swh_group = gl.groups.get(PM_GROUP)

nb_issues = 0

output = open(f"./docs/tasks_2024.csv", "w")

output.write(f"project|type|issue|spent(days)|url|parent\n")

projects = swh_group.projects.list(iterator=True)

for gproject in projects:
    project = gl.projects.get(gproject.id)

    # type= issue
    issues = project.issues.list(iterator=True, type='TASK')

    for issue in issues:

        #issue = project.issues.get(issue_entry.iid)
        #if issue.type == 'TASK':
            # priority = ''
            # status = 'created'
            # r24 = 'n'
            # for label in issue.labels:
            #     if label == 'roadmap 2024' :
            #         r24='y'
            #        nb_issues+=1

            #     if label.startswith('priority::'):
            #         priority = label[10:]

            #     if label.startswith('status::'):
            #         status = label[8:]

            parent_issue = None

            if issue.type == 'TASK':    
                spent = issue.time_stats()['total_time_spent'] / 60 / 60 / 8
                
                if spent > 0 :
                
                    for note in issue.notes.list():
                        issue_index = note.body.find('as parent issue')
                        if issue_index > -1 :
                            parent_iid = note.body[7:issue_index-1]
                            #print(f'{note.body} => {note.body[7:issue_index-1]}')
                            #print(parent_iid)
                            parent_issue = project.issues.get(int(parent_iid))

                            output.write(f"{project.name}|{issue.type}|{issue.title}|{spent}|{issue.web_url}|{parent_issue.title}\n")
             
print(nb_issues, " tasks")

output.close()
