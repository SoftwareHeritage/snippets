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
    if year <= 1970:
        continue
    total += count
    if MIN_YEAR <= year <= MAX_YEAR:
        years.append(year)
        new_contents.append(count)
        total_contents.append(total)

projection_base_year = 2022
projection_total_contents = [total_contents[projection_base_year - 1970 - 1]]
projection_new_contents = [int(new_contents[projection_base_year - 1970 - 1])]
projection_years = list(range(projection_base_year, 2036))
for _ in projection_years[1:]:
    # 1.38: hand-picked
    projection_total_contents.append(int(projection_total_contents[-1] * 1.38))
    projection_new_contents.append(int(projection_new_contents[-1] * 1.38))

projection_years_plot = projection_years[:9]
projection_total_contents_plot = projection_total_contents[:9]
projection_new_contents_plot = projection_new_contents[:9]


def print_table():
    YEARS = [2026, 2027, 2028, 2029, 2030, 2035]
    AVG_CONTENT = 100 * 1024
    PiB = 1024**5
    indices = [y - 2022 for y in YEARS]

    def _format_list(lst):
        def _fmt_one(x):
            if isinstance(x, float):
                return f"{x:.01f}"
            return str(x)

        return "| " + " | ".join(map(_fmt_one, lst)) + " |"

    print("| Year " + _format_list(YEARS))
    print(_format_list(["--------"] * (len(YEARS) + 1)))

    proj_total_contents_G = [projection_total_contents[i] / 1e9 for i in indices]
    print("| # contents total (×10⁹) " + _format_list(proj_total_contents_G))

    proj_new_contents_G = [projection_new_contents[i] / 1e9 for i in indices]
    print("| # contents added (×10⁹) " + _format_list(proj_new_contents_G))

    proj_total_weight_PiB = [
        projection_total_contents[i] * AVG_CONTENT / PiB for i in indices
    ]
    print("| Total weight (PiB) " + _format_list(proj_total_weight_PiB))

    proj_added_weight_PiB = [
        projection_new_contents[i] * AVG_CONTENT / PiB for i in indices
    ]
    print("| Weight added (PiB) " + _format_list(proj_added_weight_PiB))

    # Erasure-coding: *7/5 ; max capacity at 80%: /.8
    proj_ceph_weight_PiB = [weight * (7 / 5) / 0.8 for weight in proj_total_weight_PiB]
    print("| Total Ceph capacity needed (PiB) " + _format_list(proj_ceph_weight_PiB))

    proj_ceph_added_weight_PiB = [
        weight * (7 / 5) / 0.8 for weight in proj_added_weight_PiB
    ]
    print(
        "| Ceph capacity increase needed (PiB) "
        + _format_list(proj_ceph_added_weight_PiB)
    )

    proj_ingestion_rate_cps = [
        projection_new_contents[i] / 3600 / 24 / 365 for i in indices
    ]
    print("| Min ingestion rate (content/s) " + _format_list(proj_ingestion_rate_cps))

    proj_ingestion_rate_bps = [
        rate * AVG_CONTENT * 8 for rate in proj_ingestion_rate_cps
    ]  # Note: bits, not bytes
    proj_net_throughput_inbound_Gbps = [rate / 1e9 for rate in proj_ingestion_rate_bps]
    # Note: Gbps = 1e9 bps, not 1024**3 bps
    print(
        "| Ingestion network inbound traffic (Gbps) "
        + _format_list(proj_net_throughput_inbound_Gbps)
    )
    proj_net_throughput_outbound_Gbps = [
        2 * rate / 1e9 for rate in proj_ingestion_rate_bps
    ]
    print(
        "| Ingestion network outbound traffic (Azure + S3, Gbps) "
        + _format_list(proj_net_throughput_outbound_Gbps)
    )


def regression(ax, *, min_year=None, base_year, base_count, yearly_increase_rate):
    min_year = min_year or base_year
    regression_year = MAX_YEAR  # regression line up to current year
    min_count = 10 ** (base_count + (min_year - base_year) * yearly_increase_rate)
    max_count = 10 ** (
        base_count + (regression_year - base_year) * yearly_increase_rate
    )
    ax.plot(
        [min_year, regression_year],
        [min_count, max_count],
        color="red",
        linewidth=1,  # thinner
        label=f"+{int((10 ** (yearly_increase_rate) - 1) * 100)}%/year",
    )
    ax.legend()


fig, ((ax1, ax3), (ax2, ax4)) = plt.subplots(2, 2)
fig.tight_layout(pad=2)
fig.suptitle("Contents creation date, according to commit date")

ax1.set_ylabel("total contents")
ax1.set_xlabel("year")
ax1.bar(years, total_contents)
ax1.bar(projection_years_plot, projection_total_contents_plot, color="#ffa40688")

ax2.set_yscale("log")
ax2.set_ylabel("total contents (log scale)")
ax2.set_xlabel("year")
ax2.bar(years, total_contents)
ax2.bar(projection_years_plot, projection_total_contents_plot, color="#ffa40688")

# hand-picked coefficients
regression(
    ax2,
    min_year=1980,  # extend the regression in the past. not very useful but we have the room for it
    base_year=2000,
    base_count=7.3,  # start with 10**7.3 in 2000
    yearly_increase_rate=0.14,
)

ax3.set_ylabel("new contents per year")
ax3.set_xlabel("year")
ax3.bar(years, new_contents)
ax3.bar(projection_years_plot, projection_new_contents_plot, color="#ffa40688")

ax4.set_yscale("log")
ax4.set_ylabel("new contents per year (log scale)")
ax4.set_xlabel("year")
ax4.bar(years, new_contents)
ax4.bar(projection_years_plot, projection_new_contents_plot, color="#ffa40688")

# hand-picked coefficients
regression(
    ax4,
    min_year=1985,  # extend the regression in the past. not very useful but we have the room for it
    base_year=2000,
    base_count=6.7,  # start with 10**6.7 in 2000
    yearly_increase_rate=0.14,
)

fig.savefig(f"{GRAPH_NAME}.svg")

print_table()
