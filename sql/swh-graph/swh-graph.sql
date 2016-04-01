\timing

create temporary view counts as
    select relname as tbl, reltuples::bigint as tuples
    from pg_class
    where relnamespace = 'public'::regnamespace
    and relkind = 'r'  -- ordinary table; no indexes, sequences, etc.
    order by relname;

create temporary table nodes (
    description  text,
    tuples       bigint not null
);

create temporary table edges (like nodes);

insert into nodes
    select 'content', sum(tuples)
    from counts
    where tbl in ('content', 'skipped_content');

insert into nodes
    select 'revision', tuples
    from counts
    where tbl = 'revision';

insert into nodes
    select 'release', tuples
    from counts
    where tbl = 'release';

insert into nodes
    select 'directory', tuples
    from counts
    where tbl = 'directory';

insert into edges
    select 'revision->revision', tuples
    from counts
    where tbl = 'revision_history';

insert into edges
    select 'revision->directory', tuples
    from counts
    where tbl = 'revision';

insert into edges
    select 'release->revision', tuples
    from counts
    where tbl = 'release';

insert into edges
    with edges as (
        select sum(coalesce(cardinality(dir_entries), 0))  as dir_edges,
               sum(coalesce(cardinality(file_entries), 0)) as file_edges,
               sum(coalesce(cardinality(rev_entries), 0))  as rev_edges
        from directory tablesample bernoulli (1.0)
        )
    select 'directory->directory' as description,
           dir_edges * 100 as tuples
    from edges
    union
    select 'directory->file' as description,
           file_edges * 100 as tuples
    from edges
    union
    select 'directory->revision' as description,
           rev_edges * 100 as tuples
    from edges;

select * from nodes;
select * from edges;

select 'nodes' as feat, sum(tuples) as card from nodes
union
select 'edges' as feat, sum(tuples) as card from edges;
