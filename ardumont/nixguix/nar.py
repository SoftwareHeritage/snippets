# Copyright (C) 2022 @zimoun and the Software Heritage developers
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

import base64
import hashlib
import io
import os
import stat
import sys
from pathlib import Path


class Nar:
    def __init__(self, updater, isdebug=False):
        self._update = updater

        self.__isdebug = isdebug
        self.__indent = 0

    def str_(self, thing):
        # named 'str' in Figure 5.2 p.93 (page 101 of pdf)

        if self.__isdebug and (
            isinstance(thing, str) or isinstance(thing, io.BufferedReader)
        ):
            indent = "".join(["  " for _ in range(self.__indent)])
            print(indent + str(thing))

        # named 'int'
        if isinstance(thing, str):
            byte_sequence = thing.encode("utf-8")
            l = len(byte_sequence)
        elif isinstance(thing, io.BufferedReader):
            l = os.stat(thing.name).st_size

        # ease reading of _serialize
        elif isinstance(thing, list):
            for stuff in thing:
                self.str_(stuff)
            return
        else:
            raise ValueError("not string nor file")

        blen = l.to_bytes(8, byteorder="little")  # 64-bit little endian
        self._update(blen)

        # first part of 'pad'
        if isinstance(thing, str):
            self._update(byte_sequence)
        elif isinstance(thing, io.BufferedReader):
            for chunk in iter(lambda: thing.read(2 * 2 * 2 * 2 * 4096), b""):
                self._update(chunk)

        # second part of 'pad
        m = l % 8
        if m == 0:
            offset = 0
        else:
            offset = 8 - m
        boffset = bytearray(offset)
        self._update(boffset)

    def _serialize(self, fso):
        if self.__isdebug:
            self.__indent += 1
        self.str_("(")

        mode = os.lstat(fso).st_mode

        if stat.S_ISREG(mode):
            self.str_(["type", "regular"])
            if os.access(fso, os.X_OK):
                self.str_(["executable", ""])
            self.str_("contents")
            with open(str(fso), "rb") as f:
                self.str_(f)

        elif stat.S_ISLNK(mode):
            self.str_(["type", "symlink", "target"])
            self.str_(os.readlink(fso))

        elif stat.S_ISDIR(mode):
            self.str_(["type", "directory"])
            for path in sorted(Path(fso).iterdir()):
                self._serializeEntry(path)

        else:
            raise ValueError("unsupported file type")

        self.str_(")")
        if self.__isdebug:
            self.__indent += -1

    def _serializeEntry(self, fso):
        if self.__isdebug:
            self.__indent += 1
        self.str_(["entry", "(", "name", fso.name, "node"])
        self._serialize(fso)
        self.str_(")")
        if self.__isdebug:
            self.__indent += -1

    def serialize(self, fso):
        self.str_("nix-archive-1")
        self._serialize(fso)
        return


if __name__ == "__main__":
    directory = sys.argv[1]
    try:
        if sys.argv[2] == "sha1":
            h = hashlib.sha1()
        else:
            h = hashlib.sha256()
        updater = h.update
        try:
            if sys.argv[3] == "hex":
                convert = lambda hsh: hsh
            elif sys.argv[3] == "base64":  # hex -> base64
                convert = lambda hsh: base64.b64encode(bytes.fromhex(hsh)).decode()
            elif sys.argv[3] == "BASE32":
                convert = lambda hsh: base64.b32encode(bytes.fromhex(hsh)).decode()
            elif sys.argv[3] == "base32":
                convert = (
                    lambda hsh: base64.b32encode(bytes.fromhex(hsh)).decode().lower()
                )
            else:
                convert = lambda hsh: hsh
        except:
            convert = lambda hsh: hsh
        isPrintable = True
    except:
        updater = sys.stdout.buffer.write
        isPrintable = False

    d = os.environ.get("DEBUG")
    if d and d != "no":
        debug = True
    else:
        debug = False
    nar = Nar(updater, debug)
    nar.serialize(directory)
    if isPrintable:
        print(convert(h.hexdigest()))
