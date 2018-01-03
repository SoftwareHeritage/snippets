\timing on
set bytea_output='escape';

\copy content (sha1, sha1_git, sha256, blake2s256, length, ctime, status) to program 'pigz -c > content.csv.gz' (format csv);
\copy skipped_content (sha1, sha1_git, sha256, blake2s256, length, ctime, status, reason) to program 'pigz -c > skipped_content.csv.gz' (format csv);

\copy directory (id, dir_entries, file_entries, rev_entries) to program 'pigz -c > directory.csv.gz' (format csv);
\copy directory_entry_dir (id, target, name, perms) to program 'pigz -c > directory_entry_dir.csv.gz' (format csv);
\copy directory_entry_file (id, target, name, perms) to program 'pigz -c > directory_entry_file.csv.gz' (format csv);
\copy directory_entry_rev (id, target, name, perms) to program 'pigz -c > directory_entry_rev.csv.gz' (format csv);

\copy revision (id, date, date_offset, committer_date, committer_date_offset, type, directory, message, author, committer, synthetic, metadata, date_neg_utc_offset, committer_date_neg_utc_offset) to program 'pigz -c > revision.csv.gz' (format csv);
\copy revision_history (id, parent_id, parent_rank) to program 'pigz -c > revision_history.csv.gz' (format csv);
\copy release (id, target, date, date_offset, name, comment, author, synthetic, target_type, date_neg_utc_offset); to program 'pigz -c > release.csv.gz' (format csv);

\copy person (id, name, email) to program './anonymize-email | pigz -c > person.csv.gz' (format csv);
