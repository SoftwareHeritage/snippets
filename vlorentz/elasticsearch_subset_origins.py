import csv
import sys

import elasticsearch
import elasticsearch.helpers

hosts = [
    f"http://search-esnode{i}.internal.softwareheritage.org:9200/"
    for i in range(4, 7)
]
client = elasticsearch.Elasticsearch(hosts=hosts)

FORK_PARENT_PATH = "https://forgefed.org/ns#forkedFrom.@id"
LANGUAGE_PATH = "http://schema.org/programmingLanguage.@value"
LIKES_PATH = "https://www.w3.org/ns/activitystreams#likes.https://www.w3.org/ns/activitystreams#totalItems.@value"

query = {
    # only return URL and number of stars
    "fields": [
        "url",
        "jsonld." + LIKES_PATH,
        "jsonld." + LANGUAGE_PATH,
    ],
    "_source": False,
    # filter so that:
    "query": {
        "bool": {
            "must": [
                # include only projects detected by the forge as being in C
                {
                    "nested": {
                        "path": "jsonld",
                        "query": {
                            "match": {
                                "jsonld." + LANGUAGE_PATH: "C"
                            }
                        },
                    }
                },
                # exclude projects with unknown number of stars or on forges without
                # a concept of stars
                {
                    "nested": {
                        "path": "jsonld",
                        "query": {
                            "exists": {
                                "field": "jsonld." + LIKES_PATH
                            }
                        },
                    }
                },
            ],
            "must_not": [
                # exclude projects with no stars
                {
                    "nested": {
                        "path": "jsonld",
                        "query": {
                            "match": {
                                "jsonld." + LIKES_PATH: 0
                            }
                        },
                    }
                },
                # exclude forks (by filtering out documents that have a parent defined)
                {
                    "nested": {
                        "path": "jsonld",
                        "query": {
                            "exists": {
                                "field": "jsonld." + FORK_PARENT_PATH
                            }
                        },
                    }
                },
            ],
        }
    },
}

writer = csv.writer(sys.stdout)

for result in elasticsearch.helpers.scan(client, index="origin-v0.11", query=query):
    # result = {'_index': 'origin-v0.11', '_type': '_doc', '_id': '100c7d1725d256d0df485dcacaba5e31dc6db00f', '_score': None, 'fields': {'jsonld': [{'https://www.w3.org/ns/activitystreams#likes.https://www.w3.org/ns/activitystreams#totalItems.@value': ['2']}], 'url': ['https://github.com/alexdimitrov2000/AspNetCore_PersonalProject']}, 'sort': [237142]}
    (url,) = result["fields"]["url"]
    (jsonld,) = result["fields"]["jsonld"]
    (language,) = jsonld[LANGUAGE_PATH]
    (num_likes,) = jsonld[LIKES_PATH]
    if language == "C":
        # TODO: find a way to make Elasticsearch return only exact matches...
        continue
    writer.writerow(("swh:1:ori:" + result['_id'], url, num_likes))

