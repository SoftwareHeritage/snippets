#!/bin/bash

GITHUB_API_TOKEN_FILE=$HOME/.config/swh/github-token
FORGE_API_TOKEN_FILE=$HOME/.config/swh/forge-token

[ ! -f "$GITHUB_API_TOKEN_FILE" ] && cat << EOF && exit 1

Install one personal github token in $GITHUB_API_TOKEN_FILE with scope
public_repo (https://github.com/settings/tokens).

You must be associated to https://github.com/softwareheritage
organization.  Once the installation is done, you can trigger this
script again.
EOF

[ ! -f "$FORGE_API_TOKEN_FILE" ] && cat << EOF && exit 1
Install the forge's token in $FORGE_API_TOKEN_FILE
(https://forge.softwareheritage.org/settings/user/<your-user>/page/apitokens/).

Once the installation is done, you can trigger this script again.
EOF

[[ ( $# -lt 4 ) ]] && cat << EOF && exit 1
Use: $0 <FORGE_REPO_CALLSIGN> <FORGE_REPO_NAME> <FORGE_REPO_URL> <FORGE_REPO_DESCRIPTION>
FORGE_REPO_CALLSIGN      Repository's callsign (we will deduce the phid from it)
FORGE_REPO_NAME          Repository's name (we will use it for github name)
FORGE_REPO_URL           Repository's forge url
FORGE_REPO_DESCRIPTION   Repository's forge description
CREDENTIAL_KEY_ID        Credential key id to use (default to 2 which is K2)

Example:
sync-mirror-to-github.sh swh-indexer https://forge.softwareheritage.org/source/swh-indexer.git "Software Heritage content (as in "blob") indexers" 3

EOF

FORGE_REPO_CALLSIGN=$1
FORGE_REPO_NAME=$2
FORGE_REPO_URL=$3
FORGE_REPO_DESCRIPTION=$4
CREDENTIAL_KEY_ID=${5-"2"}  # default to K2

#### Retrieve phabricator information

FORGE_API_TOKEN=$(cat $FORGE_API_TOKEN_FILE)

DATA_REPO=$(curl -d api.token=$FORGE_API_TOKEN \
                 -d "constraints[callsigns][0]=$FORGE_REPO_CALLSIGN" \
                 https://forge.softwareheritage.org/api/diffusion.repository.search 2>/dev/null)

# Retrieve the repository's phid
FORGE_REPO_PHID=$(echo $DATA_REPO | jq '.result.data[].phid' | sed -e 's/"//gi')

#### Create the repository in github

GITHUB_USER_TOKEN=$(cat $GITHUB_API_TOKEN_FILE)

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
curl -H "Authorization: token $GITHUB_USER_TOKEN" \
     -X POST \
     -d @${TMP_FILE} \
     https://api.github.com/orgs/SoftwareHeritage/repos

# clean up
[ -f $TMP_FILE ] && rm $TMP_FILE

#### phabricator

GITHUB_REPO_URI=git@github.com:SoftwareHeritage/$FORGE_REPO_NAME.git

KEY_PHID=$(curl -d "api.token=$FORGE_API_TOKEN" \
                -d "ids[0]=$CREDENTIAL_KEY_ID" \
                https://forge.softwareheritage.org/api/passphrase.query \
               | jq '.result.data[].phid' | sed -e 's/"//gi')

# Create the uri to associate with the repository with the following options:
# - uri: github uri
# - i/o: mirror
# - display: hidden
# - credentials: set the credential to the wanted credential (id
# - passed as input in this script)
curl https://forge.softwareheritage.org/api/diffusion.uri.edit \
                -d api.token=$FORGE_API_TOKEN \
                -d transactions[0][type]=repository \
                -d transactions[0][value]=$FORGE_REPO_PHID \
                -d transactions[1][type]=uri \
                -d transactions[1][value]=$GITHUB_REPO_URI \
                -d transactions[2][type]=io \
                -d transactions[2][value]=mirror \
                -d transactions[3][type]=display \
                -d transactions[3][value]=never \
                -d transactions[4][type]=credential \
                -d transactions[4][value]=$KEY_PHID \
                -d transactions[5][type]=disable \
                -d transactions[5][value]=false | jq

cat <<EOF
    Repository $FORGE_REPO_URL mirrored at $GITHUB_REPO_URI.
EOF
