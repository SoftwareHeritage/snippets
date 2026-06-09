create external table c stored as parquet location '/srv/softwareheritage/ssd/data/vlorentz/datasets/2026-03-02/aggregate/contents';

copy (select year, avg(length), median(length) from (select date_part('year', first_occurrence_timestamp) as year, length from c where first_occurrence_timestamp is not null) group by year order by year) to '/srv/softwareheritage/ssd/data/vlorentz/datasets/2026-03-02/content_lengths_by_year.csv';
