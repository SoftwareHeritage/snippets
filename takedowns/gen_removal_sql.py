# Copyright (C) 2021  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

import pickle
import sys

from list_objects import Graph

SQL_TEMPLATE = """
BEGIN;
create temp table objects_to_remove (type text not null, id bytea not null) on commit drop;

insert into objects_to_remove (type, id) values %s;

create temp table origins_to_remove
  on commit drop
  as
    select origin.id from origin
    inner join objects_to_remove otr on digest(url, 'sha1') = otr.id and otr.type = 'ori';

copy (select '-- origin_visit_status') to stdout;
copy (select '') to stdout;

copy (select * from origin_visit_status ovs where ovs.origin in (select id from origins_to_remove)) to stdout with (format csv, header);

copy (select '') to stdout;

--delete from origin_visit_status ovs
--  where ovs.origin in (select id from origins_to_remove);

copy (select '-- origin_visit') to stdout;
copy (select '') to stdout;

copy (select * from origin_visit ov where ov.origin in (select id from origins_to_remove)) to stdout with (format csv, header);

copy (select '') to stdout;

--delete from origin_visit ov
--  where ov.origin in (select id from origins_to_remove);

copy (select '-- origin') to stdout;
copy (select '') to stdout;

copy (select * from origin o where o.id in (select id from origins_to_remove)) to stdout with (format csv, header);

copy (select '') to stdout;

--delete from origin o
--  where o.id in (select id from origins_to_remove);




copy (select '-- full snapshot data') to stdout;
copy (select '') to stdout;

copy (select s.id, sb.name, sb.target_type, sb.target from snapshot s left join snapshot_branches sbs on s.object_id = sbs.snapshot_id inner join snapshot_branch sb on sbs.branch_id = sb.object_id where s.id in (select id from objects_to_remove where type='snp')) to stdout with (format csv, header);

copy (select '') to stdout;

create temp table snp_to_remove
  on commit drop
  as
    select object_id as snapshot_id
    from snapshot s
    inner join objects_to_remove otr on s.id = otr.id and otr.type = 'snp';


create temp table snp_branch_to_remove
  on commit drop
  as
    select branch_id
    from snapshot_branches sb
    where snapshot_id in (select snapshot_id from snp_to_remove);

copy (select '-- snapshot_branches') to stdout;
copy (select '') to stdout;

copy (select * from snapshot_branches where snapshot_id in (select snapshot_id from snp_to_remove)) to stdout with (format csv, header);

copy (select '') to stdout;


--delete from snapshot_branches where snapshot_id in (select snapshot_id from snp_to_remove);


copy (select '-- snapshot_branch') to stdout;
copy (select '') to stdout;

copy (select * from snapshot_branch sb where sb.object_id in (select branch_id from snp_branch_to_remove) and not exists (select 1 from snapshot_branches sbs where sbs.branch_id = sb.object_id and sbs.snapshot_id not in (select snapshot_id from snp_to_remove))) to stdout with (format csv, header);

copy (select '') to stdout;

--delete from snapshot_branch sb where sb.object_id in (select branch_id from snp_branch_to_remove) and not exists (select 1 from snapshot_branches sbs where sbs.branch_id = sb.object_id and sbs.snapshot_id not in (select snapshot_id from snp_to_remove));


copy (select '-- snapshot') to stdout;
copy (select '') to stdout;

copy (select * from snapshot where object_id in (select snapshot_id from snp_to_remove)) to stdout with (format csv, header);

copy (select '') to stdout;


--delete from snapshot where object_id in (select snapshot_id from snp_to_remove);


copy (select '-- release') to stdout;
copy (select '') to stdout;

copy (select * from release where id in (select id from objects_to_remove where type = 'rel'))  to stdout with (format csv, header);

copy (select '') to stdout;


--delete from release where id in (select id from objects_to_remove where type = 'rel');


copy (select '-- revision_history') to stdout;
copy (select '') to stdout;

copy (select * from revision_history where id in (select id from objects_to_remove where type = 'rev')) to stdout with (format csv, header);

copy (select '') to stdout;


--delete from revision_history where id in (select id from objects_to_remove where type = 'rev');


copy (select '-- revision') to stdout;
copy (select '') to stdout;

copy (select * from revision where id in (select id from objects_to_remove where type = 'rev')) to stdout with (format csv, header);

copy (select '') to stdout;


--delete from revision where id in (select id from objects_to_remove where type = 'rev');



create temp table de_dir_to_remove
 on commit drop
 as
  select unnest(dir_entries) as id
  from directory
  inner join objects_to_remove otr
    on directory.id = otr.id and otr.type = 'dir';

create temp table de_file_to_remove
  on commit drop
  as
    select unnest(file_entries) as id
    from directory
    inner join objects_to_remove otr
      on directory.id = otr.id and otr.type = 'dir';

create temp table de_rev_to_remove
  on commit drop
  as
    select unnest(rev_entries) as id
    from directory
    inner join objects_to_remove otr
      on directory.id = otr.id and otr.type = 'dir';




copy (select '-- directory') to stdout;
copy (select '') to stdout;

copy (select dir_id as id, name, perms, w.type, target from objects_to_remove otr join lateral swh_directory_walk_one(id) w on true where otr.type = 'dir') to stdout with (format csv, header);

copy (select '') to stdout;


--delete from directory where id in (select id from objects_to_remove where type = 'dir');



copy (select '-- content') to stdout;
copy (select '') to stdout;

copy (select * from content where sha1_git in (select id from objects_to_remove where type = 'cnt')) to stdout with (format csv, header);

copy (select '') to stdout;


--delete from content where sha1_git in (select id from objects_to_remove where type = 'cnt');


ROLLBACK;"""


if __name__ == "__main__":
    graph = pickle.load(open(sys.argv[1], "rb"))

    nodes = graph.vs.select(has_inbound_edges_outside_subgraph_eq=False)["swhid"]

    values = ", ".join(
        f"('{swhid.object_type.value}', '\\x{swhid.object_id.hex()}')"
        for swhid in nodes
    )

    print(SQL_TEMPLATE % values)
