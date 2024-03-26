# Copyright (C) 2024  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

from collections import defaultdict
from typing import Callable, Dict, List
import logging

from confluent_kafka import KafkaError, TopicPartition

from swh.journal.client import EofBehavior, JournalClient, _error_cb

logger = logging.getLogger(__name__)

class OffsetBoundedJournalClient(JournalClient):
  """This journal client works on a given partition
      on a given topic and stops when a given offset is reached
  """

  def subscribe(self):
    """Subscribe can't be used as it only supports a list of topics.
       The `assign` method be called instead with the partition and offset to use
    """
    pass

  def set_statistics(self, statistics):
    self._statistics = statistics

  def assign(self, partition_id: int, max_offset: int):
    topic = self.subscription[0]
    print(f"{topic=}")
    self._max_offset = int(max_offset) #???
    self.consumer.assign([TopicPartition(topic, partition_id)])
    print(f"Consumer assigned to partition {partition_id}")

  def handle_messages(self, messages, callable: Callable[[Dict[str, List[dict]]], None]):
    """Polls Kafka for a batch of messages, and calls the worker_fn
    with these messages.
    Add the check of the position on the partition and exit if the max allowed offset
    is reached
    """
    self._statistics.set_offset(messages[0].offset())

    nb_processed, at_eof = super().handle_messages(messages, callable)

    offset=messages[len(messages)-1].offset()

    self._statistics.set_offset(offset)

    if offset >= self._max_offset:
      print(f"Max offset {self._max_offset} ({offset}) reached")
      at_eof = True

    return nb_processed, at_eof



