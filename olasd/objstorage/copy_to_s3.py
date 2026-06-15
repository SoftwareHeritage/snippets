#!/usr/bin/env python
# coding: utf-8
import csv
import enum
import logging
import os
import sys

import yaml

from swh.model.model import Content
from swh.objstorage.factory import get_objstorage

DO_COPY = True

logger = logging.getLogger('__main__')

def get_objstorages_from_config():
    config = yaml.safe_load(open(os.environ['SWH_CONFIG_FILENAME'], 'r'))
    return {
        args['name']: get_objstorage(**args) for args in config['objstorages']
    }
    
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    logger.setLevel(logging.DEBUG)
    logging.getLogger('azure').setLevel(logging.CRITICAL)
    
    csv_filename = sys.argv[1]
    dst_name = sys.argv[2]
    objstorages = get_objstorages_from_config()
    dst_objstorage = objstorages.pop(dst_name)
    
    deleted_bytes = 0
    deleted_objects = 0
    notlocal_objects = 0
    notok_objects = 0
    total_objects = 0
    
    for line in csv.DictReader(open(csv_filename)):
        obj_id = {k: bytes.fromhex(v) if k.startswith('sha') else int(v) for k,v in line.items()}

        total_objects += 1

        if obj_id in dst_objstorage:
            hash = 'sha1'
            logger.info("Object %s:%s already exists in %s", hash, obj_id[hash].hex(), dst_name)
            continue
        
        for src_name, objstorage in objstorages.items():
            if obj_id in objstorage:
                logger.info("Fetching sha1:%s from %s", obj_id['sha1'].hex(), src_name)
                obj = Content.from_data(objstorage.get(obj_id))
                fetched = obj.hashes()
                check_ok = False
                for hash in obj_id:
                    if hash in fetched:
                        if obj_id[hash] != fetched[hash]:
                            logger.warning("Hash corrupted: fetched %s:%s from %s yielded %s:%s", hash, obj_id[hash].hex(), src_name, hash, fetched[hash].hex())
                else:
                    check_ok = True
                            
                if not check_ok:
                    continue
                
                if DO_COPY:
                    dst_objstorage.add(obj.data, obj_id=obj_id)
                hash = 'sha1'
                logger.info("Copied %s:%s from %s to %s", hash, obj_id[hash].hex(), src_name, dst_name)
                break
        else:
            hash='sha1'
            logger.warning("Object %s:%s unusable", hash, obj_id[hash].hex())
