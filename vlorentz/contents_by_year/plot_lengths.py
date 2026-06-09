import csv
import datetime
import matplotlib.pyplot as plt
from statistics import mean

GRAPH_NAME = "2026-03-02"
MIN_YEAR = 1970
MAX_YEAR = 2026

rows = csv.reader(open(f"./{GRAPH_NAME}_content_lengths.csv"))
header = next(rows)
assert header == ["year", "avg(c.length)", "median(c.length)"], header

years = []
averages = []
medians = []
for year, average, median in rows:
    year = int(year)
    average = float(average)
    median = float(median)
    if year <= 1970:
        continue
    if MIN_YEAR <= year <= MAX_YEAR:
        years.append(year)
        averages.append(average)
        medians.append(median)


fig, (ax1, ax2) = plt.subplots(1, 2)
fig.tight_layout(pad=2)
fig.suptitle("Average content length, according to commit date")

ax1.set_ylabel("average length")
ax1.set_xlabel("year")
ax1.bar(years, averages)

ax2.set_ylabel("median length")
ax2.set_xlabel("year")
ax2.bar(years, medians)

fig.savefig(f"{GRAPH_NAME}_content_lengths.svg")
