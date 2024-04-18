#!/usr/bin/env python3

"""Journal client to process objects from kafka to check cassandra object consistency.

"""

import click
from yaml import safe_load

from itertools import tee
from os import makedirs, environ
from os.path import join
from swh.journal.client import get_journal_client
from swh.model.model import (
    Directory, Release, Revision, Origin, Content,
    OriginVisit, OriginVisitStatus, SkippedContent,
    RawExtrinsicMetadata, ExtID, Snapshot, DirectoryEntry
)
from swh.storage import get_storage
from swh.storage.algos import directory as dir_algos, snapshot as snp_algos, origin as ori_algos
from functools import partial
import attr
from types import GeneratorType
from swh.journal.serializers import pprint_key
from swh.storage.interface import StorageInterface
from swh.storage.utils import round_to_milliseconds
from swh.model.hashutil import hash_to_hex, hash_git_data
from datetime import datetime
import logging

from typing import Any, Callable, Dict, Iterator, List, Optional, Tuple


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


def append_swhid(filename, suffix_date, swhid, unique_key):
    """Write the swhid identifier to a filename with a suffix_date.

    For some objects (e.g. origin-visit, origin-visit-status, ...), we don't have a real
    swhid (it's a dict representation), so we'll also write the (different than swhid)
    unique key first. That will be helpful to do a join on the other part of the
    filesystem to retrieve the details on the objects.

    """
    msg = f"{swhid}\n"
    if swhid != unique_key:
        msg = f"{unique_key}\n{msg}"

    with open(f"{filename}-{suffix_date}.lst",'a') as f:
        f.write(msg)


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
        if isinstance(obj, GeneratorType):
            obj = list(obj)
        f.write(f"{repr(obj)}\n")


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


def compare_content(obj_ref: Content, obj_model_ref: Content) -> bool:
    """Content model comparison without ctime. This is returned as None by the cassandra
    backend [1].

    This is set though from the Content.from_dict method if present (and it is present
    in journal entries).

    [1] https://gitlab.softwareheritage.org/swh/devel/swh-storage/-/blob/master/swh/storage/cassandra/storage.py?ref_type=heads#L415

    [2] https://gitlab.softwareheritage.org/swh/devel/swh-model/-/blob/master/swh/model/model.py#L1451

    .. code::

       In [3]: content_d = {'sha1': b'\xd0\x1f=}\xdb\x15$\xb6\x15Z=\xa5\x80\x96\xc0\xe7\xdc\xe04A', 'sha1_git': b'\x00X\xe0\xdb\x8c\xcc:\x16X\xaa\xf8\xb24\x1e\x1a\x16\x03\x0c]\x1d', 'sha256': b'<+T\x90\xe6\x95c\xe5\x9av\xcdV\xfa\xb1Gp\xfc\xe3\x8a
          ...: j\xeaZ$\xec\xa9\xf0M[\x99\xefr\xeb', 'blake2s256': b"iq`E0RI\xd9\x9eG\xbcJU\xbdB\xa5\xd0\xea\xe9]y\xf5\xfaX\xfcWN\x82\xb8CR'", 'length': 11266, 'status': 'visible', 'ctime': datetime.datetime(2018, 4, 5, 20, 44, 3, 832543, tzinfo=d
          ...: atetime.timezone.utc)}

       In [4]: Content.from_dict(content_d)
       Out[4]: Content(sha1=hash_to_bytes('d01f3d7ddb1524b6155a3da58096c0e7dce03441'), sha1_git=hash_to_bytes('0058e0db8ccc3a1658aaf8b2341e1a16030c5d1d'), sha256=hash_to_bytes('3c2b5490e69563e59a76cd56fab14770fce38a6aea5a24eca9f04d5b99ef72eb'), blake2s256=hash_to_bytes('69716045305249d99e47bc4a55bd42a5d0eae95d79f5fa58fc574e82b8435227'), length=11266, status='visible', data=None, ctime=datetime.datetime(2018, 4, 5, 20, 44, 3, 832543, tzinfo=datetime.timezone.utc))

       In [5]: Content.from_dict(content_d).ctime
       Out[5]: datetime.datetime(2018, 4, 5, 20, 44, 3, 832543, tzinfo=datetime.timezone.utc)

    """
    return attr.evolve(obj_ref, ctime=None) == attr.evolve(obj_model_ref, ctime=None)


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


def compare_raw_extrinsic_metadata(obj_ref: RawExtrinsicMetadata, obj_model_ref: RawExtrinsicMetadata) -> bool:
    """RawExtrinsicMetadata model comparison.

    RawExtrinsicMetadata: RawExtrinsicMetadata objects, authority and fetcher contains
    an old metadata field. It is not serialized the same way when empty. (Empty dict in
    journal representation, None in storage representation)

    """

    authority_ref = attr.evolve(obj_ref.authority, metadata=None)
    fetcher_ref = attr.evolve(obj_ref.fetcher, metadata=None)

    authority_model_ref = attr.evolve(obj_model_ref.authority, metadata=None)
    fetcher_model_ref = attr.evolve(obj_model_ref.fetcher, metadata=None)


    return attr.evolve(obj_ref, authority=authority_ref, fetcher=fetcher_ref) == \
        attr.evolve(obj_model_ref, authority=authority_model_ref, fetcher=fetcher_model_ref)


def compare_object(obj_ref, obj_model_ref) -> bool:
    return obj_ref == obj_model_ref


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


def content_get_all_hashes(content_get_fn: Callable, obj_model: Content) -> Iterator[Optional[Content]]:
    """Retrieve in the backend the content from multiple calls (one by hash algo) with
    each of its hash. If any content is missing, consider the content to be replayed.

    """
    found = []
    # We'll iterate over all hashes and check for it in the backend
    for hash_key, hash_id in obj_model.hashes().items():
        found.extend(content for content in content_get_fn([hash_id], algo=hash_key))

    # If any is missing, consider it not found
    if None in found:
        yield None
    # Else yield all found objects
    yield from found


def journal_client_directory_get(storage: StorageInterface, ids: List[bytes]) -> List[Optional[Tuple[bool, Directory]]]:
    """Specific journal client directory_get function to retrieve directory with ids
    from the storage.

    As we are reading the full journal, we may hit "invalid" directories (with
    duplicated entries) which did not pass the model checks (because it did not exist
    yet). Those are not supported by the Directory model and raise. We still want to
    check their existence (in the right model format) in the backend.

    """
    directory_get_fn = dir_algos.directory_get_many_with_possibly_duplicated_entries
    for directory in directory_get_fn(storage, ids):
        # directory variable's type: Optional[Tuple[bool, Directory]]
        yield directory[1] if directory else None


def configure_obj_get(otype: str, obj: Dict, cs_storage, pg_storage):
    """Configure how to retrieve the object with type otype. Depending on the object
    type, this returns a tuple of the object model, a truncated model object function,
    an equality function, a cassandra getter function and a storage getter function.

    """
    truncate_obj_model_fn = identity
    is_equal_fn = compare_object

    if otype == "content":
        obj_model = Content.from_dict(obj)
        cs_get = partial(content_get_all_hashes, cs_storage.content_get, obj_model)
        pg_get = partial(content_get_all_hashes, pg_storage.content_get, obj_model)
        is_equal_fn = compare_content
    elif otype == "directory":
        try:
            # Convert the dict object into a valid Directory model object
            obj_model = Directory.from_dict(obj)
        except ValueError:
            # But some old directory objects have duplicated entries and failed to be
            # converted so fallback to this method when needed
            _, obj_model = Directory.from_possibly_duplicated_entries(
                id=obj["id"],
                entries=tuple(
                    DirectoryEntry.from_dict(entry) for entry in obj["entries"]
                ),
            )
        ids = [obj_model.id]
        cs_get = partial(journal_client_directory_get, cs_storage, ids)
        pg_get = partial(journal_client_directory_get, pg_storage, ids)
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
        is_equal_fn = compare_raw_extrinsic_metadata
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


def is_iterable(obj: Any) -> bool:
    """Is the object an iterable (list or generator)."""
    return isinstance(obj, (list, GeneratorType))


def search_for_obj_model(is_equal_fn, obj_model, obj_iterable) -> Tuple[Optional[Any], Iterator]:
    """This looks up the obj_model in obj_iterable.

    Returns:
        a tuple of the object found if found or None and the duplicated original
        iterable (so it can be reused for the disk flush routine)

    """
    if isinstance(obj_iterable, GeneratorType):
        obj_iterable, obj_iterable2 = tee(obj_iterable, 2)
    else:
        obj_iterable, obj_iterable2 = obj_iterable, obj_iterable
    for obj in obj_iterable:
        if obj is None:
            # some functions (e.g. Release_get, content_get,) ... may return None object
            continue
        if is_equal_fn(obj, obj_model):
            return obj, obj_iterable2
    # Let's make it clear we did not find the object, and return the eventual unconsumed
    # generator so we can flush it to disk later
    return None, obj_iterable2


def process(cs_storage, pg_storage, top_level_path, objects, suffix_timestamp, debug=False):
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
        objects: List of objects read from the journal
        suffix_timestamp: A suffix timestamp used to append to the manifest file where
            we list the problematic objects.append($0)
        debug: Bool to add extra behavior for troubleshoot purposes (should be False in
            production, the default)

    Pseudo code:

        for all object in journal
          read object in cassandra
            it exists, we found it:
              nothing to do, stop
            else (it does not exist):
             read object in postgresql
             it exists, we found it:
               write <swhid> to `<object-type>-to-replay-<suffix_timestamp>.lst`
               mkdir -p `to-replay/<object-type>/<swhid>/`
               echo $(kafka-object-as-string) > `to-replay/<object-type>/<swhid>/journal`
               echo $(postgresql-object-as-string) > `to-replay/<object-type>/<swhid>/postgresql`
               stop
             else (present in journal only)
               write <swhid> to `<object-type>-journal-only-<suffix_timestamp>.lst`
               mkdir -p `journal-only/<object-type>/<swhid>/`
               echo $(kafka-object-as-string) > `journal-only/<object-type>/<swhid>/journal`

    """
    report_path_debug = join(top_level_path, "debug", "cassandra")
    report_path_to_replay = join(top_level_path, "to_replay")
    report_path_journal_only = join(top_level_path, "journal_only")

    for otype, objs in objects.items():
        logger.info(f"Processing {len(objs)} <{otype}> objects.")
        errors_counter = 0
        for obj in objs:
            obj_model, truncate_model_fn, is_equal_fn, cs_get, pg_get = configure_obj_get(
                otype, obj, cs_storage, pg_storage)

            logger.debug("Retrieve object in cassandra")
            # Retrieve object in cassandra
            cs_obj = cs_get()
            # Due to some quirks in how cassandra stores the date for origin-visit and
            # origin-visit-status (round to milliseconds), we eventually adapt the
            # obj_model to compare journal object and cassandra object (for those
            # objects)
            truncated_obj_model = truncate_model_fn(obj_model)

            iterable = is_iterable(cs_obj)
            if iterable:
                logger.debug("List of Objects found, looking for unique object in list")
                cs_obj, cs_obj_iterable = search_for_obj_model(is_equal_fn, truncated_obj_model, cs_obj)

            # Some objects have no swhid...
            swhid = swhid_str(obj_model)
            # so we compute a unique key without the swhid (when need, e.g origin_visit, origin_visit_status,...)
            unique_key = swhid_key(obj_model)
            # For debug purposes only: check object representation written on disk
            if debug:
                append_representation_on_disk_as_tree(report_path_debug, "journal_representation", obj_model, otype, unique_key)
                append_representation_on_disk_as_tree(report_path_debug, "cassandra_representation", cs_obj, otype, unique_key)
                report_debug_filepath = join(top_level_path, f"{otype}-debug")
                append_swhid(report_debug_filepath, suffix_timestamp, swhid, unique_key)
                if iterable:
                    # Allow reading iterable multiple times (if needed)
                    cs_obj, cs_obj_iterable = tee(cs_obj_iterable, 2)

            # Due to some quirks in how cassandra stores the date for origin-visit and
            # origin-visit-status (round to milliseconds), we eventually adapt the
            # obj_model to compare journal object and cassandra object (for those
            # objects)
            truncated_obj_model = truncate_model_fn(obj_model)

            iterable = is_iterable(cs_obj)
            if iterable:
                logger.debug("List of Objects found, looking for unique object in list")
                cs_obj, cs_obj_iterable = search_for_obj_model(is_equal_fn, truncated_obj_model, cs_obj)

            if cs_obj is not None and is_equal_fn(cs_obj, truncated_obj_model):
                logger.debug("Object found in cassandra, do nothing")
                # kafka and cassandra objects match
                continue

            logger.debug("Object not found in cassandra, look it up in postgresql")
            # We'll need to flush the read representation to disk, so revert the
            # reference to either the list or the generator it was
            if cs_obj is None and iterable:
                logger.debug("Object is an iterable, reset iterable for disk flush op")
                cs_obj = cs_obj_iterable

            logger.debug("Lookup object in postgresql")
            # let's look it up on postgresql
            pg_obj = pg_get()

            iterable = is_iterable(pg_obj)
            if iterable:
                logger.debug("List of Objects found, looking for unique object in list")
                pg_obj, pg_obj_iterable = search_for_obj_model(is_equal_fn, obj_model, pg_obj)

            if pg_obj is not None and is_equal_fn(pg_obj, obj_model):
                logger.debug("Object missing in cassandra and present in postgresql")
                # kafka and postgresql objects match
                errors_counter += 1
                # object not found or at least different in cassandra
                # So we want to flush it on disk for later analysis
                logger.debug("Flush representations to disk.")
                append_representation_on_disk_as_tree(report_path_to_replay, "cassandra_representation", cs_obj, otype, unique_key)
                # save object representation in dedicated tree
                append_representation_on_disk_as_tree(report_path_to_replay, "journal_representation", obj, otype, unique_key)
                append_representation_on_disk_as_tree(report_path_to_replay, "postgresql_representation", pg_obj, otype, unique_key)
                report_filepath = join(top_level_path, f"{otype}-swhid-toreplay")
                append_swhid(report_filepath, suffix_timestamp, swhid, unique_key)
                continue

            logger.debug("Object only present in journal")
            # We'll need to flush the read representation to disk, so revert the
            # reference to either the list or the generator it was
            if pg_obj is None and iterable:
                logger.debug("Object is an iterable, reset iterable for disk flush op")
                pg_obj = pg_obj_iterable

            # We did not found any object in cassandra and postgresql that matches what
            # we read in the journal, we want to flush all that we've read to disk

            logger.debug("Flush representations found to disk")
            append_representation_on_disk_as_tree(report_path_journal_only, "cassandra_representation", cs_obj, otype, unique_key)
            append_representation_on_disk_as_tree(report_path_journal_only, "postgresql_representation", pg_obj, otype, unique_key)
            # save object representation in dedicated tree
            append_representation_on_disk_as_tree(report_path_journal_only, "journal_representation", obj, otype, unique_key)
            report_filepath = join(top_level_path, f"{otype}-swhid-in-journal-only")
            append_swhid(report_filepath, suffix_timestamp, swhid, unique_key)

        logger.info(f"\tObjects missing in cassandra: {errors_counter}.")


def configure_logger(logger, debug_flag):
    """Configure logger according to environment variable or debug_flag."""
    FORMAT = '[%(asctime)s] %(message)s'
    logging.basicConfig(format=FORMAT)
    if "LOG_LEVEL" in environ:
        log_level_str = environ["LOG_LEVEL"].upper()
    elif debug_flag:
        log_level_str = "DEBUG"
    else:
        log_level_str = "INFO"

    log_level = getattr(logging, log_level_str)
    logger.setLevel(log_level)

    cassandra_logger = logging.getLogger("cassandra.cluster")
    cassandra_logger.setLevel(logging.ERROR)


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
    "--debug",
    "-d",
    "debug_flag",
    is_flag=True,
    default=False,
    help="Flag for debug purposes"
)
def main(config_file, debug_flag):
    # Let's configure the logger
    configure_logger(logger, debug_flag)

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
        process_fn = partial(
            process, cs_storage, pg_storage, top_level_path,
            suffix_timestamp=str_now(),
            debug=debug_flag
        )
        # Run the client forever
        jn_storage.process(process_fn)
    except KeyboardInterrupt:
        logger.info("Called Ctrl-C, exiting.")


if __name__ == "__main__":
    main()
