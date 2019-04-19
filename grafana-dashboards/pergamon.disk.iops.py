from grafanalib.core import *

def device_iops_graph(device, time_from=None):
  if time_from is not None:
    timeFrom = "%s" % (time_from,)
  else:
    timeFrom = None
  return Graph(
    title='IOs for %s' % (device,),
    dataSource="Prometheus",
    timeFrom=timeFrom,
    targets=[
      Target(
        expr='rate(node_disk_reads_completed_total{instance="192.168.100.29:9100",device="%s"}[5m])' % (device),
        legendFormat="reads per second",
        refId='A',
      ),
      Target(
        expr='rate(node_disk_writes_completed_total{instance="192.168.100.29:9100",device="%s"}[5m])' % (device),
        legendFormat="writes per second",
        refId='B',
      ),
    ],
    yAxes=[
      YAxis(format=SHORT_FORMAT),
      YAxis(format=SHORT_FORMAT),
    ],
    legend=Legend(max=True, min=True, avg=True, current=True),
  )

dashboard = Dashboard(
    title="Pergamon diskstat iops auto-generated",
    templating=Templating(list=[
        Template(
            name="device",
            label="",
            query='node_disk_io_now{instance="192.168.100.29:9100"}',
            regex='/device="([s|v]d[a-z]*)/',
            dataSource='Prometheus',
            includeAll=True,
            default="All",
            hide = 2,
        ),
    ]),
    rows=[
      Row(
        title = 'device',
        panels=[
          device_iops_graph('$device'),
          device_iops_graph('$device', "1y"),
        ],
        repeat = 'device',
      ),
    ],).auto_panel_ids()
