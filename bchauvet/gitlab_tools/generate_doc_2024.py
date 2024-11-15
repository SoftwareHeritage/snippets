import gitlab
import os
from datetime import datetime

YEAR = 2024
BOARD_URL = "https://gitlab.softwareheritage.org/groups/product-management/-/boards?label_name[]=roadmap%202024"

# product management group:
PM_GROUP = 858 

gl = gitlab.Gitlab.from_config("prod", ["./python-gitlab.cfg"])
gl.auth()
swh_group = gl.groups.get(PM_GROUP)

nb_issues = 0


def write_header(output):

    output.write(".. _roadmap-current:\n")
    output.write(f".. _roadmap-{YEAR}:\n")
    output.write("\n")
    output.write(f"Roadmap {YEAR}\n")
    output.write("============\n")
    output.write("\n")
    output.write(
        f"(Version 1.0, last modified {datetime.now().strftime('%Y-%m-%d')})\n"
    )
    output.write("\n")
    output.write(
        "This document provides an overview of the technical roadmap of the Software\n"
    )
    output.write(f"Heritage initiative for the year {YEAR}.\n")
    output.write("\n")
    output.write(
        "Live tracking of the roadmap implementation progress during the year is\n"
    )
    output.write("available from a dedicated `GitLab board\n")
    output.write(f"<{BOARD_URL}>`_.\n")
    output.write("\n")
    output.write(".. contents::\n")
    output.write(":depth: 3\n")
    output.write("..\n")


def write_milestones(output):
    gl = gitlab.Gitlab.from_config("prod", ["./python-gitlab.cfg"])
    gl.auth()
    swh_group = gl.groups.get(PM_GROUP)
    projects = swh_group.projects.list(iterator=True)

    for gproject in projects:
        project = gl.projects.get(gproject.id)

        # Display project
        output.write("\n")
        output.write(f"{project.name}\n")
        output.write("-" * len(project.name) + "\n")
        output.write("\n")

        # type= issue
        issues = project.issues.list(iterator=True)

        for issue in issues:
            
            if issue.type == 'ISSUE':
                tags = []
                priority = ''
                status = 'created'
                r24 = 'n'
                for label in issue.labels:
                    if label == 'roadmap 2024' :
                        r24='y'
                        #nb_issues+=1
                    
                    if label.startswith('priority::'):
                        priority = label[10:]
                    
                    if label.startswith('status::'):
                        status = label[8:]
                    
                    if label.startswith('p_'):
                        tags.append(label.replace("p_", ""))
                    
                if r24 == 'y':
                    tags_str = tags.__str__().replace("[", "").replace("]", "").replace("'", "")
                    output.write("\n")
                    output.write(f"{issue.title}\n")
                    output.write("^" * len(issue.title) + "\n")
                    output.write("\n")

                    output.write(f"- `View in GitLab <{issue.web_url}>`__\n")
                    output.write(f"- Priority: {priority}\n")
                    output.write(f"- Tags: {tags_str}\n")
                    output.write(f"\n{issue.description}\n")
                    output.write("\n")


if not os.path.exists("docs"):
    os.makedirs("docs")

output = open(f"./docs/roadmap-{YEAR}.rst", "w")

write_header(output)
write_milestones(output)


output.close()
