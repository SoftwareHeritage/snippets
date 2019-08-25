\copy (SELECT 'swh:1:ori:' || encode(digest(url, 'sha1'), 'hex') as pid, url FROM origin ORDER BY url) TO STDOUT WITH CSV DELIMITER ' ';
