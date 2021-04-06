#!/bin/bash

DEST=swh-team@inria.fr
TEMPLATE_ID="6YKT5osoST-amJQ0MusH2Q"
URL="https://hedgedoc.softwareheritage.org"
DATE=`date +%G-W%V`

# login
http --session weeklybot --form -pb  "${URL}/login" \
	 email=${HEDGEDOC_LOGIN} password="${HEDGEDOC_PASSWORD}"

# retrieve the template
TEMPLATE=`http --session weeklybot -pb "${URL}/${TEMPLATE_ID}/download"`
TEMPLATE=$(echo "$TEMPLATE" | sed -e "s/\$DATE/$DATE/g")

RESP=`http --session weeklybot -ph POST "${URL}/new" content-type:text/markdown <<< "$TEMPLATE"`

LOCATION=`echo "$RESP" | grep "Location:" | cut -c 11-`

USERS=( `echo "$TEMPLATE" | grep '^## ' | cut -n -c 4-` )
SCRIBE=${USERS[$(( `date +%V | sed -e s/^0//` % ${#USERS[@]} ))]}


if [ -n "$LOCATION" ] ; then

#	/usr/lib/sendmail -t <<EOF
	cat <<EOF
From: Weekly planning bot <swh-team@inria.fr>
To: $DEST
Subject: [Weekly Planning] $DATE

Beep boop, I'm a bot.

Here is the pad for the next weekly planning meeting:

    $LOCATION

Please take a few minutes to pre-fill your part.

Remote attendees:

    https://meet.jit.si/EquivalentCoincidencesVentureOnlySwhTeam

Scribe: $SCRIBE

-- The Software Heritage weekly bot
EOF

fi
