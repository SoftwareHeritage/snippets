from grafanalib.core import *

def memory_graph(time_from=None):
  if time_from is not None:
    timeFrom = "%s" % (time_from,)
  else:
    timeFrom = None
  return Graph(
    title='Memory usage',
    dataSource="Prometheus",
    timeFrom=timeFrom,
    stack=True,
    tooltip=Tooltip(valueType=INDIVIDUAL),
    targets=[
      Target(
        expr='node_memory_MemTotal_bytes{instance="192.168.100.29:9100"}',
        legendFormat="Total memory",
        refId='A',
      ),
      Target(
        expr='node_memory_MemTotal_bytes{instance="192.168.100.29:9100"} - \
	      node_memory_MemAvailable_bytes{instance="192.168.100.29:9100"}',
        legendFormat="Used memory",
        refId='B',
      ),
      Target(
        expr='node_memory_Cached_bytes{instance="192.168.100.29:9100"}',
        legendFormat="File cache",
        refId='C',
      ),
      Target(
        expr='node_memory_SwapTotal_bytes{instance="192.168.100.29:9100"} - \
	      node_memory_SwapFree_bytes{instance="192.168.100.29:9100"}',
        legendFormat="Used swap",
        refId='D',
      ),
    ],
    seriesOverrides = [
	{"alias": "Total memory", "stack": "false"},
	{"alias": "Used swap", "stack": "false", "fill": "10"},
    ],
    yAxes=[
      YAxis(format='decbytes'),
      YAxis(format=SHORT_FORMAT),
    ],
  )

dashboard = Dashboard(
    title="Pergamon memory usage auto-generated",
    rows=[
      Row(
        title = 'Memory',
        panels=[
          memory_graph(),
          memory_graph("1y"),
        ],
      ),
    ],).auto_panel_ids()
