# Copyright (C) 2017  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information


from swh.model import hashutil
from swh.core import utils
from swh.core.config import SWHConfig
from swh.storage import get_storage


class RecomputeChecksums(SWHConfig):
    """Class in charge to recompute blob's hashes.

    """
    DEFAULT_CONFIG = {
        'storage': ('dict', {
            'cls': 'remote',
            'args': {
              'url': 'http://localhost:5002/'
            },
        }),
        # the set of checksums that should be computed. For
        # variable-length checksums a desired checksum length should also
        # be provided. An example of this config parameter could then be:
        # sha1, sha256, sha3:224, blake2:512
        'compute-new-checksums': (
            'list[str]', ['sha3:224', 'blake2:512']),
        # whether checksums that already exist in the DB should be
        # recomputed/updated or left untouched
        'recompute-existing-checksums': ('bool', 'False'),
        'batch': ('int', 100)
    }

    CONFIG_BASE_FILENAME = 'storage/recompute'

    def __init__(self):
        self.config = self.parse_config_file()
        self.storage = get_storage(**self.config['storage'])
        self.batch = self.config['batch']
        self.compute_new_checksums = self.config['compute-new-checkums']
        self.recompute_existing_checksums = self.config[
            'recompute_existing_checksums']

    def run(self, ids):
        """Given a list of ids, (re)compute a given set of checksums on
            contents available in our object storage, and update the
            content table accordingly.

            Args:
               ids ([bytes]): content identifier

        """
        # Determine what to update checksums
        checksums_algorithms = set(self.compute_new_checksums)
        if self.recompute_existing_checksums:
            checksums_algorithms = checksums_algorithms + set(
                hashutil.ALGORITHMS)

        keys_to_update = list(set(checksums_algorithms)-set(['sha1']))

        for content_ids in utils.grouper(ids, self.batch):
            contents = self.storage.content_get_metadata(content_ids)

            updated_contents = []
            for content in contents:
                raw_contents = list(self.storage.content_get([content['id']]))
                if not raw_contents:
                    continue

                raw_content = raw_contents[0]['data']
                updated_content = hashutil.hashdata(
                    raw_content, algo=checksums_algorithms)

                if updated_content['sha1'] != content['sha1']:
                    self.log.error(
                        "Corrupted content! The old sha1 %s and the new one %s don't match." % (
                            content['sha1'], updated_content['sha1']))
                    continue

                updated_contents.append(updated_content)

            # Update the contents with new hashes (except for sha1
            # since it's the primary key for now)
            self.storage.content_update(updated_contents, keys=keys_to_update)
