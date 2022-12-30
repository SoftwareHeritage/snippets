import xlrd
import sys
import gitlab
import logging


class Milestone:
    def __init__(self, title, prefix, id=0):
        self.title = title
        self.prefix = prefix
        self.id = id

    def __str__(self) -> str:
        return f"milestone #{self.id} - {self.full_title()}"

    def full_title(self) -> str:
        return self.prefix + self.title


class Label:
    def __init__(self, name, color="#8fbc8f", prefix="", id=0):
        self.prefix = prefix
        self.name = name
        self.id = id
        self.color = color

    def __str__(self) -> str:
        return f"label #{self.id} - {self.full_name()} - {self.color}"

    def full_name(self):
        if self.prefix != "":
            return f"{self.prefix}::{self.name}"
        else:
            return self.name


class Issue:
    def __init__(self, title, milestone_id, project_id, id=0):
        self.title = title
        self.milestone_id = milestone_id
        self.project_id = project_id
        self.labels = list()
        self.id = id

    def __str__(self) -> str:
        str_labels = ",".join(self.labels)
        return f"issue #{self.id} - project #{self.project_id} - milestone #{self.milestone_id} - {self.title} - labels : {str_labels}"


# spreadsheet parameters:


def get_param_from_spreadsheet(name):
    for row in range(0, 100):
        if sheet_params.cell(row, 0).value == name:
            return sheet_params.cell(row, 1).value


workbook = xlrd.open_workbook("2023_Roadmap.xls")
sheet_data = workbook.sheet_by_name("data")
sheet_params = workbook.sheet_by_name("params")

SWH_GROUP_ID = int(get_param_from_spreadsheet("swh_group_id"))
META_PROJECT_ID = int(get_param_from_spreadsheet("meta_project_id"))
ACTIVITY_LABELS_PREFIX = get_param_from_spreadsheet("activity_labels_prefix")
ACTIVITY_LABELS_COLOR = get_param_from_spreadsheet("activity_labels_color")
EXTRA_LABELS_COLOR = get_param_from_spreadsheet("extra_labels_color")
ROADMAP_PREFIX = get_param_from_spreadsheet("roadmap_prefix")

gl = gitlab.Gitlab.from_config("staging", ["./python-gitlab.cfg"])
gl.auth()
swh_group = gl.groups.get(SWH_GROUP_ID)
meta_project = gl.projects.get(META_PROJECT_ID)

# LABELS


def load_labels():
    labels = list()
    _read_activity_labels(labels)
    _read_extra_labels(labels)
    # _read_goal_labels(labels)
    return labels


def _read_activity_labels(labels):
    for row in range(1, sheet_data.nrows):
        label_name = sheet_data.cell(row, 3).value
        if label_name != "":
            found = False
            for lbl in labels:
                if lbl.name == label_name:
                    found = True
                    break
            if not found:
                label = Label(label_name, ACTIVITY_LABELS_COLOR, ACTIVITY_LABELS_PREFIX)
                labels.append(label)


# def _read_goal_labels(labels):
#     for row in range(1, sheet_data.nrows):
#         label_name = sheet_data.cell(row, 0).value.lower().strip()
#         if label_name != "":
#             found = False
#             for lbl in labels:
#                 if lbl.name == label_name:
#                     found = True
#                     break
#             if not found:
#                 label = Label(label_name, ACTIVITY_LABELS_COLOR, "goal")
#                 labels.append(label)


def _read_extra_labels(labels):
    for row in range(1, sheet_data.nrows):

        content = sheet_data.cell(row, 4).value
        if content != "":
            for label_name in content.split(","):
                found = False
                for lbl in labels:
                    if lbl.name.strip() == label_name.strip():
                        found = True
                        break
                if not found:
                    label = Label(label_name.strip(), EXTRA_LABELS_COLOR)
                    labels.append(label)


def insert_labels(labels):
    for label in labels:
        lbl = swh_group.labels.create(
            {
                "name": label.full_name(),
                "color": label.color,
            }
        )
        label.id = lbl.id
        logging.info(f"inserted label: {label.full_name()}")


def get_label_by_name(name, labels):
    for label in labels:
        if label.name == name.strip():
            return label


# MILESTONES
def load_milestones():
    milestones = list()
    for row in range(1, sheet_data.nrows):
        goal_name = sheet_data.cell(row, 0).value.lower().strip()
        prefix = ROADMAP_PREFIX.replace("$GOAL", goal_name)
        milestone_title = sheet_data.cell(row, 1).value
        found = False
        for m in milestones:
            if m.title == milestone_title:
                found = True
                break
        if not found:
            milestone = Milestone(milestone_title, prefix)
            milestones.append(milestone)

    return milestones


def insert_milestones(milestones):
    for milestone in milestones:
        mlst = swh_group.milestones.create({"title": milestone.full_title()})
        milestone.id = mlst.id
        logging.info(f"inserted milestone #{milestone.id} - {milestone.full_title()}")


def get_milestone_by_title(title, milestones):
    for milestone in milestones:
        if milestone.title == title:
            return milestone


# ISSUES
def load_issues(milestones, labels):
    issues = list()
    for row in range(1, sheet_data.nrows):
        issue_title = sheet_data.cell(row, 2).value
        if issue_title != "":
            milestone_title = sheet_data.cell(row, 1).value
            milestone = get_milestone_by_title(milestone_title, milestones)
            issue = Issue(issue_title, milestone.id, META_PROJECT_ID)

            # goal label :
            # goal_label_name = sheet_data.cell(row, 0).value.lower()
            # goal_label = get_label_by_name(goal_label_name, labels)
            # issue.labels.append(goal_label.full_name())

            # activity label :
            activity_label_name = sheet_data.cell(row, 3).value
            activity_label = get_label_by_name(activity_label_name, labels)
            issue.labels.append(activity_label.full_name())

            # extra labels :
            extra_labels = sheet_data.cell(row, 4).value
            if extra_labels != "":
                for xl in extra_labels.split(","):
                    issue.labels.append(get_label_by_name(xl, labels).full_name())

            issues.append(issue)
    return issues


def insert_issues(issues):
    for issue in issues:
        iss = meta_project.issues.create(
            {
                "title": issue.title,
                "milestone_id": issue.milestone_id,
                "labels": ",".join(issue.labels),
            }
        )
        issue.id = iss.id
        logging.info(
            f"inserted issue #{iss.iid} : {issue.title} - milestone: {issue.milestone_id}"
        )
