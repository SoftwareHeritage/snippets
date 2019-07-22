TABLES = [
    {
        'name': 'origin_visit',
        'columns': [
            ('origin', 'bigint'),
            ('visit', 'bigint'),
            ('date', 'bigint'),
            ('status', 'string'),
            ('metadata', 'string'),
            ('snapshot_id', 'bigint'),
        ],
        'partition': None
    },
    {
        'name': 'origin',
        'columns': [
            ('id', 'bigint'),
            ('type', 'string'),
            ('url', 'string'),
        ],
        'partition': None
    },
    {
        'name': 'snapshot_branches',
        'columns': [
            ('snapshot_id', 'bigint'),
            ('branch_id', 'bigint'),
        ],
        'partition': None
    },
    {
        'name': 'snapshot_branch',
        'columns': [
            ('object_id', 'bigint'),
            ('name', 'binary'),
            ('target', 'binary'),
            ('target_type', 'string'),
        ],
        'partition': None
    },
    {
        'name': 'snapshot',
        'columns': [
            ('object_id', 'bigint'),
            ('id', 'binary'),
        ],
        'partition': 'id'
    },
    {
        'name': 'release',
        'columns': [
            ('id', 'binary'),
            ('target', 'binary'),
            ('date', 'bigint'),
            ('date_offset', 'smallint'),
            ('name', 'binary'),
            ('comment', 'binary'),
            ('author', 'bigint'),
            ('target_type', 'string'),
        ],
        'partition': 'id'
    },
    {
        'name': 'revision_history',
        'columns': [
            ('id', 'binary'),
            ('parent_id', 'binary'),
            ('parent_rank', 'int'),
        ],
        'partition': 'id'
    },
    {
        'name': 'revision',
        'columns': [
            ('id', 'binary'),
            ('date', 'bigint'),
            ('date_offset', 'smallint'),
            ('committer_date', 'bigint'),
            ('committer_date_offset', 'smallint'),
            ('type', 'string'),
            ('directory', 'binary'),
            ('message', 'binary'),
            ('author', 'bigint'),
            ('committer', 'bigint'),
        ],
        'partition': 'id'
    },
    {
        'name': 'person',
        'columns': [  # Don't export personal information
            ('id', 'bigint'),
        ],
        'partition': 'id'
    },
    {
        'name': 'directory_entry_rev',
        'columns': [
            ('id', 'bigint'),
            ('target', 'binary'),
            ('name', 'binary'),
            ('perms', 'int'),
        ],
        'partition': 'target'
    },
    {
        'name': 'directory_entry_file',
        'columns': [
            ('id', 'bigint'),
            ('target', 'binary'),
            ('name', 'binary'),
            ('perms', 'int'),
        ],
        'partition': 'target'
    },
    {
        'name': 'directory_entry_dir',
        'columns': [
            ('id', 'bigint'),
            ('target', 'binary'),
            ('name', 'binary'),
            ('perms', 'int'),
        ],
        'partition': 'target'
    },
    {
        'name': 'directory',
        'columns': [
            ('id', 'binary'),
            ('dir_entries', 'array<bigint>'),
            ('file_entries', 'array<bigint>'),
            ('rev_entries', 'array<bigint>'),
        ],
        'partition': 'id'
    },
    {
        'name': 'skipped_content',
        'columns': [
            ('sha1', 'binary'),
            ('sha1_git', 'binary'),
            ('length', 'bigint'),
        ],
        'partition': 'sha1_git'
    },
    {
        'name': 'content',
        'columns': [
            ('sha1', 'binary'),
            ('sha1_git', 'binary'),
            ('length', 'bigint'),
        ],
        'partition': 'sha1_git'
    },
]
