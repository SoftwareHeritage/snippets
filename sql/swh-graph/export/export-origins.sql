\copy (SELECT 'swh:1:ori:' || encode(digest(url, 'sha1'), 'hex') as pid, url FROM origin) TO STDOUT WITH CSV DELIMITER ' ';
