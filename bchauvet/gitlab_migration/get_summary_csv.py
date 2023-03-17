import gitlab
import os
from datetime import datetime

BOARD_URL = "https://gitlab.softwareheritage.org/groups/swh/-/milestones?sort=name_asc"
ROADMAP_PREFIX = "[Roadmap - $GOAL]"
SWH_GROUP = 25
SEPARATOR = "|"


def write_milestones(output):
    gl = gitlab.Gitlab.from_config("prod", ["./python-gitlab.cfg"])
    gl.auth()
    swh_group = gl.groups.get(SWH_GROUP)

    _milestones = swh_group.milestones.list(get_all=True)

    goals = [
        "Collect",
        "Preserve",
        "Share",
        "Documentation",
        "Technical debt",
        "Tooling and infrastructure",
    ]

    milestones = [[]] * len(goals)

    # group milestones by Goal
    for i in range(len(goals)):
        goal = goals[i]
        prefix = ROADMAP_PREFIX.replace("$GOAL", goal)
        for milestone in _milestones:
            if milestone.title.endswith(prefix):
                milestones[i].append(milestone)


    # header

    output.write(f"goal|milestone|priority|lead|effort\n")


    # display goals & milestones
    for i in range(len(goals)):
        goal = goals[i]
        prefix = ROADMAP_PREFIX.replace("$GOAL", goal)
        for milestone in milestones[i]:
            
            if milestone.title.endswith(prefix):
                
                title = milestone.title.replace(prefix, "")
                priority = ""
                lead = ""
                effort = ""

                description = milestone.description.splitlines()
                priority_prefix = "- Priority: "
                lead_prefix = "- Lead: "
                effort_prefix = "- Effort: "
                for line in description:
                    if line.startswith(priority_prefix):
                        priority = line[priority_prefix.__len__():]
                    if line.startswith(lead_prefix):
                        lead = line[lead_prefix.__len__():]
                    if line.startswith(effort_prefix):
                        effort = line[effort_prefix.__len__():]


                output.write(f"{goal}|{title}|{priority}|{lead}|{effort}\n")             

if not os.path.exists("docs"):
    os.makedirs("docs")

output = open(f"./docs/summary.csv", "w")

write_milestones(output)


output.close()
