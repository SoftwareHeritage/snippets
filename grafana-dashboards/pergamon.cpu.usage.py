from grafanalib.core import *

def cpu_usage_graph(cpu=0, time_from=None):
  if time_from is not None:
    timeFrom = "%s" % (time_from,)
  else:
    timeFrom = None
  return Graph(
    title='CPU %s usage' % (cpu,),
    dataSource="Prometheus",
    timeFrom=timeFrom,
    stack=True,
    percentage=True,
    targets=[
      Target(
        expr='irate(node_cpu_seconds_total{instance="192.168.100.29:9100",cpu="%s",mode="system"}[5m])' % (cpu),
        legendFormat="system time",
        refId='A',
      ),
      Target(
        expr='irate(node_cpu_seconds_total{instance="192.168.100.29:9100",cpu="%s",mode="irq"}[5m])' % (cpu),
        legendFormat="irq",
        refId='B',
      ),
      Target(
        expr='irate(node_cpu_seconds_total{instance="192.168.100.29:9100",cpu="%s",mode="softirq"}[5m])' % (cpu),
        legendFormat="softirq",
        refId='C',
      ),
      Target(
        expr='irate(node_cpu_seconds_total{instance="192.168.100.29:9100",cpu="%s",mode="user"}[5m])' % (cpu),
        legendFormat="user time",
        refId='D',
      ),
      Target(
        expr='irate(node_cpu_seconds_total{instance="192.168.100.29:9100",cpu="%s",mode="nice"}[5m])' % (cpu),
        legendFormat="nice",
        refId='E',
      ),
      Target(
        expr='irate(node_cpu_seconds_total{instance="192.168.100.29:9100",cpu="%s",mode="idle"}[5m])' % (cpu),
        legendFormat="idle",
        refId='F',
      ),
      Target(
        expr='irate(node_cpu_seconds_total{instance="192.168.100.29:9100",cpu="%s",mode="iowait"}[5m])' % (cpu),
        legendFormat="iowait",
        refId='G',
      ),
      Target(
        expr='irate(node_cpu_seconds_total{instance="192.168.100.29:9100",cpu="%s",mode="steal"}[5m])' % (cpu),
        legendFormat="steal",
        refId='H',
      ),
    ],
    yAxes=[
      YAxis(format='percentunit'),
      YAxis(format=SHORT_FORMAT),
    ],
  )

dashboard = Dashboard(
    title="Pergamon CPU usage auto-generated",
    rows=[
      Row(
        title = 'CPU 0',
        panels=[ cpu_usage_graph('0'), cpu_usage_graph('0', "1y"), ],
      ),
      Row(
        title = 'CPU 1',
        panels=[ cpu_usage_graph('1'), cpu_usage_graph('1', "1y"), ],
      ),
    ],).auto_panel_ids()
