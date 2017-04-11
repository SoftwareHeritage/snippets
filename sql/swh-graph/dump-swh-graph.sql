\copy directory (id, dir_entries, file_entries, rev_entries, object_id) to program 'pigz -c > directory.csv.gz' (format csv);
\copy directory_entry_dir (id, name, target) to program 'pigz -c > directory_entry_dir.csv.gz' (format csv);
\copy directory_entry_file (id, name, target) to program 'pigz -c > directory_entry_file.csv.gz' (format csv);
\copy directory_entry_rev (id, name, target) to program 'pigz -c > directory_entry_rev.csv.gz' (format csv);
\copy revision (id, directory, object_id) to program 'pigz -c > revision.csv.gz' (format csv);
\copy revision_history (id, parent_id, parent_rank) to program 'pigz -c > revision_history.csv.gz' (format csv);
\copy release (id, target, target_type, object_id) to program 'pigz -c > release.csv.gz' (format csv);
