from roadmap_xls_to_gitlab import *


def delete_roadmap_milestones():
    response = requests.get(
        API_MILESTONE_ENDPOINT, {"per_page": 100}, headers=API_HEADERS
    )

    for milestone in response.json():
        if milestone["title"].startswith(ROADMAP_PREFIX):
            url = f"{API_MILESTONE_ENDPOINT}/{milestone['id']}"
            response = requests.delete(url, headers=API_HEADERS)
            print(response)
            print(f"deleted milestone: id={milestone['id']} - {milestone['title']}")


def delete_issues_by_label(label, project_id):
    response = requests.get(
        API_ISSUE_ENDPOINT,
        {"labels": label, "per_page": 100},
        headers=API_HEADERS,
    )
    print(response.headers["X-total"])
    total_pages = int(response.headers["X-total-pages"])

    for issue in response.json():
        issue_iid = int(issue["iid"])
        url = f"{ENDPOINTS_BASE_URL}/projects/{project_id}/issues/{issue_iid}"
        response = requests.delete(url, headers=API_HEADERS)
        print(f"deleted issue: issue_iid={issue_iid} - {issue['title']}")

    if total_pages > 1:
        delete_issues_by_label(label, project_id)
    else:
        return


def delete_labels():
    read_activity_labels()
    read_extra_labels()

    for label in labels:
        response = requests.delete(
            f"{API_LABEL_ENDPOINT}/{label.full_name()}", headers=API_HEADERS
        )
        print(response)
        print(f"deleted label: {label.name}")

    # labels = list()


# delete_roadmap_milestones()

# delete_issues_by_label("roadmap_import", META_PROJECT_ID)

# delete_labels()
