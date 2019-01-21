from __future__ import print_function

import argparse
import time

import grpc
from jaeger_client import Config

import hello_world_pb2
import hello_world_pb2_grpc
from grpc_opentracing import open_tracing_client_interceptor
from grpc_opentracing import scope

HOST_PORT = 'localhost:50051'


def main():
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
        service_name='hello_world_client')
    tracer = config.initialize_tracer()
    tracer_interceptor = open_tracing_client_interceptor.OpenTracingClientInterceptor(
        tracer,
        log_payloads=args.log_payloads)
    with tracer.start_span("step1") as span:
        scope.set_active_span(span)
        time.sleep(0.01)
    channel = grpc.insecure_channel(HOST_PORT)
    channel = grpc.intercept_channel(channel, tracer_interceptor)
    stub = hello_world_pb2_grpc.GreeterStub(channel)
    response = stub.SayHello(hello_world_pb2.HelloRequest(name='you'))
    print("Message received: " + response.message)


if __name__ == '__main__':
    main()
