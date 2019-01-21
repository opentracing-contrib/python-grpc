# OpenTracing support for gRPC in Python

The `grpcio-opentracing` package makes it easy to add OpenTracing support to 
gRPC-based systems in Python.

## Installation

```
pip install grpcio-opentracing
```

## Getting started

See the below code for basic usage or [examples/hello_world](examples/hello_world) for a
complete example.

### Client-side usage example

```python
import grpc
from grpc_opentracing import open_tracing_client_interceptor

tracer = # some OpenTracing Tracer instance
tracer_interceptor = open_tracing_client_interceptor.OpenTracingClientInterceptor(tracer)
channel = # the grpc.Channel you created to invoke RPCs
channel = grpc.intercept_channel(channel, tracer_interceptor)

# All future RPC activity involving `channel` will be automatically traced.
```

### Server-side usage example

```python
import grpc
from concurrent import futures
from grpc_opentracing import open_tracing_server_interceptor

tracer = # some OpenTracing Tracer instance
tracer_interceptor = open_tracing_server_interceptor.OpenTracingServerInterceptor(tracer)
server = grpc.server(
    futures.ThreadPoolExecutor(max_workers=10),
    interceptors=(tracer_interceptor,))
# All future RPC activity involving `server` will be automatically traced.
```

### Integrating with other spans.

```python
from grpc_opentracing import scope

span = scope.get_active_span()
span = tracer.start_span("do some thing", child_of=span)
# do some thing
span.finish()
...
```