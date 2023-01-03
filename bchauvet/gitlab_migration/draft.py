from roadmap_xls_to_gitlab import *
from datetime import datetime
import gitlab

import logging

#gl = gitlab.Gitlab.from_config("staging")

#gl.auth()


swh_group = gl.groups.get(25)

meta_project = gl.projects.get(2)


print(meta_project)

# swh_group.labels.delete("plop")

# issues = meta_project.issues.list(iterator=True, labels="roadmap_import")

# for issue in issues:
#     print(issue.iid)

# meta_project.issues.delete(5238)

# milestones = swh_group.milestones.list(get_all=True)

# for milestone in milestones:
#     print(f"{milestone.id} - {milestone.title}")

# swh_group.milestones.delete(156)


# print(meta_project)


# meta_project.issues.create({"title": "plop", "description": "let's rock"})
# lbl = swh_group.labels.create({"name": "foo", "color": "#8899aa"})
# print(lbl.id)


# logging.basicConfig(
#     filename=f"import_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log",
#     encoding="utf-8",
#     level=logging.INFO,
#     format="%(levelname)s:%(message)s",
# )

# logging.info("plop")
