import gitlab
import os
from datetime import datetime

YEAR = 2023
BOARD_URL = "https://gitlab-staging.swh.network/groups/swh/-/milestones?sort=name_asc"
ROADMAP_PREFIX = "[Roadmap - $GOAL] "
SWH_GROUP = 25


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
    gl = gitlab.Gitlab.from_config("staging", ["./python-gitlab.cfg"])
    gl.auth()
    swh_group = gl.groups.get(SWH_GROUP)

    _milestones = swh_group.milestones.list(get_all=True)

    goals = [
        "Collect",
        "Preserve",
        "Share",
        "Documentation",
        "Technical Debt",
        "Tooling and Infrastructure",
    ]

    milestones = [[]] * len(goals)

    # group milestones by Goal
    for i in range(len(goals)):
        goal = goals[i]
        prefix = ROADMAP_PREFIX.replace("$GOAL", goal).lower()
        for milestone in _milestones:
            if milestone.title.lower().startswith(prefix):
                milestone.title = milestone.title[len(prefix) :]
                milestones[i].append(milestone)

    # display goals & milestones
    for i in range(len(goals)):
        goal = goals[i]
        output.write("\n")
        output.write(f"{goal}\n")
        output.write("-" * len(goal) + "\n")
        output.write("\n")
        for milestone in milestones[i]:
            output.write("\n")
            output.write(f"{milestone.title}\n")
            output.write("^" * len(milestone.title) + "\n")
            output.write("\n")

            output.write(f"- `Milestone: <{milestone.web_url}>`__\n")
            output.write(f"{milestone.description}\n")
            output.write("\n")

if not os.path.exists("docs"):
    os.makedirs("docs")

output = open(f"./docs/roadmap-{YEAR}.rst", "w")

write_header(output)
write_milestones(output)


output.close()
