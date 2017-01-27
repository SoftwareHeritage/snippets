#!/bin/bash

GHB_API_TOKEN_FILE=$HOME/.config/swh/github-token
FORGE_API_TOKEN_FILE=$HOME/.config/swh/forge-token

[ ! -f "$GHB_API_TOKEN_FILE" ] && cat << EOF && exit 1
Install the github api's token in $GHB_API_TOKEN_FILE.
It must have the scope public_repo.
You must be associated to https://github.com/softwareheritage organization.
Once the installation is done, you can trigger this script again.
EOF

[ ! -f "$FORGE_API_TOKEN_FILE" ] && cat << EOF && exit 1
Install the github api's token in $FORGE_API_TOKEN_FILE.
Once the installation is done, you can trigger this script again.
EOF

[[ ( $# -lt 4 ) ]] && cat << EOF && exit 1
Use: $0 <FORGE_REPO_CALLSIGN> <FORGE_REPO_NAME> <FORGE_REPO_URL> <FORGE_REPO_DESCRIPTION>
FORGE_REPO_CALLSIGN      Repository's callsign (we will deduce the phid from it)
FORGE_REPO_NAME          Repository's name (we will use it for github name)
FORGE_REPO_URL           Repository's forge url
FORGE_REPO_DESCRIPTION   Repository's forge description

Example:
sync-mirror-to-github.sh swh-indexer https://forge.softwareheritage.org/source/swh-indexer.git "Software Heritage content (as in "blob") indexers"

EOF

FORGE_REPO_CALLSIGN=$1
FORGE_REPO_NAME=$2
FORGE_REPO_URL=$3
FORGE_REPO_DESCRIPTION=$4
TRYOUT=$5

#### Retrieve phabricator information

FORGE_API_TOKEN=$(cat $FORGE_API_TOKEN_FILE)

# Retrieve the repository's phid
FORGE_REPO_PHID=$(curl -d api.token=$FORGE_API_TOKEN \
                       -d "constraints[callsigns][0]=$FORGE_REPO_CALLSIGN" \
                       https://forge.softwareheritage.org/api/diffusion.repository.search 2>/dev/null \
                       jq '.result.data[].phid')

echo $FORGE_REPO_PHID

#### Create the repository in github

GHB_USER_TOKEN=$(cat $GHB_API_TOKEN_FILE)

if [ ! -z "$TRYOUT"]; then

    TMP_FILE=$(mktemp)
    cat <<EOF > $TMP_FILE
{
  "name": "$FORGE_REPO_NAME",
  "description": "$FORGE_REPO_DESCRIPTION",
  "homepage": "$FORGE_REPO_URL",
  "private": false,
  "has_issues": false,
  "has_wiki": false,
  "has_downloads": true
}
EOF

    # Create the repository in github
    curl -H "Authorization: token $GHB_USER_TOKEN" \
         -X POST \
         -d @${TMP_FILE} \
         https://api.github.com/v3/orgs/SoftwareHeritage/repos

    # clean up
    [ -f $TMP_FILE ] && rm $TMP_FILE

fi

#### phabricator

GITHUB_REPOSITORY_URI=git@github.com:SoftwareHeritage/$FORGE_REPO_NAME.git

K2_PHID=$(curl -d "api.token=$FORGE_API_TOKEN" \
               -d 'ids[0]=2' \
               https://forge.softwareheritage.org/api/passphrase.query \
               2>/dev/null \
              | jq '.result.data[].phid')

echo $K2_PHID


if [ ! -z "$TRYOUT" ]; then
    curl https://forge.softwareheritage.org/api/diffusion.uri.edit \
         -d api.token=$FORGE_API_TOKEN \
         -d transactions[0][type]=repository \
         -d transactions[0][value]=$FORGE_REPO_PHID \
         -d transactions[1][type]=uri \
         -d transactions[1][value]=$GITHUB_REPOSITORY_URI \
         -d transactions[2][type]=io \
         -d transactions[2][value]=mirror \
         -d transactions[3][type]=display \
         -d transactions[3][value]=never \
         -d transactions[4][type]=credential \
         -d transactions[4][value]=$K2_PHID
fi
