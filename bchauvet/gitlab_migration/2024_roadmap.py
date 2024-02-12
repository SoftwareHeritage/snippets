import gitlab
import os
from datetime import datetime

# product management group:
PM_GROUP = 858 


gl = gitlab.Gitlab.from_config("prod", ["./python-gitlab.cfg"])
gl.auth()
swh_group = gl.groups.get(PM_GROUP)

nb_issues = 0
issues = swh_group.issues.list(iterator=True)


output = open(f"./docs/2024.csv", "w")

output.write(f"|issue|project|roadmap2024|\n")


for issue in issues:
    project = gl.projects.get(issue.project_id)
    r24 = 'n'
    if 'roadmap 2024' in issue.labels:
        r24='y'
    output.write(f"{project.name}|{issue.title}|{r24}\n")
    print(issue.title, ' : ', issue.labels, ' - priority:', '\n')
    nb_issues+=1

print(nb_issues, " issues")

output.close()
