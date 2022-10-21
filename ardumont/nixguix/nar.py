# Copyright (C) 2022 @zimoun and the Software Heritage developers
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

import base64
import hashlib
import io
import os
import stat
from pathlib import Path

import click


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
            length = len(byte_sequence)
        elif isinstance(thing, io.BufferedReader):
            length = os.stat(thing.name).st_size

        # ease reading of _serialize
        elif isinstance(thing, list):
            for stuff in thing:
                self.str_(stuff)
            return
        else:
            raise ValueError("not string nor file")

        blen = length.to_bytes(8, byteorder="little")  # 64-bit little endian
        self._update(blen)

        # first part of 'pad'
        if isinstance(thing, str):
            self._update(byte_sequence)
        elif isinstance(thing, io.BufferedReader):
            for chunk in iter(lambda: thing.read(2 * 2 * 2 * 2 * 4096), b""):
                self._update(chunk)

        # second part of 'pad
        m = length % 8
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


@click.command()
@click.argument("directory")
@click.option("--hash-algo", "-H", default="sha256")
@click.option(
    "--format-output",
    "-f",
    default="hex",
    type=click.Choice(["hex", "base32", "base64"], case_sensitive=False),
)
@click.option("--debug/--no-debug", default=lambda: os.environ.get("DEBUG", False))
def cli(directory, hash_algo, format_output, debug):
    """Compute NAR hashes on a directory."""
    h = hashlib.sha256() if hash_algo == "sha256" else "sha1"
    updater = h.update
    format_output = format_output.lower()

    def identity(hsh):
        return hsh

    def convert_b64(hsh: str):
        return base64.b64encode(bytes.fromhex(hsh)).decode().lower()

    def convert_b32(hsh: str):
        return base64.b32encode(bytes.fromhex(hsh)).decode().lower()

    convert_fn = {
        "hex": identity,
        "base64": convert_b64,
        "base32": convert_b32,
    }

    convert = convert_fn[format_output]

    nar = Nar(updater, isdebug=debug)
    nar.serialize(directory)
    print(convert(h.hexdigest()))


if __name__ == "__main__":
    cli()
