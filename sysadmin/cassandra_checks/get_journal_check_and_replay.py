#!/usr/bin/env python3

from swh.journal.client import get_journal_client
from swh.model.model import Release, Revision, Origin, Content, OriginVisit, OriginVisitStatus, SkippedContent, RawExtrinsicMetadata, ExtID
from swh.model.swhids import CoreSWHID, ObjectType
from swh.model import hashutil
from swh.storage import get_storage
from swh.storage.algos import directory, snapshot, origin as algos_origin
from config import *
import hashlib
from swh.core.api.classes import PagedResult
from functools import partial
import attr
from types import GeneratorType


def round_to_milliseconds(date):
    """Round datetime to milliseconds before insertion, so equality doesn't fail after a
    round-trip through a DB (eg. Cassandra)

    """
    return date.replace(microsecond=(date.microsecond // 1000) * 1000)

def process(objects):
    cs_storage = get_storage("cassandra", **cs_staging_storage_conf)
    pg_storage = get_storage("postgresql", **pg_staging_storage_conf)
    for otype, objs in objects.items():
        for obj in objs:
            print(f"{bcolors.BOLD}{bcolors.OKGREEN}{'📥 ##########':<12} {otype.upper()}{bcolors.ENDC}")
            swhidType = None
            swhid = None
            cs_hash = None
            pg_hash = None
            id = None
            sha1 = None
            hash = None
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
                print(stargs)
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
                sha1 = obj_model.sha1
                stargs = {"sha1":sha1}
            elif otype == "snapshot":
                obj_model = Snapshot.from_dict(obj)
                # snapshot_get return the dict and not the swh model object
                # (deal with huge snapshot)
                cs_get = partial(snapshot.snapshot_get_all_branches, cs_storage)
                pg_get = partial(snapshot.snapshot_get_all_branches, pg_storage)
                id = obj_model.id
                stargs = id
            print(f"###### {obj_model=}")
            #print(obj_model)
            #print(len(stargs))
            #print(type(stargs))
            #print(stargs)
            cs_obj = cs_get(stargs)
            pg_obj = pg_get(stargs)

            if isinstance(cs_obj, (list, GeneratorType)):
                for _cs_obj in cs_obj:
                    if otype == "origin_visit_status":
                        date = round_to_milliseconds(obj_model.date)
                        obj_model = attr.evolve(obj_model, date=date)
                    if _cs_obj == obj_model:
                        cs_obj = _cs_obj
                        break
            if hasattr(obj_model, 'swhid'):
                cs_swhid = str(cs_obj.swhid())
                jn_swhid = str(obj_model.swhid())
                print(f"{bcolors.BOLD}{bcolors.OKGREEN}{'🗄️  jn_swhid':<14}{bcolors.ENDC} {jn_swhid}")
                print(f"{bcolors.BOLD}{bcolors.OKGREEN}{'🗄️  cs_swhid':<14}{bcolors.ENDC} {cs_swhid}")
            else:
                if otype == "extid":
                    print(cs_obj._compute_hash_from_attributes())
                    print(obj_model._compute_hash_from_attributes())
                if otype in ("origin_visit","origin_visit_status"):
                    date = round_to_milliseconds(obj_model.date)
                    obj_model = attr.evolve(obj_model, date=date)
                    print(obj_model == cs_obj)
                print(cs_obj)
                print(obj_model)

try:
    jn_storage = get_journal_client(**client_cfg)
except ValueError as exc:
    print(exc)
    exit(1)
print(f"{bcolors.OKGREEN}🚧 Processing objects...{bcolors.ENDC}")
try:
    # Run the client forever
    jn_storage.process(process)
except KeyboardInterrupt:
    print("Called Ctrl-C, exiting.")
