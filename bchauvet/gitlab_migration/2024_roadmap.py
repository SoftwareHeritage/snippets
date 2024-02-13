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

output.write(f"issue|project|roadmap2024|url|\n")

projects = swh_group.projects.list(iterator=True)

for gproject in projects:
    project = gl.projects.get(gproject.id)

    # type= issue
    issues = project.issues.list(iterator=True, type='ISSUE')

    for issue in issues:
        if issue.type == 'ISSUE':
            r24 = 'n'
            if 'roadmap 2024' in issue.labels:
                r24='y'
            output.write(f"{project.name}|{issue.title}|{r24}|{issue.web_url}\n")
            print(issue.title, ' : ', issue.labels)
            nb_issues+=1
            print(issue)


print(nb_issues, " issues")

output.close()
