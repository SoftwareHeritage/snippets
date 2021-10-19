import sys
import copy
import statistics
import pandas as pd
import matplotlib.pyplot as pl

filename = str(sys.argv[1])

print('Reading:', filename)

with open(filename) as f:
    content = f.read().splitlines()

template = {'unfiltered_count':[], 'missing_duration':[], 'filtered_count':[], 'add_duration':[]}

data = {'content': copy.deepcopy(template),
        'directory': copy.deepcopy(template),
        'skipped_content': copy.deepcopy(template),
        'revision': copy.deepcopy(template),
        'release': copy.deepcopy(template)}


for line in content:
    l = line.strip().split(';')
    # print(f"{l}")
    values = data[l[0]]
    values['unfiltered_count'].append(int(l[1]))
    values['missing_duration'].append(float(l[2]))
    values['filtered_count'].append(int(l[3]))
    values['add_duration'].append(float(l[4]))


for type in ['content', 'directory', 'skipped_content', 'revision', 'release']:
    print(f"############### {type}")
    d = data[type]
    if len(d['unfiltered_count']) > 1:
        print(f"Number of unfiltered {type}: {sum(d['unfiltered_count'])}")
        print(f"Number of filtered {type}: {sum(d['filtered_count'])}")
        print(f"{type}_missing duration: {sum(d['missing_duration'])}")
        print(f"{type}_add duration: {sum(d['add_duration'])}")
        print()
        print(f"Average unfiltered count {type}: {statistics.mean(d['unfiltered_count'])}")
        print(f"Average filtered count {type}: {statistics.mean(d['filtered_count'])}")
        print(f"Average {type}_missing duration: {statistics.mean(d['missing_duration'])}")
        print(f"Average {type}_add duration: {statistics.mean(d['add_duration'])}")
        print()
        print(f"Median unfiltered count {type}: {statistics.median(d['unfiltered_count'])}")
        print(f"Median filtered count {type}: {statistics.median(d['filtered_count'])}")
        print(f"Median {type}_missing duration: {statistics.median(d['missing_duration'])}")
        print(f"Median {type}_add duration: {statistics.median(d['add_duration'])}")

        print()
        print(f"Percentiles {type}_missing duration: {statistics.quantiles(d['missing_duration'], n=10)}")
        print(f"Percentiles {type}_add duration: {statistics.quantiles(d['add_duration'], n=10)}")

    else:
        print("No data")

    print()


print("generating graphs...") 

graph_data=[]

# graph_data =[
#     [10, 20, 30, 40, 50, 60, 70, 80, 90],
#     statistics.quantiles(data['content']['add_duration'], n=10)
# ]
q1 = statistics.quantiles(data['content']['add_duration'], n=10)
q2 = statistics.quantiles(data['directory']['add_duration'], n=10)

print(q1)
print(q2)

for i in range(0, 9):
    print(i)
    graph_data.append([q1[i], q2[i]])

    # statistics.quantiles(data['directory']['add_duration']),
    # statistics.quantiles(data['revision']['add_duration']),


print(graph_data)
# p = pd.DataFrame(graph_data, columns=['content', 'directory', 'revision'])
# p = pd.DataFrame(graph_data, columns=['percent','content'])
p = pd.DataFrame(graph_data, index=range(10, 100, 10), columns=['content', 'directory'])

# p= p.cumsum()
p.plot.bar()
pl.savefig('test')
# p = pd.DataFrame(statistics.quantiles(data['content']['add_duration'], n=10))
