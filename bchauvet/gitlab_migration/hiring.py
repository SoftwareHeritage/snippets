import gitlab

META_PROJECT_ID = 2
MANAGEMENT_GROUP_ID = 21

gl = gitlab.Gitlab.from_config("staging", ["./python-gitlab.cfg"])
gl.auth()
meta_project = gl.projects.get(META_PROJECT_ID)


# collect hiring issues
hiring_issues = meta_project.issues.list(get_all=True, labels="Hiring")

print(len(hiring_issues))

# create a hiring project
hiring_project = gl.projects.create(
    {"name": "Hiring", "namespace_id": MANAGEMENT_GROUP_ID}
)

# create labels for hiring project
label = hiring_project.labels.create({"name": "decision::hired", "color": "#00b140"})
label = hiring_project.labels.create({"name": "decision::rejected", "color": "#ff0000"})

label = hiring_project.labels.create(
    {"name": "position::backend-dev", "color": "#6699cc"}
)
label = hiring_project.labels.create({"name": "position::devops", "color": "#6699cc"})
label = hiring_project.labels.create({"name": "position::sysadmin", "color": "#6699cc"})
label = hiring_project.labels.create(
    {"name": "position::sysadm_intern", "color": "#e6e6fa"}
)

label = hiring_project.labels.create({"name": "status::1_sorted", "color": "#cdab8f"})
label = hiring_project.labels.create(
    {"name": "status::2_interviewLVL1", "color": "#adb08c"}
)
label = hiring_project.labels.create(
    {"name": "status::3_shortlist", "color": "#8db488"}
)
label = hiring_project.labels.create(
    {"name": "status::4_validated", "color": "#6eb985"}
)


# move hiring issues to the new hiring project
for issue in hiring_issues:

    issue.move(hiring_project.id)

    # affect position labels:
    if (issue.title.lower().startswith("[devops")):
        issue.labels = ['position::devops']
    elif (issue.title.lower().startswith("[backend") or issue.title.lower().startswith("[dev")):
        issue.labels = ['position::backend-dev']
    elif (issue.title.lower().startswith("[sysadm")):
        issue.labels = ['position::sysadmin']

    issue.save()    

