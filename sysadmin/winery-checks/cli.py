# Copyright (C) 2024  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

import click
from yaml import safe_load

from swh.core.cli import CONTEXT_SETTINGS
from swh.core.cli import swh as swh_cli_group
from swh.journal.serializers import kafka_to_value
import swh.objstorage.factory as factory
from swh.model import model
from swh.model.model import Content
from swh.objstorage.exc import ObjNotFoundError
import swh.objstorage.factory as factory
from swh.objstorage.interface import ObjStorageInterface, objid_from_dict

from datetime import datetime, timedelta
import time
from typing import Any, Dict, Optional
from threading import Thread
from journal_client import OffsetBoundedJournalClient

_stop = False

def read_config(config_file: Optional[Any] = None) -> Dict:
    """Read configuration from config_file if provided, from the SWH_CONFIG_FILENAME if
    set or fallback to the DEFAULT_CONFIG.

    """
    from os import environ

    if not config_file:
        config_file = environ.get("SWH_CONFIG_FILENAME")

    if not config_file:
        raise ValueError("You must provide a configuration file.")

    with open(config_file) as f:
        data = f.read()
        config = safe_load(data)

    return config

@click.command()
@click.option(
    "--config-file",
    "-C",
    default=None,
    type=click.Path(
        exists=True,
        dir_okay=False,
    ),
    help=(
        "Configuration file. This has a higher priority than SWH_CONFIG_FILENAME "
        "environment variable if set."
    ),
)
@click.option(
    "--partition",
    "-p",
    default=None,
    type=int,
    help="The partition to read",
)
@click.option(
    "--max-offset",
    "-o",
    help="The offset where to stop, if none",
)
def journal_client(config_file, partition, max_offset):
    """Listens for new messages from the SWH Journal, and count them"""
    import functools

    # from .journal_client import process_journal_messages

    config = read_config(config_file)
    journal_cfg = config["journal"]

    journal_cfg["object_types"] = ["content"]
    journal_cfg["prefix"] = "swh.journal.objects"

    print(f"{journal_cfg=}")

    objstorage = factory.get_objstorage(**config["objstorage"])

    stats = Statistics()
    stats.set_max_offset(int(max_offset))
    stats.set_partition(partition)
    stats.start()

    client = OffsetBoundedJournalClient(**journal_cfg)
    client.set_statistics(stats)
    client.assign(partition, max_offset)

    worker_fn = functools.partial(process_journal_messages, objstorage=objstorage, statistics=stats)

    nb_messages = 0
    try:
        nb_messages = client.process(worker_fn)
        print(f"Processed {nb_messages} messages.")
    except KeyboardInterrupt:
      pass
    else:
        print("Done.")
    finally:
        client.close()
        stats.stop()


def process_journal_messages(
    messages: Dict[str, Dict[bytes, bytes]], *, objstorage: ObjStorageInterface, statistics
) -> None:
    """Count the number of different values of an object's property.
    It allow for example to count the persons inside the
    Release (authors) and Revision (authors and committers) classes
    """

    for message in messages.get("content"):
      statistics.start_object()
      # kakfa_content = kafka_to_value(message)
      content = model.Content.from_dict(message)

      content_hashes = objid_from_dict(content.hashes())
      # print(f"{content_hashes=}")
      try:
          # print("get object")
          content_bytes = objstorage.get(content_hashes)
      except ObjNotFoundError:
        print(f"{content_hashes} not found")
        statistics.add_not_found()
      else:
        # print("comparing hash")
        recomputed_hashes = objid_from_dict(
            Content.from_data(content_bytes).hashes()
        )
        if content_hashes != recomputed_hashes:
          statistics.add_incorrect_hash()
          print("Incorrect hash recomputed={recomputed_hashes} expected={content_hashes}")


class Statistics(Thread):
  DELAY=1

  def set_max_offset(self, max_offset):
    self._max_offset = max_offset

  def start(self):
    print("statistics: start")
    self._continue = True
    self._start_time = datetime.now()
    self._total_objects = 0
    self._objects_range = 0
    self._last_check = self._start_time
    self._last_object_count = 0

    self._not_found = 0
    self._incorrect_hash = 0
    self._offset = -1

    super().start()

  def run(self):
    while True:
      current_time = datetime.now()
      duration = current_time - self._last_check
      duration_s = duration.total_seconds()
      self._last_check = current_time

      object_checked = self._total_objects
      object_checked_diff = self._total_objects - self._last_object_count
      self._last_object_count = object_checked

      estimated_offset = self._offset + self._objects_range

      if self._offset > 0:
        total_duration_s = (current_time - self._start_time).total_seconds()
        speed = object_checked / total_duration_s
        offset_to_check = self._max_offset - estimated_offset
        s_to_complete = offset_to_check / speed
        duration_to_complete = timedelta(seconds=s_to_complete)
      else:
        duration_to_complete = "N/A"
        offset_to_check = "N/A"

      print(f"partition={self._partition} object_checked={object_checked}\t" +
          f"not_found={self._not_found}\tincorrect_hash={self._incorrect_hash}" +
          f"\tto_check={offset_to_check} time_to_completion={duration_to_complete}"
          f"\t({object_checked_diff / duration_s:.2f}/s)")
      time.sleep(self.DELAY)
      if not self._continue:
        self.print_last_stats()
        break

  def stop(self):
    self._continue = False

  def print_last_stats(self):
    end = datetime.now()
    duration = end - self._start_time
    duration_s = duration.total_seconds()
    object_per_sec = self._total_objects / duration_s
    print(f"partition={self._partition} total duration: {duration} {self._total_objects} checked\t" +
      f"not_found={self._not_found}\tincorrect_hash={self._incorrect_hash}" +
      f"\t({object_per_sec:.2f}/s)")

  def start_object(self):
    self._total_objects += 1
    self._objects_range += 1

  def add_not_found():
    self._not_found += 1

  def add_incorrect_hash():
    self._incorrect_hash += 1

  def set_offset(self, offset: int):
    self._offset = offset
    self._objects_range = 0

  def set_partition(self, partition: int):
    self._partition = partition

if __name__ == "__main__":
    journal_client()
