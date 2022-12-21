from roadmap_xls_to_gitlab import *

read_milestones()
# insert_milestones()

read_activity_labels()
read_extra_labels()
# insert_labels()

read_issues()
# insert_issues()


print()
print("LABELS :")
print("--------")
for label in labels:
    print(label)
print()

print("MILESTONES :")
print("------------")
for milestone in milestones:
    print(milestone)
print()

print("ISSUES :")
print("--------")
for issue in issues:
    print(issue)
