-- compute the number of objects available in each archive copy, according to
-- the content_archive table
--
-- DB: softwareheritage-archiver

select copies.key as archive, count(content_id)
from content_archive, jsonb_each(copies) as copies
where copies.value->>'status' = 'present'
group by copies.key;
