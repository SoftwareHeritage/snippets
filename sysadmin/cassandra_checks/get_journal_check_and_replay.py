#!/usr/bin/env python3

"""Journal client to process objects from kafka to check cassandra object consistency.

"""

import click
from yaml import safe_load

from os import makedirs
from os.path import join
from swh.journal.client import get_journal_client
from swh.model.model import Directory, Release, Revision, Origin, Content, OriginVisit, OriginVisitStatus, SkippedContent, RawExtrinsicMetadata, ExtID, Snapshot
from swh.storage import get_storage
from swh.storage.algos import directory as dir_algos, snapshot as snp_algos, origin as ori_algos
from functools import partial
import attr
from types import GeneratorType
from swh.journal.serializers import pprint_key
from swh.storage.utils import round_to_milliseconds
from swh.model.hashutil import hash_to_hex, hash_git_data
from datetime import datetime
import logging

from typing import Any, Dict, Optional


logger = logging.getLogger(__name__)


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


def str_now():
    """Generate a now() date as a string to use as suffix filename"""
    return str(datetime.now()).replace(" ","_")


def append_swhid(filename, suffix_date, swhid):
    """Write the swhid identifier to a filename with a suffix_date."""
    with open(f"{filename}-{suffix_date}.lst",'a') as f:
        f.write(f"{swhid}\n")


def append_representation_on_disk_as_tree(top_level_path, representation_type, obj, otype, unique_key):
    """Write the representation of the object obj with type otype in an arborescence
    tree at <top_level_path>/<otype>/<unique-key> in the file <representation_type>.

    If a file already exist, a new line is appended to the file with the other
    representation.

    """
    dir_path = f"{top_level_path}/{otype}/{unique_key}/"
    makedirs(dir_path, exist_ok=True)
    journal_path = join(dir_path, representation_type)
    with open(journal_path, 'a') as f:
        f.write(repr(obj))


def flush_objects_to_disk(top_level_path, representation_type, obj_or_list, otype, unique_key):
    """Flush the backend <representation-type> representation of the objects we found in
    backends but failed to compare with the journal object.

    Because some functions in the storage interface returns list of elements or 1
    element.

    """
    if isinstance(obj_or_list, (list, GeneratorType)):
        for _obj in obj_or_list:
            append_representation_on_disk_as_tree(top_level_path, representation_type, _obj, otype, unique_key)
    else:
        append_representation_on_disk_as_tree(top_level_path, representation_type, obj_or_list, otype, unique_key)


def swhid_str(obj):
    """Build a swhid like string representation for model object with SWHID (e.g. most
    swh dag objects). Otherwise, just write a unique representation of the object (e.g.
    extid, origin_visit, origin_visit_status) as a dict.

    """
    if hasattr(obj, 'swhid'):
        return str(obj.swhid())
    return pprint_key(obj.unique_key())


def swhid_key(obj):
    """Build a swhid like string representation for model object with SWHID (e.g. most
    swh dag objects). Otherwise, just write a unique representation of the object (e.g.
    extid, origin_visit, origin_visit_status) which is filesystem compliant.

    """
    if hasattr(obj, 'swhid'):
        return str(obj.swhid())
    return hash_to_hex(hash_git_data(str(obj.unique_key()).encode('utf-8'), "blob"))


def compare_directory(obj_ref: Directory, obj_model_ref: Directory) -> bool:
    """Directory model comparison.

    Their directory entries might be in different order when getting them from
    postgresql or cassandra. As that does not impact the hash, that should not impact
    the equality test. That should/could be dealt with in the model but it's not
    currently the case so we do it here (for now).

    """
    return obj_ref.id == obj_model_ref.id and \
        sorted(obj_ref.entries) == sorted(obj_model_ref.entries)


def compare_revision(obj_ref: Revision, obj_model_ref: Revision) -> bool:
    """Revision model comparison.

    Revision: Revision objects in cassandra do not hold any metadata while the historic
    revision in postgresql have it. Those cassandra revisions have been replayed out of
    the postgresql ones with a specific fixer which drops that field. So, we do not
    account for them during the comparison.

    """

    return attr.evolve(obj_ref, metadata=None) == attr.evolve(obj_model_ref, metadata=None)


def compare_object(obj_ref, obj_model_ref) -> bool:
    return obj_ref == obj_model_ref


EQUAL_FN = {
    "directory": compare_directory,
    "revision": compare_revision
}


def is_equal(obj_ref, obj_model_ref):
    """Objects model comparison.

    """
    equal_fn = EQUAL_FN.get(obj_ref.object_type, compare_object)
    return equal_fn(obj_ref, obj_model_ref)


def cassandra_truncate_obj_model(obj_model):
    """Cassandra's swh representation for origin-visit and origin-visit-status use date
    in their model (instead of other timestamp model). This has the unfortunate effect
    to round the timestamp to the millisecond. So we need to adapt the obj_model so the
    comparison can happen "properly".

    Called only for the object type origin_visit and origin_visit_status

    """
    date = round_to_milliseconds(obj_model.date)
    return attr.evolve(obj_model, date=date)


def identity(obj_model):
    return obj_model


def configure_obj_get(otype: str, obj: Dict, cs_storage, pg_storage):
    """Configure how to retrieve the object with type otype. Depending on the object
    type, this returns a tuple of the object model, a truncated model object function,
    an equality function, a cassandra getter function and a storage getter function.

    """
    truncate_obj_model_fn = identity
    is_equal_fn = compare_object

    if otype == "content":
        obj_model = Content.from_dict(obj)
        sha1s = [obj_model.sha1]
        cs_get = partial(cs_storage.content_get, sha1s)
        pg_get = partial(pg_storage.content_get, sha1s)
    elif otype == "directory":
        obj_model = Directory.from_dict(obj)
        id_ = obj_model.id
        cs_get = partial(dir_algos.directory_get, cs_storage, id_)
        pg_get = partial(dir_algos.directory_get, pg_storage, id_)
        is_equal_fn = compare_directory
    elif otype == "extid":
        obj_model = ExtID.from_dict(obj)
        extid_type = obj_model.extid_type
        extids = [obj_model.extid]
        cs_get = partial(cs_storage.extid_get_from_extid, extid_type, extids)
        pg_get = partial(pg_storage.extid_get_from_extid, extid_type, extids)
    elif otype == "origin":
        obj_model = Origin.from_dict(obj)
        url = obj_model.url
        urls = [url]
        cs_get = partial(cs_storage.origin_get, urls)
        pg_get = partial(pg_storage.origin_get, urls)
    elif otype == "origin_visit":
        obj_model = OriginVisit.from_dict(obj)
        origin = obj_model.origin
        visit = obj_model.visit
        cs_get = partial(cs_storage.origin_visit_get_by, origin, visit)
        pg_get = partial(pg_storage.origin_visit_get_by, origin, visit)
        truncate_obj_model_fn = cassandra_truncate_obj_model
    elif otype == "origin_visit_status":
        obj_model = OriginVisitStatus.from_dict(obj)
        origin = obj_model.origin
        visit = obj_model.visit
        cs_get = partial(
            ori_algos.iter_origin_visit_statuses, cs_storage, origin, visit)
        pg_get = partial(
            ori_algos.iter_origin_visit_statuses, pg_storage, origin, visit)
        truncate_obj_model_fn = cassandra_truncate_obj_model
    elif otype == "raw_extrinsic_metadata":
        obj_model = RawExtrinsicMetadata.from_dict(obj)
        ids = [obj_model.id]
        cs_get = partial(cs_storage.raw_extrinsic_metadata_get_by_ids, ids)
        pg_get = partial(pg_storage.raw_extrinsic_metadata_get_by_ids, ids)
    elif otype == "release":
        obj_model = Release.from_dict(obj)
        ids = [obj_model.id]
        cs_get = partial(cs_storage.release_get, ids)
        pg_get = partial(pg_storage.release_get, ids)
    elif otype == "revision":
        obj_model = Revision.from_dict(obj)
        ids = [obj_model.id]
        cs_get = partial(cs_storage.revision_get, ids)
        pg_get = partial(pg_storage.revision_get, ids)
        is_equal_fn = compare_revision
    elif otype == "skipped_content":
        obj_model = SkippedContent.from_dict(obj)
        hashes = obj_model.hashes()
        cs_get = partial(cs_storage.skipped_content_find, hashes)
        pg_get = partial(pg_storage.skipped_content_find, hashes)
    elif otype == "snapshot":
        obj_model = Snapshot.from_dict(obj)
        id_ = obj_model.id
        # snapshot_get return the dict and not the swh model object
        # (deal with huge snapshot)
        cs_get = partial(snp_algos.snapshot_get_all_branches, cs_storage, id_)
        pg_get = partial(snp_algos.snapshot_get_all_branches, pg_storage, id_)

    return obj_model, truncate_obj_model_fn, is_equal_fn, cs_get, pg_get


def process(cs_storage, pg_storage, top_level_path, objects):
    """Process objects read from the journal.

    This reads journal objects and for each of them, check whether they are present in
    the cassandra storage. If they are, the check stops there. Otherwise, check for the
    presence of the object in the postgresql backend. If present in the postgresql
    backend, write the object as missing in cassandra. This object needs to be replayed.
    If not present either in the postgresql backend, just marks it as such.

    Args:
        cs_storage: Configuration dict for cassandra storage communication
        pg_storage: Configuration dict for postgresql storage communication
        top_level_path: Top level directory to write swhid error reporting

    Pseudo code:

        for all object in journal
          read object in cassandra
            it exists, we found it:
              nothing to do, stop
            else (it does not exist):
             read object in postgresql
             it exists, we found it:
               write <swhid> to `<object-type>-to-replay-$(date).lst`
               mkdir -p `to-replay/<object-type>/<swhid>/`
               echo $(kafka-object-as-string) > `to-replay/<object-type>/<swhid>/journal`
               echo $(postgresql-object-as-string) > `to-replay/<object-type>/<swhid>/postgresql`
               stop
             else (present in journal only)
               write <swhid> to `<object-type>-journal-only-$(date).lst`
               mkdir -p `journal-only/<object-type>/<swhid>/`
               echo $(kafka-object-as-string) > `journal-only/<object-type>/<swhid>/journal`

    """

    suffix_timestamp = str_now()
    for otype, objs in objects.items():
        logger.info(f"Processing {len(objs)} <{otype}> objects.")
        errors_counter = 0
        for obj in objs:
            obj_model, truncate_model_fn, is_equal, cs_get, pg_get = configure_obj_get(
                otype, obj, cs_storage, pg_storage)

            # Retrieve object in cassandra
            cs_obj = cs_get()
            # Due to some quirks in how cassandra stores the date for origin-visit and
            # origin-visit-status (round to milliseconds), we eventually adapt the
            # obj_model to compare journal object and cassandra object (for those
            # objects)
            truncated_obj_model = truncate_model_fn(obj_model)

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
            # For debug purposes only: check object representation written on disk
            # top_level_debug = join(top_level_path, "debug", "cassandra")
            # append_representation_on_disk_as_tree(top_level_debug, "journal_representation", obj_model, otype, unique_key)
            # append_representation_on_disk_as_tree(top_level_debug, "cassandra_representation", cs_obj, otype, unique_key)
            # report_debug_filepath = join(top_level_path, f"{otype}-debug)
            # append_swhid(report_debug_filepath, suffix_timestamp, swhid)

            if is_equal(cs_obj, truncated_obj_model):
                # kafka and cassandra objects match
                continue

            # let's look it up on postgresql
            pg_obj = pg_get()

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
                top_level_report_path = join(top_level_path, "to_replay")
                # object not found or at least different in cassandra
                # So we want to flush it on disk for later analysis
                flush_objects_to_disk(top_level_report_path, "cassandra_representation", cs_obj, otype, unique_key)
                # save object representation in dedicated tree
                append_representation_on_disk_as_tree(top_level_report_path, "journal_representation", obj, otype, unique_key)
                append_representation_on_disk_as_tree(top_level_report_path, "postgresql_representation", pg_obj, otype, unique_key)
                report_filepath = join(top_level_path, f"{otype}-swhid-toreplay")
                append_swhid(report_filepath, suffix_timestamp, swhid)
                continue

            # We did not found any object in cassandra and postgresql that matches what
            # we read in the journal

            top_level_report_path = join(top_level_path, "journal_only")
            flush_objects_to_disk(top_level_report_path, "cassandra_representation", cs_obj, otype, unique_key)
            flush_objects_to_disk(top_level_report_path, "postgresql_representation", pg_obj, otype, unique_key)
            # save object representation in dedicated tree
            append_representation_on_disk_as_tree(top_level_report_path, "journal_representation", obj, otype, unique_key)
            report_filepath = join(top_level_path, f"{otype}-swhid-in-journal-only")
            append_swhid(report_filepath, suffix_timestamp, swhid)

        logger.info(f"\tObjects missing in cassandra: {errors_counter}.")


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
def main(config_file):

    FORMAT = '[%(asctime)s] %(message)s'
    logging.basicConfig(format=FORMAT)
    logger.setLevel(logging.INFO)
    cassandra_logger = logging.getLogger("cassandra.cluster")
    cassandra_logger.setLevel(logging.ERROR)

    # Read the configuration out of the swh configuration file
    config = read_config(config_file)

    try:
        jn_storage = get_journal_client(**config["journal_client"])
    except ValueError as exc:
        logger.info(exc)
        exit(1)
    logger.info("🚧 Processing objects...")
    try:
        cs_storage = get_storage("cassandra", **config["cassandra"])
        pg_storage = get_storage("postgresql", **config["postgresql"])
        top_level_path = config["top_level_path"]
        process_fn = partial(process, cs_storage, pg_storage, top_level_path)
        # Run the client forever
        jn_storage.process(process_fn)
    except KeyboardInterrupt:
        logger.info("Called Ctrl-C, exiting.")


if __name__ == "__main__":
    main()
