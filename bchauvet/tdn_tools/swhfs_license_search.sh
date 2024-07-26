# usage: ./swhfs_license_search.sh >licenses_tcyrus.csv 2>/dev/null

# swh-fs directory path:
SWHFS_HOME=~/swhfs

python3 search_licences.py tcyrus > origins.csv

origins_file=origins.csv

echo "origin;file name;license"

while read origin
do
    if [ ! -z "${origin}" ]
    then
        (IFS="+"; read _z; echo -en ${_z//%/\\x}"") <<< "${origin};" 
        cd $SWHFS_HOME/origin/$origin
        root_path=`ls . | tail -1`/snapshot/HEAD/root
        file=$(ls $root_path | grep -iw -m 1 -e "license" -e "copying" -e "readme")
        if [ ! -z "${file}" ]
        then 
            echo -n "${file};"
            license_path="${root_path}/${file}"
            if grep -iwq -e "GNU General Public License" $license_path 
            then
                echo "GPL"
            elif grep -iwq -e "MIT" $license_path 
            then
                echo "MIT"  
            elif grep -iwq -e "Copyright" $license_path 
            then
                echo "Copyright"  
            else
                echo "??"
            fi
        else 
            echo "none"
        fi
    fi
done <  "$origins_file"