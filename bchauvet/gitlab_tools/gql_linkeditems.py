import configparser
import json

from gql import gql, Client
from gql.transport.aiohttp import AIOHTTPTransport

config = configparser.ConfigParser()
config.read('python-gitlab.cfg')
token = config.get('prod','private_token')

# Select your transport with a defined url endpoint
transport = AIOHTTPTransport(url=f"https://gitlab.softwareheritage.org/api/graphql?private_token={token}")

# Create a GraphQL client using the defined transport
client = Client(transport=transport, fetch_schema_from_transport=True)

# Provide a GraphQL query
query = gql(
    """
    query getLinkedItems {
      workItem(id: "gid://gitlab/WorkItem/8781") {
        widgets {
          ... on WorkItemWidgetLinkedItems {     
            linkedItems {
              edges {
                node {
                  linkId
                  linkType
                  linkCreatedAt
                  linkUpdatedAt
                  workItem {
                    id
                    title
                  }
                }
              }
            }
          }
        }
      }
    }

"""
)

result = client.execute(query, parse_result=True)
print(result["workItem"]["widgets"][10])


# Execute the query on the transport
# result = client.execute(query)
# print(result)