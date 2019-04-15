from grafanalib.core import *

def network_graph(device, time_from=None):
  if time_from is not None:
    timeFrom = "%s" % (time_from,)
  else:
    timeFrom = None
  return Graph(
    title='Network traffic',
    dataSource="Prometheus",
    timeFrom=timeFrom,
    stack=True,
    tooltip=Tooltip(valueType=INDIVIDUAL),
    targets=[
      Target(
        expr='irate(node_network_receive_bytes_total{instance="192.168.100.29:9100",device="%s"}[5m])' % (device),
        legendFormat="bytes per second in",
        refId='A',
      ),
      Target(
        expr='irate(node_network_transmit_bytes_total{instance="192.168.100.29:9100",device="%s"}[5m])' % (device),
        legendFormat="bytes per second out",
        refId='B',
      ),
    ],
    yAxes=[
      YAxis(format='decbytes'),
      YAxis(format=SHORT_FORMAT),
    ],
    legend=Legend(max=True, min=True, avg=True, current=True),
  )

dashboard = Dashboard(
    title="Pergamon network traffic auto-generated",
    templating=Templating(list=[
        Template(
            name="interface",
            label="",
            query='node_arp_entries{instance="192.168.100.29:9100"}',
            regex='/device="([^"]*)/',
            dataSource='Prometheus',
            includeAll=True,
            default="All",
            hide = 2,
        ),
    ]),
    rows=[
      Row(
        title = '$interface traffic',
        panels=[
          network_graph("$interface"),
          network_graph("$interface","1y"),
        ],
	repeat = 'interface',
      ),
    ],).auto_panel_ids()
