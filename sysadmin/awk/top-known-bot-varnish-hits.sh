#!/usr/bin/env bash
# vim: ai ts=4 sts=4 sw=4

set -eu
set -o pipefail

typeset -r HLINE=$(printf -- '-%0.s' {1..29})
typeset -r VARNISHLOG=/var/log/varnish/varnishncsa.log
#typeset -r VARNISHLOG=/root/vlogstest.log
typeset -r SINCE=$(awk '{print "📆 since", substr($4,2)}' <(head -1 "$VARNISHLOG".1))
#typeset -r SINCE=$(awk '{print "📆 since", substr($4,2)}' <(head -1 "$VARNISHLOG"))
typeset -r BOTS="Svix-Webhooks
	ClaudeBot
	ChatGPT-User
	Bytespider
	facebookexternalhit
	Amazonbot
	Googlebot
	AhrefsBot
	GoogleOther
	DataForSeoBot
	ImagesiftBot
	bingbot
	PetalBot
	SemrushBot
	DuckDuckGo
	Applebot
	YandexBot
	YandexRenderResourcesBot
	Baiduspider"

# a little awk and ♥️  in this cruel world
awk -v bots="$BOTS" \
	-v hline="$HLINE" \
	-v since="$SINCE" '
BEGIN{
	format="%-29s %s\n"
	printf format, hline, hline
	format="%-28s %s\n"
	split(bots,bot," ")
	for (i in bot)
		counters[bot[i]]=0
	printf format, "🌐 Web Crawlers", since
	format="%-29s %s\n"
	printf format, hline, hline
	format="%-29s %-14s %s\n"
	printf format, "", "Hits", "Ratio"
	printf format, "", hline, ""
}
{
	for (i in counters)
		if($0 ~ i)
			counters[i]+=1
}
END{
	# sort by bots name
	#PROCINFO["sorted_in"] = "@ind_str_asc"
	# sort by hits
	PROCINFO["sorted_in"] = "@val_num_desc"
	"date" | getline date
	close("date")
	for (i in counters)
		printf format, i, counters[i], counters[i]/NR*100
	printf "\nReported on %s.\n", date
}' "$VARNISHLOG"{,.1}
#}' "$VARNISHLOG"

exit 0
