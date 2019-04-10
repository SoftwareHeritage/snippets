from grafanalib.core import *

def cpu_usage_graph(cpu=0, time_from=None):
  if time_from is not None:
    timeFrom = "%s" % (time_from,)
  else:
    timeFrom = None
  return Graph(
    title='Uptime',
    dataSource="Prometheus",
    timeFrom=timeFrom,
    targets=[
      Target(
        expr='time() - node_boot_time_seconds{instance="192.168.100.29:9100"}',
        legendFormat="uptime",
        refId='A',
      ),
    ],
    yAxes=[
      YAxis(format=SECONDS_FORMAT),
      YAxis(format=SHORT_FORMAT),
    ],
  )

dashboard = Dashboard(
    title="Pergamon uptime auto-generated",
    rows=[
      Row(
        title = 'Uptime',
        panels=[
          cpu_usage_graph('0'),
          cpu_usage_graph('0', "1y"),
        ],
        repeat = 'cpu',
      ),
    ],).auto_panel_ids()
