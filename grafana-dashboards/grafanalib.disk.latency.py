from grafanalib.core import *

def device_latency_graph(target, device, time_from=None):
  if time_from is not None:
    timeFrom = "%s" % (time_from,)
  else:
    timeFrom = None
  return Graph(
    title='Average latency for %s' % (device,),
    dataSource="Prometheus",
    timeFrom=timeFrom,
    targets=[
      Target(
        expr='rate(node_disk_io_time_weighted_seconds_total{instance="%s",device="%s"}[5m])' % (target, device),
        legendFormat="io_time_weighted_seconds rate",
        refId='A',
      ),
      Target(
        expr='xrate(node_disk_io_time_weighted_seconds_total{instance="%s",device="%s"}[5m])' % (target, device),
        legendFormat="io_time_weighted_seconds xrate",
        refId='B',
      ),
    ],
    yAxes=[
      YAxis(format='ms'),
      YAxis(format=SHORT_FORMAT),
    ],
    legend=Legend(max=True, min=True, avg=True, current=True),
  )

dashboard = Dashboard(
    title="Diskstat latency auto-generated",
    templating=Templating(list=[
        Template(
            name="host",
            label="",
            query='node_uname_info{instance="$target"}',
            regex='/nodename="([^"]*)"/',
            dataSource='Prometheus',
	),
        Template(
            name="target",
            label="",
            query='node_disk_io_now',
            regex='/instance="([^"]*)"/',
            dataSource='Prometheus',
        ),
        Template(
            name="device",
            label="",
            query='node_disk_io_now{instance="$target"}',
            regex='/device="([sd|vd|dm|md][a-z0-9-]*)/',
            dataSource='Prometheus',
            includeAll=True,
            default="All",
            hide=2,
        ),
    ]),
    rows=[
      Row(
        title = '$device device',
        panels=[
          device_latency_graph('$target', '$device'),
          device_latency_graph('$target', '$device', "1y"),
        ],
        repeat = 'device',
      ),
    ],).auto_panel_ids()
