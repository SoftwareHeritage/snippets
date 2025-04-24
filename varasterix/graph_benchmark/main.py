import click
import grpc
import swh.graph.grpc.swhgraph_pb2_grpc as swhgraph_grpc


@click.command()
@click.argument("grpc-server", type=click.STRING)
def main(grpc_server: str):
    with grpc.insecure_channel(grpc_server) as channel:
        grpc_stub = swhgraph_grpc.TraversalServiceStub(channel)
        grpc_stub.GetNode
        grpc_stub.Traverse


if __name__ == "__main__":
    main()
