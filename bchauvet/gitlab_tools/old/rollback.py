from roadmap_xls_to_gitlab import *
import os

from datetime import datetime

if not os.path.exists("logs"):
    os.makedirs("logs")

logging.basicConfig(
    filename=f"logs/rollback_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log",
    encoding="utf-8",
    level=logging.INFO,
    format="%(levelname)s:%(message)s",
)


def delete_roadmap_milestones():

    _milestones = swh_group.milestones.list(get_all=True)

    for milestone in _milestones:
        # if milestone.title.startswith(ROADMAP_PREFIX):
        swh_group.milestones.delete(milestone.id)
        logging.info(f"deleted milestone: id={milestone.id} - {milestone.title}")


def delete_issues_by_label(label, project_id):

    _project = gl.projects.get(project_id)

    _issues = _project.issues.list(get_all=True, labels=label)

    for issue in _issues:
        _project.issues.delete(issue.iid)
        logging.info(f"deleted issue: issue_iid={issue.iid} - {issue.title}")


def delete_labels():
    labels = load_labels()

    for label in labels:
        swh_group.labels.delete(label.full_name())
        logging.info(f"deleted label: {label.full_name()}")


delete_roadmap_milestones()

delete_issues_by_label("roadmap_import", META_PROJECT_ID)

delete_labels()
