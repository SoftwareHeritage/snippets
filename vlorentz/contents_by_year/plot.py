import csv
import datetime
import matplotlib.pyplot as plt
from statistics import mean

GRAPH_NAME = "2026-03-02"
MIN_YEAR = 1970
MAX_YEAR = 2026

rows = csv.reader(open(f"./{GRAPH_NAME}.csv"))
header = next(rows)
assert header == ["year", "count(*)"], header

years = []
total_contents = []
new_contents = []
total = 0
for year, count in rows:
    year = int(year)
    count = int(count)
    total += count
    if MIN_YEAR <= year <= MAX_YEAR:
        years.append(year)
        new_contents.append(count)
        total_contents.append(total)


def regression(ax, *, base_year, base_count, yearly_increase_rate):
    regression_year = MAX_YEAR  # regression line up to current year
    min_count = 10 ** (base_count - (base_year - base_year) ** (1-yearly_increase_rate))
    max_count = 10 ** (
        base_count + (regression_year - base_year) ** yearly_increase_rate
    )
    ax.plot(
        [base_year, regression_year],
        [min_count, max_count],
        color="red",
        linewidth=1,  # thinner
        label=f"+{int(yearly_increase_rate*100)}%/year"
    )
    ax.legend()


fig, ((ax1, ax3), (ax2, ax4)) = plt.subplots(2, 2)
fig.tight_layout(pad=2)
fig.suptitle("Contents creation date, according to commit date")

ax1.set_ylabel("total contents")
ax1.set_xlabel("year")
ax1.bar(years, total_contents)

ax2.set_yscale("log")
ax2.set_ylabel("total contents (log scale)")
ax2.set_xlabel("year")
ax2.bar(years, total_contents)

# hand-picked coefficients
regression(
    ax2,
    base_year=2000,
    base_count=7.3,  # start with 10**7.3 in 1998
    yearly_increase_rate=0.40,  # +40% every year
)

ax3.set_ylabel("new contents per year")
ax3.set_xlabel("year")
ax3.bar(years, new_contents)

ax4.set_yscale("log")
ax4.set_ylabel("new contents per year (log scale)")
ax4.set_xlabel("year")
ax4.bar(years, new_contents)

# hand-picked coefficients
regression(
    ax4,
    base_year=2000,
    base_count=6.7,  # start with 10**7.3 in 1998
    yearly_increase_rate=0.40,  # +40% every year
)

fig.savefig(f"{GRAPH_NAME}.svg")
