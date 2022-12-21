import xlrd
import json
import requests
import sys

if len(sys.argv) == 1:
    print("gitlab access-token required as argument")
    exit()

# TODO : log results
# TODO : use python-gitlab library

labels = list()
milestones = list()
issues = list()


class Milestone:
    def __init__(self, title, id=0):
        self.title = title
        self.id = id

    def __str__(self) -> str:
        return f"milestone #{self.id} - {self.title}"


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
        return f"issue #{self.id} - project #{self.project_id} - milestone #{self.milestone_id} - {self.title} - labels : {str_labels}"


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

# api parameters:
API_TOKEN = sys.argv[1]
API_HEADERS = {"PRIVATE-TOKEN": API_TOKEN}
ENDPOINTS_BASE_URL = "https://gitlab-staging.swh.network/api/v4"
API_LABEL_ENDPOINT = f"{ENDPOINTS_BASE_URL}/groups/{SWH_GROUP_ID}/labels"
API_MILESTONE_ENDPOINT = f"{ENDPOINTS_BASE_URL}/groups/{SWH_GROUP_ID}/milestones"
API_ISSUE_ENDPOINT = f"{ENDPOINTS_BASE_URL}/projects/{META_PROJECT_ID}/issues"

# LABELS
def read_activity_labels():
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


def read_extra_labels():
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


def insert_labels():
    for label in labels:
        body = {
            "name": label.full_name(),
            "color": label.color,
        }
        response = requests.post(
            API_LABEL_ENDPOINT, json=body, headers=API_HEADERS
        ).json()
        label.id = response["id"]
        print(f"inserted label #{label.name}")


def get_label_by_name(name):
    for label in labels:
        if label.name == name.strip():
            return label


# MILESTONES
def read_milestones():
    for row in range(1, sheet_data.nrows):
        milestone_title = ROADMAP_PREFIX + sheet_data.cell(row, 1).value
        found = False
        for m in milestones:
            if m.title == milestone_title:
                found = True
                break
        if not found:
            milestone = Milestone(milestone_title)
            milestones.append(milestone)


def insert_milestones():
    for milestone in milestones:
        body = {"title": milestone.title}
        response = requests.post(API_MILESTONE_ENDPOINT, json=body, headers=API_HEADERS)
        milestone.id = response.json()["id"]
        print(f"inserted milestone #{milestone.id} - {milestone.title}")


def get_milestone_by_title(title):
    for milestone in milestones:
        if milestone.title == title:
            return milestone


# ISSUES
def read_issues():
    for row in range(1, sheet_data.nrows):
        issue_title = sheet_data.cell(row, 2).value
        if issue_title != "":
            milestone_title = sheet_data.cell(row, 1).value
            milestone = get_milestone_by_title(ROADMAP_PREFIX + milestone_title)
            issue = Issue(issue_title, milestone.id, META_PROJECT_ID)
            activity_label_name = sheet_data.cell(row, 3).value
            activity_label = get_label_by_name(activity_label_name)
            issue.labels.append(activity_label.full_name())
            # extra labels :
            extra_labels = sheet_data.cell(row, 4).value
            if extra_labels != "":
                for xl in extra_labels.split(","):
                    issue.labels.append(get_label_by_name(xl).full_name())
            issues.append(issue)


def insert_issues():
    for issue in issues:
        body = {
            "title": issue.title,
            "milestone_id": issue.milestone_id,
            "labels": ",".join(issue.labels),
        }
        response = requests.post(
            API_ISSUE_ENDPOINT, json=body, headers=API_HEADERS
        ).json()
        issue.id = response["id"]
        print(
            f"inserted issue #{issue.id} : {issue.title} - milestone: {issue.milestone_id}"
        )
