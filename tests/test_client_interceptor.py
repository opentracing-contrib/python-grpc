import unittest

from grpc_opentracing.grpc_interceptor import open_tracing_client_interceptor

from _tracer import Tracer


class TestOpenCensusClientInterceptor(unittest.TestCase):

    def test_constructor_default(self):
        interceptor = open_tracing_client_interceptor.OpenTracingClientInterceptor(Tracer(), True)
        self.assertIsNotNone(interceptor._tracer)
        self.assertTrue(interceptor._log_payloads)
