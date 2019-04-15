from grafanalib.core import *

def swap_activity_graph(time_from=None):
  if time_from is not None:
    timeFrom = "%s" % (time_from,)
  else:
    timeFrom = None
  return Graph(
    title='Swap activity',
    dataSource="Prometheus",
    timeFrom=timeFrom,
    targets=[
      Target(
        expr='irate(node_vmstat_pswpin{instance="192.168.100.29:9100"}[5m])',
        legendFormat="pages per second in",
        refId='A',
      ),
      Target(
        expr='irate(node_vmstat_pswpout{instance="192.168.100.29:9100"}[5m])',
        legendFormat="pages per second out",
        refId='B',
      ),
    ],
    yAxes=[
      YAxis(format=SHORT_FORMAT),
      YAxis(format=SHORT_FORMAT),
    ],
  )

dashboard = Dashboard(
    title="Pergamon swap usage auto-generated",
    rows=[
      Row(
        title = 'Swap',
        panels=[
          swap_activity_graph(),
          swap_activity_graph("1y"),
        ],
      ),
    ],).auto_panel_ids()
