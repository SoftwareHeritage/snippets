-- compute the number of visits that each SWH origin went through
-- report them grouped by number of visits, in decreasing order
with origin_visits as (
     select origin, count(visit) as visits
     from origin_visit
     group by origin
     )
select count(origin), visits
from origin_visits
group by visits
order by visits desc;

-- sample output
-- 
-- count   | visits
-- --------+--------
--       1 |      7
--       7 |      6
--    2841 |      5
-- 2672450 |      4
-- 8121753 |      3
--  432803 |      2
--  569244 |      1
