TABLES = [
    {
        'name': 'origin_visit',
        'columns': [
            ('origin', 'int'),
            ('visit', 'int'),
            ('date', 'timestamp'),
            ('status', 'string'),
            ('snapshot_id', 'int'),
        ],
        'partition': None
    },
    {
        'name': 'origin',
        'columns': [
            ('id', 'int'),
            ('type', 'string'),
            ('url', 'string'),
        ],
        'partition': None
    },
    {
        'name': 'snapshot_branches',
        'columns': [
            ('snapshot_id', 'int'),
            ('branch_id', 'int'),
        ],
        'partition': None
    },
    {
        'name': 'snapshot_branch',
        'columns': [
            ('object_id', 'int'),
            ('name', 'binary'),
            ('target', 'binary'),
            ('target_type', 'string'),
        ],
        'partition': None
    },
    {
        'name': 'snapshot',
        'columns': [
            ('object_id', 'int'),
            ('id', 'binary'),
        ],
        'partition': 'id'
    },
    {
        'name': 'release',
        'columns': [
            ('id', 'binary'),
            ('target', 'binary'),
            ('date', 'timestamp'),
            ('date_offset', 'int'),
            ('name', 'binary'),
            ('comment', 'binary'),
            ('author', 'int'),
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
            ('date', 'timestamp'),
            ('date_offset', 'int'),
            ('committer_date', 'timestamp'),
            ('committer_date_offset', 'int'),
            ('type', 'string'),
            ('directory', 'binary'),
            ('message', 'binary'),
            ('author', 'int'),
            ('committer', 'int'),
        ],
        'partition': 'id'
    },
    {
        'name': 'person',
        'columns': [  # Don't export personal information
            ('id', 'int'),
        ],
        'partition': 'id'
    },
    {
        'name': 'directory_entry_rev',
        'columns': [
            ('id', 'int'),
            ('target', 'binary'),
            ('name', 'binary'),
            ('perms', 'int'),
        ],
        'partition': 'target'
    },
    {
        'name': 'directory_entry_file',
        'columns': [
            ('id', 'int'),
            ('target', 'binary'),
            ('name', 'binary'),
            ('perms', 'int'),
        ],
        'partition': 'target'
    },
    {
        'name': 'directory_entry_dir',
        'columns': [
            ('id', 'int'),
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
            ('dir_entries', 'array<int>'),
            ('file_entries', 'array<int>'),
            ('rev_entries', 'array<int>'),
        ],
        'partition': 'id'
    },
    {
        'name': 'skipped_content',
        'columns': [
            ('sha1', 'binary'),
            ('sha1_git', 'binary'),
            ('length', 'int'),
        ],
        'partition': 'sha1_git'
    },
    {
        'name': 'content',
        'columns': [
            ('sha1', 'binary'),
            ('sha1_git', 'binary'),
            ('length', 'int'),
        ],
        'partition': 'sha1_git'
    },
]
