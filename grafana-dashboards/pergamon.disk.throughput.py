from grafanalib.core import *

def device_tput_graph(device, time_from=None):
  if time_from is not None:
    timeFrom = "%s" % (time_from,)
  else:
    timeFrom = None
  return Graph(
    title='Throughput for %s' % (device,),
    dataSource="Prometheus",
    timeFrom=timeFrom,
    targets=[
      Target(
        expr='irate(node_disk_read_bytes_total{instance="192.168.100.29:9100",device="%s"}[5m])' % (device),
#        expr='node_disk_read_bytes_total{instance="192.168.100.29:9100",device="%s"}' % (device),
        legendFormat="bytes read per second",
        refId='A',
      ),
      Target(
        expr='rate(node_disk_written_bytes_total{instance="192.168.100.29:9100",device="%s"}[23m])' % (device),
        legendFormat="bytes written per second",
        refId='B',
      ),
    ],
    yAxes=[
      YAxis(format='bytes'),
      YAxis(format=SHORT_FORMAT),
    ],
    legend=Legend(max=True, min=True, avg=True, current=True),
  )

dashboard = Dashboard(
    title="Pergamon diskstat throughput auto-generated",
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
          device_tput_graph('$device'),
          device_tput_graph('$device', "1y"),
        ],
        repeat = 'device',
      ),
    ],).auto_panel_ids()
