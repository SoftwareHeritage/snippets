import os

class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

JOURNAL_PASSWORD = os.environ['JOURNAL_PASSWORD']
JOURNAL_USER = os.environ['JOURNAL_USER']
BROKER = os.environ['JOURNAL_HOST'] + ":" + os.environ['JOURNAL_PORT']
PG_PASSWORD = os.environ['PG_PASSWORD']
PG_USER = os.environ['PG_USER']
PG_HOST = os.environ['PG_HOST']
CS_PASSWORD = os.environ['CS_STAGING_PASSWORD']
CS_USER = os.environ['CS_USER']
CS_HOST = os.environ['CS_HOST']

db = f"host={PG_HOST} port=5432 user={PG_USER} dbname=swh password={PG_PASSWORD}"
pg_staging_storage_conf = {'db': db ,
 'objstorage': {'cls': 'noop'},
 }

client_cfg = {
    "cls": "kafka",
    "brokers": [BROKER],
    "group_id": "swh-gsa-test",
    "object_types": ["content"],
    #   - content
    #   - directory
    #   - extid
    #   - origin
    #   - origin_visit
    #   - origin_visit_status
    #   - raw_extrinsic_metadata
    #   - release
    #   - revision
    #   - skipped_content
    #   - snapshot
    "sasl.username": JOURNAL_USER,
    "sasl.password": JOURNAL_PASSWORD,
    "security.protocol": "sasl_ssl",
    "sasl.mechanism": "SCRAM-SHA-512",
    "message.max.bytes": "524288000",
    "stop_after_objects": 10,
    "batch_size": 10,
    "privileged": True,
}

cs_prod_storage_conf = {'hosts': ['cassandra01.internal.softwareheritage.org',
          'cassandra02.internal.softwareheritage.org',
          'cassandra03.internal.softwareheritage.org',
          'cassandra04.internal.softwareheritage.org',
          'cassandra05.internal.softwareheritage.org',
          'cassandra06.internal.softwareheritage.org',
          'cassandra07.internal.softwareheritage.org',
          'cassandra08.internal.softwareheritage.org',
          'cassandra09.internal.softwareheritage.org',
          'cassandra10.internal.softwareheritage.org'],
  'keyspace': 'swh',
  'consistency_level': 'LOCAL_QUORUM',
  'auth_provider':
      {'cls': 'cassandra.auth.PlainTextAuthProvider',
      'password': CS_PASSWORD,
      'username': CS_USER},
      'directory_entries_insert_algo': 'batch',
      'objstorage': {'cls': 'noop'}
}

cs_staging_storage_conf = {'hosts': ['cassandra1.internal.staging.swh.network',
    'cassandra2.internal.staging.swh.network',
    'cassandra3.internal.staging.swh.network'],
  'keyspace': 'swh',
  'consistency_level': 'LOCAL_QUORUM',
  'auth_provider':
      {'cls': 'cassandra.auth.PlainTextAuthProvider',
      'password': CS_PASSWORD,
      'username': CS_USER},
      'directory_entries_insert_algo': 'batch',
      'objstorage': {'cls': 'noop'}
}
