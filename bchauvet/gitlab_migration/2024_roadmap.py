import gitlab
import os
from datetime import datetime

# product management group:
PM_GROUP = 858 


gl = gitlab.Gitlab.from_config("prod", ["./python-gitlab.cfg"])
gl.auth()
swh_group = gl.groups.get(PM_GROUP)

nb_issues = 0

output = open(f"./docs/2024.csv", "w")

output.write(f"project|issue|priority|status|url|\n")

projects = swh_group.projects.list(iterator=True)

for gproject in projects:
    project = gl.projects.get(gproject.id)

    # type= issue
    issues = project.issues.list(iterator=True, type='ISSUE')

    for issue in issues:
        if issue.type == 'ISSUE':
            priority = ''
            status = 'created'
            r24 = 'n'
            for label in issue.labels:
                if label == 'roadmap 2024' :
                    r24='y'
                    nb_issues+=1

                if label.startswith('priority::'):
                    priority = label[10:]

                if label.startswith('status::'):
                    status = label[8:]

                
            if r24 == 'y':
                output.write(f"{project.name}|{issue.title}|{priority}|{status}|{issue.web_url}\n")
                print(issue.title, ' : ', issue.labels)



print(nb_issues, " issues")

output.close()
