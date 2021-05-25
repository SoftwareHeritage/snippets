import statusio
import requests
from datetime import datetime, timedelta
from typing import List, Tuple
import os

API_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S+00:00"

# 2014-03-28T05:43:00+00:00

def get_prometheus_metrics(raw_data) -> List[List]:
    return raw_data.get("data").get("result")[0].get("values")

def get_average(values: List[int]) -> float:
    return sum(values) / len(values)

def get_scn_statistics(start, end, interval):
    url = f'{prometheus_url}?query=sum(swh_web_accepted_save_requests{{environment="production", load_task_status=~"scheduled|not_yet_scheduled", vhost_name="archive.softwareheritage.org"}})&start={start}&end={end}&step={interval}'
    
    response = requests.get(url)
    if response.ok == False:
        print("Unable to get prometheus metrics")
        os.exit(1)

    return get_prometheus_metrics(response.json())

def extract_status_io_data(prometheus_data: List[List]) -> Tuple:
    dates = []
    values = []

    for tuple in prometheus_data:
        date = datetime.fromtimestamp(tuple[0])
        
        dates.append(date.strftime(API_DATE_FORMAT))
        values.append(int(tuple[1]))
    
    return (dates, values)


api_id = "changeme"
api_key = "changeme"

status_page_id = "changeme"

scn_metric = "changeme"

prometheus_url = "http://pergamon.internal.softwareheritage.org:9090/api/v1/query_range"

api = statusio.Api(api_id=api_id, api_key=api_key)

# summary = api.StatusSummary(status_page_id)
# print(summary)

# print()

# components = api.ComponentList(status_page_id)
# print(components)

# print()

# http://pergamon.internal.softwareheritage.org:9090/api/v1/query_range?query=sum(swh_web_accepted_save_requests%7Benvironment%3D%22production%22%2C%20load_task_status%3D~%22scheduled%7Cnot_yet_scheduled%22%2C%20vhost_name%3D%22archive.softwareheritage.org%22%7D)&start=1621432297.968&end=1621518697.968&step=300&_=1621517926744

current_time = datetime.utcnow()
day_start = current_time - timedelta(days=1)
hour_interval = 3600
day_interval = 3600*24

week_start = current_time - timedelta(days=7)
month_start = current_time - timedelta(days=30)
# print(day_start)
# print(day_start.strftime(API_DATE_FORMAT))

# daily_average = get_average(day_start.timestamp(), current_time.timestamp())

# daily_statistics = f'{prometheus_url}?query=sum(swh_web_accepted_save_requests{{environment="production", load_task_status=~"scheduled|not_yet_scheduled", vhost_name="archive.softwareheritage.org"}})&start=1621432297.968&end=1621518697.968&step=3600&_=1621517926744'

# response = requests.get(daily_statistics)
# if response.ok == False:
#     print("Unable to get prometheus metrics")
#     os.exit(1)

raw_prometheus_data = get_scn_statistics(day_start.timestamp(), current_time.timestamp(), hour_interval)
day_dates, day_values = extract_status_io_data(raw_prometheus_data)
day_avg = get_average(day_values)

raw_prometheus_data = get_scn_statistics(week_start.timestamp(), current_time.timestamp(), day_interval)
week_dates, week_values = extract_status_io_data(raw_prometheus_data)
week_avg = get_average(day_values)

raw_prometheus_data = get_scn_statistics(month_start.timestamp(), current_time.timestamp(), day_interval)
month_dates, month_values = extract_status_io_data(raw_prometheus_data)
month_avg = get_average(day_values)


print("day")
print(day_values)
print(day_avg)
print()
print("week")
print(week_values)
print(week_avg)
print()
print("month")
print(month_dates)
print(month_values)
print(month_avg)


result = api.MetricUpdate(
    statuspage_id=status_page_id,
    metric_id=scn_metric,
                     day_avg=day_avg,
                     day_start=day_start.timestamp(),
                     day_dates=day_dates,
                     day_values=day_values,
                     week_avg=week_avg,
                     week_start=week_start.timestamp(),
                     week_dates=week_dates,
                     week_values=week_values,
                     month_avg=month_avg,
                     month_start=month_start.timestamp(),
                     month_dates=month_dates,
                     month_values=month_values)

print(result)
