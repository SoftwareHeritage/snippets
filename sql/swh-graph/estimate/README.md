SQL queries to compute the size of the **Software Heritage graph**, which has
as nodes commits/trees/blobs, and as edges the relations among them.

The main file is swh-graph.txt, in org-mode, which generates swh-graph.sql
using org-babel-tangle (C-c C-v t). swh-graph.out are the last results obtained
running the query.
