from __future__ import print_function

import argparse
import time

import grpc
from concurrent import futures
from jaeger_client import Config

import hello_world_pb2
import hello_world_pb2_grpc
from grpc_opentracing import open_tracing_server_interceptor
from grpc_opentracing import scope

_ONE_DAY_IN_SECONDS = 60 * 60 * 24


class HelloWorld(hello_world_pb2_grpc.GreeterServicer):
    def __init__(self, tracer):
        self.tracer = tracer

    def SayHello(self, request, context):
        span = scope.get_active_span()
        span = self.tracer.start_span("do some thing", child_of=span)
        time.sleep(0.1)
        span.finish()
        return hello_world_pb2.HelloReply(message='Hello, %s!' % request.name)


def serve():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--log_payloads',
        action='store_true',
        default=True,
        help='log request/response objects to open-tracing spans')
    args = parser.parse_args()

    config = Config(
        config={
            'sampler': {
                'type': 'const',
                'param': 1,
            },
            'logging': True,
        },
        service_name='hello_world_server')
    tracer = config.initialize_tracer()
    tracer_interceptor = open_tracing_server_interceptor.OpenTracingServerInterceptor(
        tracer, log_payloads=args.log_payloads)
    server = grpc.server(
        futures.ThreadPoolExecutor(max_workers=10),
        interceptors=(tracer_interceptor,))
    hello_world_pb2_grpc.add_GreeterServicer_to_server(HelloWorld(tracer), server)
    server.add_insecure_port('[::]:50051')
    server.start()
    try:
        while True:
            time.sleep(_ONE_DAY_IN_SECONDS)
    except KeyboardInterrupt:
        server.stop(0)


if __name__ == '__main__':
    serve()
