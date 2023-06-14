import gitlab
import os
from datetime import datetime

gl = gitlab.Gitlab.from_config("prod", ["./python-gitlab.cfg"])
gl.auth()

hiring_project = gl.projects.get(441)
hiring_issues = hiring_project.issues.list(get_all=True)

print(len(hiring_issues))


if not os.path.exists("docs"):
    os.makedirs("docs")

output = open(f"./docs/hiring_mgt.csv", "w")

output.write(f"NOM|ORIGINE|DATE|CV|DETAILS\n")

date_format = '%Y-%m-%dT%H:%M:%S.%fZ'

for issue in hiring_issues:
    #print(issue)

    nom = issue.title
    origine = 'n/a'
    for lbl in issue.labels:
        if lbl.startswith("origin"):
            origine =  lbl[8:]
    date = datetime.strptime(issue.created_at, date_format)
    date_txt = date.strftime('%Y-%m-%d')
    
    line = issue.description.split('\n')[0]
    cv = 'https://gitlab.softwareheritage.org/teams/management/hiring-management' + line[line.find('(')+1:line.find(')')]
    #print (cv)

    output.write(f"{nom}|{origine}|{date_txt}|{cv}|{issue.web_url}\n")

output.close()


