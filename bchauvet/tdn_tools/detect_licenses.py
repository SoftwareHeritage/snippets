import configparser
from urllib.parse import quote
from swh.web.client.client import WebAPIClient
import re
import sys
import subprocess


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

allowed_licences = [
"GPL", # Adding the GPL
"0BSD",
"AAL",
"Abstyles",
"AdaCore-doc",
"Adobe-2006",
"Adobe-Glyph",
"ADSL,AFL-1.1",
"AFL-1.2",
"AFL-2.0",
"AFL-2.1",
"AFL-3.0",
"Afmparse",
"AMDPLPA",
"AML",
"AMPAS",
"ANTLR-PD",
"Apache-1.0",
"Apache-1.1",
"Apache-2.0",
"APAFML",
"App-s2p",
"Artistic-1.0",
"Artistic-1.0-cl8",
"Artistic-1.0-Perl",
"Artistic-2.0,Baekmuk",
"Bahyph",
"Barr",
"Beerware",
"Bitstream-Charter",
"Bitstream-Vera",
"BlueOak-1.0.0",
"Boehm-GC",
"Borceux,Brian-Gladman-3-Clause",
"BSD-1-Clause",
"BSD-2-Clause",
"BSD-2-Clause-Patent",
"BSD-2-Clause-Views",
"BSD-3-Clause",
"BSD-3-Clause-Attribution",
"BSD-3-Clause-Clear",
"BSD-3-Clause-LBNL",
"BSD-3-Clause-Modification,BSD-3-Clause-No-Nuclear-License-2014",
"BSD-3-Clause-No-Nuclear-Warranty",
"BSD-3-Clause-Open-MPI",
"BSD-4-Clause",
"BSD-4-Clause-Shortened",
"BSD-4-Clause-UC",
"BSD-4.3RENO",
"BSD-4.3TAHOE",
"BSD-Advertising-Acknowledgement",
"BSD-Attribution-HPND-disclaimer",
"BSD-Source-Code",
"BSL-1.0",
"bzip2-1.0.6",
"Caldera,CC-BY-1.0",
"CC-BY-2.0",
"CC-BY-2.5",
"CC-BY-2.5-AU",
"CC-BY-3.0",
"CC-BY-3.0-AT",
"CC-BY-3.0-DE",
"CC-BY-3.0-NL",
"CC-BY-3.0-US",
"CC-BY-4.0",
"CDLA-Permissive-1.0",
"CDLA-Permissive-2.0",
"CECILL-B",
"CERN-OHL-1.1,CERN-OHL-1.2",
"CERN-OHL-P-2.0",
"CFITSIO",
"checkmk",
"ClArtistic",
"Clips",
"CMU-Mach",
"CNRI-Jython",
"CNRI-Python",
"CNRI-Python-GPL-Compatible",
"COIL-1.0",
"Community-Spec-1.0",
"Condor-1.1",
"Cornell-Lossless-JPEG,Crossword",
"CrystalStacker",
"Cube",
"curl",
"DL-DE-BY-2.0",
"DOC",
"Dotseqn",
"DRL-1.0",
"DSDP",
"dtoa",
"dvipdfm,ECL-1.0",
"ECL-2.0",
"EFL-1.0",
"EFL-2.0",
"eGenix",
"Entessa",
"EPICS",
"etalab-2.0",
"EUDatagrid",
"Fair",
"FreeBSD-DOC,FSFAP",
"FSFULLR",
"FSFULLRWD",
"FTL",
"GD",
"Giftware",
"Glulxe",
"GLWTPL",
"Graphics-Gems",
"GStreamer-exception-2005",
"HaskellReport",
"HP-1986",
"HPND",
"HPND-Markus-Kuhn",
"HPND-sell-variant",
"HPND-sell-variant-MIT-disclaimer",
"HTMLTIDY",
"IBM-pibs",
"ICU",
"IJG",
"IJG-short",
"ImageMagick",
"iMatix",
"Info-ZIP",
"Intel,Intel-ACPI",
"ISC",
"Jam",
"JasPer-2.0",
"JPNIC",
"JSON",
"Kazlib",
"Knuth-CTAN",
"Latex2e",
"Latex2e-translated-notice,Leptonica",
"Libpng",
"libpng-2.0",
"libtiff",
"Linux-OpenIB",
"LLVM-exception",
"LOOP",
"LPL-1.0",
"LPL-1.02",
"LPPL-1.3c,Martin-Birgmeier",
"metamail",
"Minpack",
"MirOS",
"MIT",
"MIT-0",
"MIT-advertising",
"MIT-CMU",
"MIT-enna",
"MIT-feh",
"MIT-Festival",
"MIT-Modern-Variant",
"MIT-open-group",
"MIT-Wu",
"MITNFA",
"mpich2",
"mplus",
"MS-LPL,MS-PL",
"MTLL",
"MulanPSL-1.0",
"MulanPSL-2.0",
"Multics",
"Mup",
"NAIST-2003",
"NASA-1.3",
"Naumen",
"NBPL-1.0,NCSA",
"Net-SNMP",
"NetCDF",
"Newsletr",
"NICTA-1.0",
"NIST-PD-fallback",
"NIST-Software",
"NLOD-1.0",
"NLOD-2.0,NRL",
"NTP",
"NTP-0",
"O-UDA-1.0",
"ODC-By-1.0",
"OFFIS",
"OFL-1.0",
"OFL-1.0-no-RFN",
"OFL-1.0-RFN",
"OFL-1.1-no-RFN",
"OFL-1.1-RFN",
"OGC-1.0",
"OGDL-Taiwan-1.0",
"OGL-Canada-2.0",
"OGL-UK-1.0",
"OGL-UK-2.0,OGL-UK-3.0",
"OGTSL",
"OLDAP-1.1",
"OLDAP-1.2",
"OLDAP-1.3",
"OLDAP-1.4",
"OLDAP-2.0",
"OLDAP-2.0.1,OLDAP-2.1",
"OLDAP-2.2",
"OLDAP-2.2.1",
"OLDAP-2.2.2",
"OLDAP-2.3",
"OLDAP-2.4",
"OLDAP-2.5",
"OLDAP-2.6,OLDAP-2.7",
"OLDAP-2.8",
"OML",
"OpenSSL",
"OPUBL-1.0",
"PHP-3.0",
"PHP-3.01",
"Plexus",
"PostgreSQL",
"PSF-2.0,psfrag",
"psutils",
"Python-2.0",
"Python-2.0.1",
"Qhull",
"Rdisc",
"RSA-MD",
"Ruby",
"Saxpath",
"SCEA",
"SchemeReport,Sendmail",
"SGI-B-1.1",
"SGI-B-2.0",
"SGP4",
"SHL-0.5",
"SHL-0.51",
"SHL-2.0",
"SHL-2.1",
"SMLNJ",
"snprintf",
"Spencer-86,Spencer-94",
"Spencer-99",
"SSH-OpenSSH",
"SSH-short",
"SunPro",
"Swift-exception",
"SWL",
"TCL",
"TCP-wrappers,TermReadKey",
"TPDL",
"TTWL",
"TU-Berlin-1.0",
"TU-Berlin-2.0",
"UCAR",
"Unicode-DFS-2015",
"Unicode-DFS-2016,UnixCrypt",
"UPL-1.0",
"Vim",
"VSL-1.0",
"W3C",
"W3C-19980720",
"W3C-20150513",
"w3m",
"Widget-Workshop",
"Wsuipa,X11",
"X11-distribute-modifications-variant",
"Xdebug-1.03",
"Xerox",
"Xfig",
"XFree86-1.1",
"xinetd",
"xlock",
"Xnet",
"xpp,XSkat",
"Zed",
"Zend-2.0",
"Zlib",
"zlib-acknowledgement",
"ZPL-1.1",
"ZPL-2.0",
"ZPL-2.1"
]

license_file_re = re.compile(rf"^(|.*[-_. ])({'|'.join(license_file_names)})(|[-_. ].*)$", re.IGNORECASE)

config = configparser.ConfigParser()
config.read('config.ini')
shwfs_home = config.get('SWH', 'swhfs_home')

class OriginInfo:
    def __init__(self, url, visit, licenses):
        self.url = url
        self.visit = visit
        self.licenses = licenses
    
    def to_csv_line_first_license_only(self):
        url = self.url
        visit = self.visit
        filename = "-"
        license = "-"
        if len(self.licenses) > 0:
            filename = self.licenses[0].filename
            license = self.licenses[0].license
        return (f"{url};{visit};{filename};{license}\n")


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
    root_path = get_root_path(encoded_origin)
    license_files = []
    try:
        license_files = get_license_files(root_path)
        for file in license_files:
            license_info = get_license_info(root_path,file)
            result.licenses.append(license_info)
    except:
        result.visit = "False"
    return result

# Returns the root directory path for the HEAD revision in the most recent snapshot 
def get_root_path(origin):
    path = f"{shwfs_home}/origin/{origin}"
    command = f"ls {path} | tail -1"
    cmd_result = subprocess.check_output(command, shell="True", executable="/bin/bash")
    visit = cmd_result.decode().rstrip()
    path += "/" + visit + "/snapshot/HEAD/root"
    return path

# Returns a list of licence filenames matching the licence filenames pattern
def get_license_files(path):
    license_files = []
    command = f"ls -p {path} | grep -v /"

    try:
        cmd_result = subprocess.check_output(command, shell="True", executable="/bin/bash", stderr = subprocess.STDOUT)
        for line in cmd_result.splitlines():
            file = line.decode().rstrip()
            if re.match(license_file_re, file):
                license_files.append(file)
    except:
        raise
    # finally:
    #     for line in cmd_result.splitlines():
    #         file = line.decode().rstrip()
    #         if re.match(license_file_re, file):
    #             license_files.append(file)
    
    return license_files

# returns the license information found in a file
def get_license_info(path, file):
    result = LicenseInfo(file, "unknown")
    command = f"cat {path}/{file}"
    cmd_result = subprocess.check_output(command, shell="True", executable="/bin/bash")
    file_content = cmd_result.decode().rstrip()
    for license in allowed_licences:
        if license in file_content:
            result.license = license
            break
    return result

# process_origin("https://github.com/tcyrus/keyboard-layout")


query = sys.argv[1]

output = open(f"results_{query}.csv", "w")
output.write(f"origin;full_visit;file;licence\n")

for origin in get_origins(query):
    origin_info = process_origin(origin)
    output.write(origin_info.to_csv_line_first_license_only())

output.close
