\copy directory (id, dir_entries, file_entries, rev_entries, object_id) to program 'gzip -c > directory.csv.gz' (format csv);
\copy directory_entry_dir (id, name, target) to program 'gzip -c > directory_entry_dir.csv.gz' (format csv);
\copy directory_entry_file (id, name, target) to program 'gzip -c > directory_entry_file.csv.gz' (format csv);
\copy directory_entry_rev (id, name, target) to program 'gzip -c > directory_entry_rev.csv.gz' (format csv);
\copy revision (id, directory, object_id) to program 'gzip -c > revision.csv.gz' (format csv);
\copy revision_history (id, parent_id, parent_rank) to program 'gzip -c > revision_history.csv.gz' (format csv);
\copy release (id, target, object_id) to program 'gzip -c > revision_history.csv.gz' (format csv);
