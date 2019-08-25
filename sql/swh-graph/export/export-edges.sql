\copy (SELECT 'swh:1:dir:' || encode(directory.id, 'hex') as source, 'swh:1:cnt:' || encode(target, 'hex') as dest FROM directory CROSS JOIN UNNEST(file_entries) as t(file_id) INNER JOIN directory_entry_file ON directory_entry_file.id = file_id ORDER BY dest) TO STDOUT WITH CSV DELIMITER ' ';

\copy (SELECT 'swh:1:dir:' || encode(directory.id, 'hex') as source, 'swh:1:dir:' || encode(target, 'hex') as dest FROM directory CROSS JOIN UNNEST(dir_entries) as t(dir_id) INNER JOIN directory_entry_dir ON directory_entry_dir.id = dir_id ORDER BY dest) TO STDOUT WITH CSV DELIMITER ' ';

\copy (SELECT 'swh:1:dir:' || encode(directory.id, 'hex') as source, 'swh:1:rev:' || encode(target, 'hex') as dest FROM directory CROSS JOIN UNNEST(rev_entries) as t(rev_id) INNER JOIN directory_entry_rev ON directory_entry_rev.id = rev_id ORDER BY dest) TO STDOUT WITH CSV DELIMITER ' ';

\copy (SELECT 'swh:1:ori:' || encode(digest(url, 'sha1'), 'hex') as source, 'swh:1:snp:' || encode(snapshot.id, 'hex') as dest FROM origin_visit INNER JOIN snapshot on origin_visit.snapshot = snapshot.id INNER JOIN origin on origin_visit.origin = origin.id ORDER BY dest) TO STDOUT WITH CSV DELIMITER ' ';

\copy (SELECT 'swh:1:rel:' || encode(id, 'hex') as source, 'swh:1:rev:' || encode(target, 'hex') as dest FROM release ORDER BY dest) TO STDOUT WITH CSV DELIMITER ' ';

\copy (SELECT 'swh:1:rev:' || encode(id, 'hex') as source, 'swh:1:dir:' || encode(directory, 'hex') as dest FROM revision ORDER BY dest) TO STDOUT WITH CSV DELIMITER ' ';

\copy (SELECT 'swh:1:rev:' || encode(id, 'hex') as source, 'swh:1:rev:' || encode(parent_id, 'hex') as dest FROM revision_history ORDER BY dest) TO STDOUT WITH CSV DELIMITER ' ';

\copy (SELECT 'swh:1:snp:' || encode(snapshot.id, 'hex') as source, 'swh:1:rev:' || encode(snapshot_branch.target, 'hex') as dest FROM snapshot_branch INNER JOIN snapshot_branches on snapshot_branches.branch_id = snapshot_branch.object_id INNER JOIN snapshot on snapshot_branches.snapshot_id = snapshot.object_id ORDER BY dest) TO STDOUT WITH CSV DELIMITER ' ';
