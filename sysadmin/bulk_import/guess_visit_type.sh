#!/bin/bash

#set -x

LIST=${1}
OK="visit_type.csv"
INCORRECT="incorrect.csv"
UNKNOWN="unknown.csv"
TO_REDIRECT="to_redirect.csv"

ORIGIN_TO_CHECK=$(wc -l $LIST | awk '{print $1}')

POS=1

check_origin() {
  origin=$1

  if [[ "$origin"  == *"://github.com/"* ]] || [[ "$origin"  == *"://bitbucket.org/"* ]] || \
     [[ "$origin" == *"://code.google.com/"* ]]; then
    if [[ $(echo $origin | tr '/' ' ' | wc -w) == 4 ]]; then
      return 0
    else
      return 1
    fi
  else
    return 0
  fi

}

# shellcheck disable=SC1073
while read origin; do

  echo -n "Checking ${POS}/${ORIGIN_TO_CHECK} $origin : "

  if check_origin $origin; then
    if [[ "$origin" == *"://github.com/"* ]]; then
      # github is git, the simplest case
      type="git"
    elif [[ "$origin" == *"://bitbucket.org/"* ]]; then
      # bitbucket only support git now, but we have the old hg repositories
      # already ingested
      # remove trailing /
      origin=$(echo $origin | sed 's|/$||')
      type=$(psql -X -q -t service=swh-scheduler -c "select visit_type from origin_visit_stats where url='$origin'" | sed 's/\s\+|\s\+/;/')
      if [ -z "$type" ]; then
        type="git"
      fi
    elif [[ "$origin" == *"://code.google.com/"* ]]; then
      type="to_redirect"
    elif [[ "$origin" == *"://sourceforge.net/"* ]]; then
      project="$(echo $origin | cut -f5 -d'/')"
      # echo $project
      curl -f -s https://sourceforge.net/rest/p/${project} > /tmp/full.json
      result=$?

      if [ $result -gt 0 ]; then
        type="unknown"
        echo -n "(error $result) "
        echo "$origin;$result" >> sourceforge_not_found.cvs
      else

        if cat /tmp/full.json | jq -r '.tools[] | select(.mount_point == "code")' > /tmp/code.json; then

          # cat /tmp/code.json
          type=$(cat /tmp/code.json | jq -r '.name')

          if [ "$type" == "cvs" ]; then
            clone_url="rsync://a.cvs.sourceforge.net/cvsroot/$project"
            # also keep track the redirection
            echo "${origin};${clone_url}" >> "$TO_REDIRECT"
            origin="${clone_url}"
          elif [ "$type" == "svn" ]; then
            clone_url="https://svn.code.sf.net/p/${project}/code"
            # also keep track the redirection
            echo "${origin};${clone_url}" >> "$TO_REDIRECT"
            origin="${clone_url}"
          elif [ "$type" == "hg" ]; then
            clone_url="http://hg.code.sf.net/p/${project}/code"
            # also keep track the redirection
            echo "${origin};${clone_url}" >> "$TO_REDIRECT"
            origin="${clone_url}"
          elif [ "$type" == "git" ]; then
            clone_url="https://git.code.sf.net/p/${project}/code"
            # also keep track the redirection
            echo "${origin};${clone_url}" >> "$TO_REDIRECT"
            origin="${clone_url}"
          else
            # echo -n "|$? $type|"
            echo "$origin" >> sourceforge_nocode.cvs
            type="unknown"
          fi

        fi
      fi
      rm -f /tmp/code.json /tmp/full.json

    else
      type="unknown"
    fi

    if [ "$type" == "unknown" ]; then
      echo "${origin}" >> "$UNKNOWN"
      echo "unknown"
    elif [ "$type" == "to_redirect" ]; then
      echo "${origin}" >> "$TO_REDIRECT"
      echo "to_redirect"
    else
      echo "${origin};${type}" >> "$OK"
      echo "$type"
    fi

  else
    echo "incorrect"
    echo "${origin}" >> "$INCORRECT"
  fi

  POS=$(( POS + 1 ))

done < "${LIST}"

