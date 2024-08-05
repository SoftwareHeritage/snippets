#!/usr/bin/awk -f
# vim: ai ts=4 sts=4 sw=4

BEGIN{
format="%-45s %s\n"
group=ENVIRON["GROUP_ID"]
}
{
if ($1 == group){counters[$2]+=$6}
}
END{
"date" | getline date
close("date")
printf "## %s\n", date
printf "## GROUP_ID: %s\n", group
printf format, "## TOPICS", "## LAG"
# sort by topics name
#PROCINFO["sorted_in"] = "@ind_str_asc"
# sort by lag
PROCINFO["sorted_in"] = "@val_num_desc"
for (i in counters)
	printf  format, i, counters[i]
}
