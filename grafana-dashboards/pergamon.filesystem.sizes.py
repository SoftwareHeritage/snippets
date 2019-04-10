from grafanalib.core import *

def filesystem_graph(mountpoint, time_from=None):
  if time_from is not None:
    timeFrom = "%s" % (time_from,)
  else:
    timeFrom = None
  return Graph(
    title='Size of %s' % (mountpoint,),
    dataSource="Prometheus",
    timeFrom=timeFrom,
    targets=[
      Target(
        expr='node_filesystem_size_bytes{instance="192.168.100.29:9100",mountpoint="%s"}' % (mountpoint),
        legendFormat="Filesystem size",
        refId='A',
      ),
      Target(
        expr='node_filesystem_size_bytes{instance="192.168.100.29:9100",mountpoint="%s"} - \
              node_filesystem_avail_bytes{instance="192.168.100.29:9100",mountpoint="%s"}' % (mountpoint, mountpoint),
        legendFormat="Used space",
        refId='B',
      ),
    ],
    yAxes=[
      YAxis(format='decbytes'),
      YAxis(format=SHORT_FORMAT),
    ],
  )

dashboard = Dashboard(
    title="Pergamon filesystem sizes auto-generated",
    templating=Templating(list=[
        Template(
            name="filesystem",
            label="",
            query='node_filesystem_size_bytes{instance="192.168.100.29:9100"}',
            regex='/mountpoint=\"(.*)\"/',
            dataSource='Prometheus',
            includeAll=True,
            default="All",
            hide = 2,
        ),
    ]),
    rows=[
      Row(
        title = '$filesystem',
        panels=[
          filesystem_graph('$filesystem'),
          filesystem_graph('$filesystem', "1y"),
        ],
        repeat = 'filesystem',
      ),
    ],).auto_panel_ids()

