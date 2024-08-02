import configparser
from urllib.parse import quote
from swh.web.client.client import WebAPIClient
import re
import sys
from pathlib import Path
from scancode.api import get_licenses


license_file_names = [
"li[cs]en[cs]e(s?)",
"legal",
"copy(left|right|ing)",
"unlicense",
"[al]?gpl([-_ v]?)(\d\.?\d?)?", # AGPLv3
"bsd(l?)", # BSDL
"mit(x?)", # MITX
"apache",
"artistic", # Artistic.txt
"copying(v?)(\d?)", # COPYING3, COPYINGv3
"disclaimer",
"eupl",
"gfdl",
"[cm]pl",
"cc0",
"al([-_ v]?)(\d\.?\d)?", # AL2.0
"about",
"notice",
"readme",
"guidelines",
]

license_file_re = re.compile(rf"^(|.*[-_. ])({'|'.join(license_file_names)})(|[-_. ].*)$", re.IGNORECASE)

config = configparser.ConfigParser()
config.read('config.ini')
shwfs_home = Path.home() / config.get('SWH', 'swhfs_home')

class OriginInfo:
    def __init__(self, url, visit, licenses):
        self.url = url
        self.visit = visit
        self.licenses = licenses
    
    def to_csv_line(self):
        url = self.url
        visit = self.visit
        licences = ""
        for license in self.licenses:
            licences = licences + f"{license.license}({license.filename}) - "
        return (f"{url};{visit};{licences}\n")


class LicenseInfo:
    def __init__(self, filename, license):
        self.filename = filename
        self.license = license

# Returns the list of visited origin urls matching the swh api search query
def get_origins(query):
    origins = []
    token = config.get('SWH', 'auth_token')
    cli = WebAPIClient(bearer_token=token)
    resp = cli.origin_search(query, limit=1000)
    for origin_entry in resp:
        origins.append(origin_entry['url'])
    return origins

# Search for files in 
def process_origin(origin):
    result = OriginInfo(origin, "True", [])
    encoded_origin = quote(origin, safe='')   
    license_files = []
    try:
        root_path = get_root_path(encoded_origin)
        license_files = get_license_files(root_path)
        for file in license_files:
            license_info = get_license_info(root_path,file)
            result.licenses.append(license_info)
    except Exception as e:
        #print(e)
        result.visit = "False"
    return result

# Returns the root directory path for the HEAD revision in the most recent snapshot 
def get_root_path(origin):
    path = shwfs_home / "origin" / origin
    visit = ""

    for item in sorted(path.iterdir(), reverse=True):
        if item.is_dir():
            visit = item.name
            break
    
    path = path / visit / "snapshot" / "HEAD" / "root"

    return path

# Returns a list of licence filenames matching the licence filenames pattern
def get_license_files(path):
    license_files = []
    for item in path.iterdir():
        if item.is_file():
            filename = item.name
            if re.match(license_file_re, filename):
                license_files.append(filename)  
    return license_files

# returns the license information found in a file
def get_license_info(path, file):
    result = LicenseInfo(file, "")
    path = path / file
    licenses = get_licenses(str(path)) #, min_score=self.DEFAULT_MIN_SCORE, deadline=deadline)
    result.license = licenses["detected_license_expression"]
    return result


query = sys.argv[1]

#result_name = query.replace("/", "")
output = open(f"results_{query}.csv", "w")
output.write(f"origin;full_visit;licences\n")

for origin in get_origins(query):
    print(".", end="") 
    origin_info = process_origin(origin)
    output.write(origin_info.to_csv_line())

output.close
