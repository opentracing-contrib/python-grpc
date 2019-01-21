"""Implementation of the client-side open-tracing interceptor using grpc Interceptor."""

import collections
import logging

import grpc
import opentracing
import six
from opentracing.ext import tags as ot_tags

from grpc_opentracing import scope
from grpc_opentracing.grpc_interceptor import utils as grpc_utils

log = logging.getLogger(__name__)


class _ClientCallDetails(
    collections.namedtuple(
        '_ClientCallDetails',
        ('method', 'timeout', 'metadata', 'credentials')),
    grpc.ClientCallDetails):
    pass


def _inject_span_context(tracer, span, metadata):
    headers = {}
    try:
        tracer.inject(span.context, opentracing.Format.HTTP_HEADERS, headers)
    except (opentracing.UnsupportedFormatException,
            opentracing.InvalidCarrierException,
            opentracing.SpanContextCorruptedException) as e:
        logging.exception('tracer.inject() failed')
        span.log_kv({'event': 'error', 'error.object': e})
        return metadata
    metadata = () if metadata is None else tuple(metadata)
    return metadata + tuple((k.lower(), v) for (k, v) in six.iteritems(headers))


class OpenTracingClientInterceptor(grpc.UnaryUnaryClientInterceptor,
                                   grpc.UnaryStreamClientInterceptor,
                                   grpc.StreamUnaryClientInterceptor,
                                   grpc.StreamStreamClientInterceptor):

    def __init__(self, tracer, log_payloads):
        self._tracer = tracer
        self._log_payloads = log_payloads

    def _start_span(self, method):
        active_span_context = None
        active_span = scope.get_active_span()
        if active_span is not None:
            active_span_context = active_span.context
        tags = {
            ot_tags.COMPONENT: 'grpc',
            ot_tags.SPAN_KIND: ot_tags.SPAN_KIND_RPC_CLIENT
        }
        return self._tracer.start_span(
            operation_name=method, child_of=active_span_context, tags=tags)

    def _intercept_call(
            self, client_call_details, request_iterator
    ):
        metadata = ()
        if client_call_details.metadata is not None:
            metadata = client_call_details.metadata

        # Start a span
        current_span = self._start_span(client_call_details.method)

        metadata = _inject_span_context(self._tracer, current_span,
                                        metadata)
        client_call_details = _ClientCallDetails(
            client_call_details.method,
            client_call_details.timeout,
            metadata,
            client_call_details.credentials)

        if self._log_payloads:
            request_iterator = grpc_utils.log_or_wrap_request_or_iterator(
                span=current_span,
                is_client_stream=True,
                request_or_iterator=request_iterator
            )

        return client_call_details, request_iterator, current_span

    def _callback(self, current_span):
        def callback(future_response):
            exception = future_response.exception()
            if exception is not None:
                exception = str(exception)
                current_span.set_tag('error', True)
                error_log = {'event': 'error', 'error.kind': exception}
                current_span.log_kv(error_log)

            if self._log_payloads:
                response = future_response.result()
                current_span.log_kv({'response': response})

            scope.set_active_span(current_span)
            scope.end_span()

        return callback

    def intercept_unary_unary(
            self, continuation, client_call_details, request
    ):

        new_details, new_request, current_span = self._intercept_call(
            client_call_details=client_call_details,
            request_iterator=iter((request,)))

        response = continuation(
            new_details,
            next(new_request))

        response.add_done_callback(self._callback(current_span))

        return response

    def intercept_unary_stream(
            self, continuation, client_call_details, request
    ):

        new_details, new_request_iterator, current_span = self._intercept_call(
            client_call_details=client_call_details,
            request_iterator=iter((request,)))

        response_it = continuation(
            new_details,
            next(new_request_iterator))
        if self._log_payloads:
            response_it = grpc_utils.log_or_wrap_response_or_iterator(
                current_span, True, response_it
            )
        response_it = grpc_utils.wrap_iter_with_end_span(response_it)

        return response_it

    def intercept_stream_unary(
            self, continuation, client_call_details, request_iterator
    ):

        new_details, new_request_iterator, current_span = self._intercept_call(
            client_call_details=client_call_details,
            request_iterator=request_iterator)

        response = continuation(
            new_details,
            new_request_iterator)

        response.add_done_callback(self._callback(current_span))

        return response

    def intercept_stream_stream(
            self, continuation, client_call_details, request_iterator
    ):

        new_details, new_request_iterator, current_span = self._intercept_call(
            client_call_details=client_call_details,
            request_iterator=request_iterator)

        response_it = continuation(
            new_details,
            new_request_iterator)
        if self._log_payloads:
            response_it = grpc_utils.log_or_wrap_response_or_iterator(
                current_span, True, response_it
            )
        response_it = grpc_utils.wrap_iter_with_end_span(response_it)

        return response_it
