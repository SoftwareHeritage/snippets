from roadmap_xls_to_gitlab import *
from datetime import datetime

logging.basicConfig(
    filename=f"logs/import_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log",
    encoding="utf-8",
    level=logging.INFO,
    format="%(levelname)s:%(message)s",
)

milestones = load_milestones()
insert_milestones(milestones)

labels = load_labels()
insert_labels(labels)

issues = load_issues(milestones, labels)
insert_issues(issues)
