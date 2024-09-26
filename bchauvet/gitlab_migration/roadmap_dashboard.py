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

output.write(f"project|issue|type|priority|status|spent(days)|url|\n")

projects = swh_group.projects.list(iterator=True)

for gproject in projects:
    project = gl.projects.get(gproject.id)

    # type= issue
    issues = project.issues.list(iterator=True, type='ISSUE')

    for issue in issues:
        #issue = project.issues.get(issue_entry.iid)
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
                # time spent on issue:
                spent = issue.time_stats()['total_time_spent'] / 60 / 60 / 8
                output.write(f"{project.name}|{issue.title}|{type}|{priority}|{status}|{spent}|{issue.web_url}\n")
                nb_issues += 1

print(nb_issues, " issues")

output.close()
