from grafanalib.core import *

def loadavg_graph(time_from=None):
  if time_from is not None:
    timeFrom = "%s" % (time_from,)
  else:
    timeFrom = None
  return Graph(
    title='Load average',
    dataSource="Prometheus",
    timeFrom=timeFrom,
    targets=[
      Target(
        expr='node_load5{instance="192.168.100.29:9100"}',
        legendFormat="5m load average",
        refId='A',
      ),
    ],
    yAxes=[
      YAxis(format=SHORT_FORMAT),
      YAxis(format=SHORT_FORMAT),
    ],
  )

dashboard = Dashboard(
    title="Pergamon loadavg auto-generated",
    rows=[
      Row(
        title = 'Load average',
        panels=[ loadavg_graph(), loadavg_graph("1y"), ],
      ),
    ],).auto_panel_ids()
