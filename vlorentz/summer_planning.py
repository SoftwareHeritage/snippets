import datetime
import enum
import html.parser
import os
import pprint
import re

import colorama
import requests

START_DAY = datetime.date.fromisoformat("2021-06-28")  # must be a monday
END_DAY = datetime.date.fromisoformat("2021-08-31")
INTERVAL_RE = re.compile(r"~?([0-9-]+)\s*→\s*~?([0-9-]+)")
URL = "https://intranet.softwareheritage.org/api.php?action=parse&page=Summer_planning_2021&format=json"
AUTH_LOGIN = os.environ["SWH_INTRANET_LOGIN"]
AUTH_PASSWORD = os.environ["SWH_INTRANET_PASSWORD"]


class Modes(enum.Enum):
    TITLE = enum.auto()
    IN_SECTION = enum.auto()
    IN_TABLE = enum.auto()


class Parser(html.parser.HTMLParser):
    stack = []
    current_mode = None
    current_table = None
    current_person = None

    def __init__(self):
        super().__init__()
        self.tables = {}

    def handle_starttag(self, tag, attrs):
        self.stack.append((tag, attrs))
        if tag == "h2":
            self.current_mode = Modes.TITLE
            self.current_person = ""
        elif tag == "table":
            self.current_mode = Modes.IN_TABLE
            self.current_table = []
        elif tag == "tr":
            self.current_table.append([])
        elif tag in ("td", "th"):
            self.current_table[-1].append("")

    def handle_endtag(self, tag):
        while self.stack[-1][0] != tag:
            del self.stack[-1]
        if tag == "h2":
            self.current_mode = Modes.IN_SECTION
        elif tag == "table":
            self.tables[self.current_person] = self.current_table
            self.current_mode = Modes.IN_SECTION
            self.current_table = None

    def handle_data(self, data):
        data = data.strip()
        if not data:
            return
        if self.current_mode == Modes.TITLE:
            if not self.current_person:
                self.current_person = data
        elif self.current_mode == Modes.IN_TABLE:
            self.current_table[-1][-1] += data


def print_calendar(tables):
    one_week = datetime.timedelta(weeks=1)
    current_day = START_DAY

    current_line = []
    def append_cell(s, color=""):
        current_line.append(f"{color}{s:^15.15}{colorama.Style.RESET_ALL}")
    def flush_row():
        nonlocal current_line
        print(" ".join(current_line))
        current_line = []

    # header
    append_cell("")
    while current_day < END_DAY:
        append_cell(current_day.isoformat())
        current_day += one_week
    flush_row()

    for (person, table) in tables.items():
        current_day = START_DAY
        intervals = [INTERVAL_RE.match(row[0]) for row in table]
        intervals = [tuple(map(datetime.date.fromisoformat, interval.groups())) for interval in intervals if interval]
        append_cell(person)
        while current_day < END_DAY:
            color = colorama.Fore.WHITE + colorama.Back.BLACK
            status = "working"
            for (start, end) in intervals:
                if current_day <= start <= current_day+one_week or current_day <= end <= current_day+one_week:
                    color = colorama.Fore.BLACK + colorama.Back.YELLOW
                    status = "partial"
                elif start <= current_day and current_day+one_week <= end:
                    color = colorama.Fore.WHITE + colorama.Back.BLUE
                    status = "not working"
            append_cell(status, color=color)
            current_day += one_week
        flush_row()


def main():
    data = requests.get(URL, auth=(AUTH_LOGIN, AUTH_PASSWORD))
    html = data.json()["parse"]["text"]["*"]

    p = Parser()
    p.feed(html)

    print_calendar(p.tables)


if __name__ == "__main__":
    main()

