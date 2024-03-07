#!/usr/bin/env python3

'''
source swhEnv/bin/activate
source env/get_journal_check_and_replay_passwords
./get_journal_check_and_replay.py
'''

from swh.journal.client import get_journal_client
from swh.model.model import Directory, Release, Revision, Origin, Content, OriginVisit, OriginVisitStatus, SkippedContent, RawExtrinsicMetadata, ExtID, Snapshot
from swh.storage import get_storage
from swh.storage.algos import directory, snapshot, origin as algos_origin
from config import *
from functools import partial
import attr
from types import GeneratorType
from swh.journal.serializers import pprint_key
from swh.storage.utils import round_to_milliseconds
from swh.model.hashutil import hash_to_hex, hash_git_data
from datetime import datetime, timezone
import logging


logger = logging.getLogger(__name__)

def str_now():
    return str(datetime.now()).replace(" ","_")


def append_swhid(filename, suffix_date, swhid):
    with open(f"{filename}-{suffix_date}.lst",'a') as f:
        f.write(f"{swhid}\n")


def swhid_str(obj):
    """Build a swhid like string representation for model object with SWHID (e.g. most
    swh dag objects). Otherwise, just write a unique representation of the object (e.g.
    extid, origin_visit, origin_visit_status)

    """
    if hasattr(obj, 'swhid'):
        return str(obj.swhid())
    return pprint_key(obj.unique_key())


def swhid_key(obj):
    """Build a swhid like string representation for model object with SWHID (e.g. most
    swh dag objects). Otherwise, just write a unique representation of the object (e.g.
    extid, origin_visit, origin_visit_status)

    """
    if hasattr(obj, 'swhid'):
        return str(obj.swhid())
    return hash_to_hex(hash_git_data(str(obj.unique_key()).encode('utf-8'), "blob"))


def is_equal (obj_ref, obj_model_ref):
    """
    Objects model comparison with directory scpecific case.
    """
    if isinstance(obj_ref, Directory) and isinstance(obj_model_ref, Directory):
        return obj_ref.id == obj_model_ref.id and sorted(obj_ref.entries) == sorted(obj_model_ref.entries)
    return obj_ref == obj_model_ref


def process(cs_storage, pg_storage, objects):
    """Process objects read from the journal.

    This reads journal objects and for each of them, check whether they are present in
    the cassandra storage. If they are, the check stops there. Otherwise, check for the
    presence of the object in the postgresql backend. If present in the postgresql
    backend, write the object as missing in cassandra. This object needs to be replayed.
    If not present either in the postgresql backend, just marks it as such.

    Pseudo code:

        for all object in journal
          read object in cassandra
            it exists, we found it:
              nothing to do, stop
            else (it does not exist):
             read object in postgresql
             it exists, we found it:
               write <swhid> to `<object-type>-to-replay.lst`
               mkdir -p `to-replay/<object-type>/<swhid>/`
               echo $(kafka-object-as-string) > `<object-type>-to-replay/<swhid>/journal`
               echo $(postgresql-object-as-string) > `<object-type>-to-replay/<swhid>/postgresql`
               stop
             else (present in journal only)
               mkdir -p `journal-only/<object-type>/<swhid>/`
               echo $(kafka-object-as-string) > `<object-type>-to-replay/<swhid>/journal`

    """

    suffix_timestamp = str_now()
    for otype, objs in objects.items():
        logger.info(f"Processing {len(objs)} <{otype}> objects.")
        errors_counter = 0
        for obj in objs:
            if otype == "content":
                obj_model = Content.from_dict(obj)
                cs_get = cs_storage.content_get
                pg_get = pg_storage.content_get
                sha1 = obj_model.sha1
                stargs = [sha1]
            elif otype == "directory":
                obj_model = Directory.from_dict(obj)
                cs_get = partial(directory.directory_get, cs_storage)
                pg_get = partial(directory.directory_get, pg_storage)
                id = obj_model.id
                stargs = id
            elif otype == "extid":
                obj_model = ExtID.from_dict(obj)
                extid_type = obj_model.extid_type
                extid = obj_model.extid
                cs_get = partial(cs_storage.extid_get_from_extid, extid_type)
                pg_get = partial(pg_storage.extid_get_from_extid, extid_type)
                stargs = [extid]
                #print(stargs)
            elif otype == "origin":
                obj_model = Origin.from_dict(obj)
                cs_get = cs_storage.origin_get
                pg_get = pg_storage.origin_get
                url = obj_model.url
                id = obj_model.id
                stargs = [url]
            elif otype == "origin_visit":
                obj_model = OriginVisit.from_dict(obj)
                origin = obj_model.origin
                visit = obj_model.visit
                cs_get = partial(cs_storage.origin_visit_get_by, origin)
                pg_get = partial(pg_storage.origin_visit_get_by, origin)
                stargs = visit
            elif otype == "origin_visit_status":
                obj_model = OriginVisitStatus.from_dict(obj)
                origin = obj_model.origin
                visit = obj_model.visit
                cs_get = partial(algos_origin.iter_origin_visit_statuses, cs_storage, origin)
                pg_get = partial(algos_origin.iter_origin_visit_statuses, pg_storage, origin)
                stargs = visit
            elif otype == "raw_extrinsic_metadata":
                obj_model = RawExtrinsicMetadata.from_dict(obj)
                cs_get = cs_storage.raw_extrinsic_metadata_get_by_ids
                pg_get = pg_storage.raw_extrinsic_metadata_get_by_ids
                id = obj_model.id
                stargs = [id]
            elif otype == "release":
                obj_model = Release.from_dict(obj)
                cs_get = cs_storage.release_get
                pg_get = pg_storage.release_get
                id = obj_model.id
                stargs = [id]
            elif otype == "revision":
                obj_model = Revision.from_dict(obj)
                cs_get = cs_storage.revision_get
                pg_get = pg_storage.revision_get
                id = obj_model.id
                stargs = [id]
            elif otype == "skipped_content":
                obj_model = SkippedContent.from_dict(obj)
                cs_get = cs_storage.skipped_content_find
                pg_get = pg_storage.skipped_content_find
                stargs = obj_model.hashes()
            elif otype == "snapshot":
                obj_model = Snapshot.from_dict(obj)
                # snapshot_get return the dict and not the swh model object
                # (deal with huge snapshot)
                cs_get = partial(snapshot.snapshot_get_all_branches, cs_storage)
                pg_get = partial(snapshot.snapshot_get_all_branches, pg_storage)
                id = obj_model.id
                stargs = id
            cs_obj = cs_get(stargs)

            # cassandra storage truncate timestamp to the whole millisecond
            if otype in ("origin_visit", "origin_visit_status"):
                date = round_to_milliseconds(obj_model.date)
                truncated_obj_model = attr.evolve(obj_model, date=date)
            else:
                truncated_obj_model = obj_model

            if isinstance(cs_obj, (list, GeneratorType)):
                for _cs_obj in cs_obj:
                    if _cs_obj is None:
                        # release_get may return None object
                        continue
                    if is_equal(_cs_obj, truncated_obj_model):
                        cs_obj = _cs_obj
                        break

            # Some objects have no swhid...
            swhid = swhid_str(obj_model)
            # so we compute a unique key without the swhid (when need, e.g origin_visit, origin_visit_status,...)
            unique_key = swhid_key(obj_model)
            ## Debug: check object representation written on disk
            #write_representation_on_disk("cassandra", "journal_representation", obj_model, otype, unique_key)
            #write_representation_on_disk("cassandra", "cassandra_representation", cs_obj, otype, unique_key)
            #append_swhid(f"{otype}-debug", suffix_timestamp, swhid)

            if is_equal(cs_obj, truncated_obj_model):
                # kafka and cassandra objects match
                continue

            # object not found in cassandra
            #print(f"{obj_model=}")
            pg_obj = pg_get(stargs)

            if isinstance(pg_obj, (list, GeneratorType)):
                for _pg_obj in pg_obj:
                    if _pg_obj is None:
                        # release_get may return None object
                        continue
                    if is_equal(_pg_obj, obj_model):
                        pg_obj = _pg_obj
                        break

            if is_equal(pg_obj, obj_model):
                # kafka and postgresql objects match
                errors_counter += 1
                append_swhid(f"{otype}-swhid-toreplay", suffix_timestamp, swhid)
                # save object representation in dedicated tree
                write_representation_on_disk("to_replay", "journal_representation", obj, otype, unique_key)
                write_representation_on_disk("to_replay", "postgresql_representation", pg_obj, otype, unique_key)
                continue

            # object is present only in journal
            append_swhid(f"{otype}-swhid-in-journal-only", suffix_timestamp, swhid)
            # save object representation in dedicated tree
            write_representation_on_disk("journal_only", "journal_representation", obj, otype, unique_key)

        logger.info(f"\tObjects missing in cassandra: {errors_counter}.")

def write_representation_on_disk(top_level_path, representation_type, obj, otype, unique_key):
    dir_path = f"{top_level_path}/{otype}/{unique_key}/"
    os.makedirs(dir_path, exist_ok=True)
    journal_path = os.path.join(dir_path, representation_type)
    with open(journal_path, 'a') as f:
        f.write(repr(obj))

if __name__ == "__main__":
    FORMAT = '[%(asctime)s] %(message)s'
    logging.basicConfig(format=FORMAT)
    logger.setLevel(logging.INFO)
    cassandra_logger = logging.getLogger("cassandra.cluster")
    cassandra_logger.setLevel(logging.ERROR)
    try:
        jn_storage = get_journal_client(**client_cfg)
    except ValueError as exc:
        logger.info(exc)
        exit(1)
    logger.info("🚧 Processing objects...")
    try:
        cs_storage = get_storage("cassandra", **cs_staging_storage_conf)
        pg_storage = get_storage("postgresql", **pg_staging_storage_conf)
        process_fn = partial(process, cs_storage, pg_storage)
        # Run the client forever
        jn_storage.process(process_fn)
    except KeyboardInterrupt:
        logger.info("Called Ctrl-C, exiting.")
