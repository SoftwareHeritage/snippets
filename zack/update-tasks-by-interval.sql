-- summarize the active update tasks by update interval
--
-- DB: softwareheritage-scheduler

select current_interval, count(*)
from task
group by current_interval
order by current_interval;

-- sample output
--
-- current_interval |  count
-- ------------------+----------
-- 12:00:00         |    27578
-- 24:00:00         |    60094
-- 2 days           |    91370
-- 4 days           |   124005
-- 8 days           |   877766
-- 16 days          |   896318
-- 32 days          |  8427918
-- 64 days          | 12533398
-- (8 rows)
