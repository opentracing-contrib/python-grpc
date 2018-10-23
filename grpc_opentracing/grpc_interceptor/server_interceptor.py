"""Implementation of the service-side open-tracing interceptor using grpc.ServerInterceptor."""
import logging
import re
import sys

import grpc
import opentracing
from opentracing.ext import tags as ot_tags

from grpc_opentracing import scope
from grpc_opentracing.grpc_interceptor import utils as grpc_utils

_CANCELLED = 'cancelled'


class OpenTracingServerInterceptor(grpc.ServerInterceptor):

    def __init__(self, tracer, log_payloads):
        self._tracer = tracer
        self._log_payloads = log_payloads

    def _start_span(self, servicer_context, method):
        span_context = None
        error = None
        metadata = servicer_context.invocation_metadata()
        try:
            if metadata:
                span_context = self._tracer.extract(
                    opentracing.Format.HTTP_HEADERS, dict(metadata))
        except (opentracing.UnsupportedFormatException,
                opentracing.InvalidCarrierException,
                opentracing.SpanContextCorruptedException) as e:
            logging.exception('tracer.extract() failed')
            error = e
        tags = {
            ot_tags.COMPONENT: 'grpc',
            ot_tags.SPAN_KIND: ot_tags.SPAN_KIND_RPC_SERVER
        }
        _add_peer_tags(servicer_context.peer(), tags)
        span = self._tracer.start_span(
            operation_name=method, child_of=span_context, tags=tags)
        if error is not None:
            span.log_kv({'event': 'error', 'error.object': error})
        scope.set_active_span(span)
        return span

    def intercept_service(self, continuation, handler_call_details):
        def trace_wrapper(behavior, request_streaming, response_streaming):
            def new_behavior(request_or_iterator, servicer_context):
                span = self._start_span(servicer_context, handler_call_details.method)
                try:
                    if self._log_payloads:
                        request_or_iterator = grpc_utils.log_or_wrap_request_or_iterator(
                            span, request_streaming, request_or_iterator)
                    # invoke the original rpc behavior
                    response_or_iterator = behavior(request_or_iterator,
                                                    servicer_context)

                    if self._log_payloads:
                        response_or_iterator = grpc_utils.log_or_wrap_response_or_iterator(
                            span, response_streaming, response_or_iterator
                        )
                    if response_streaming:
                        response_or_iterator = grpc_utils.wrap_iter_with_end_span(response_or_iterator)
                    _check_error_code(span, servicer_context)
                except Exception as exc:
                    logging.exception(exc)
                    e = sys.exc_info()[0]
                    span.set_tag('error', True)
                    span.log_kv({'event': 'error', 'error.object': e})
                    raise
                finally:
                    # if the response is unary, end the span here. Otherwise
                    # it will be closed when the response iter completes
                    if not response_streaming:
                        scope.end_span()
                return response_or_iterator

            return new_behavior

        return _wrap_rpc_behavior(
            continuation(handler_call_details),
            trace_wrapper
        )


def _wrap_rpc_behavior(handler, fn):
    """Returns a new rpc handler that wraps the given function"""
    if handler is None:
        return None

    if handler.request_streaming and handler.response_streaming:
        behavior_fn = handler.stream_stream
        handler_factory = grpc.stream_stream_rpc_method_handler
    elif handler.request_streaming and not handler.response_streaming:
        behavior_fn = handler.stream_unary
        handler_factory = grpc.stream_unary_rpc_method_handler
    elif not handler.request_streaming and handler.response_streaming:
        behavior_fn = handler.unary_stream
        handler_factory = grpc.unary_stream_rpc_method_handler
    else:
        behavior_fn = handler.unary_unary
        handler_factory = grpc.unary_unary_rpc_method_handler

    return handler_factory(fn(behavior_fn,
                              handler.request_streaming,
                              handler.response_streaming),
                           request_deserializer=handler.request_deserializer,
                           response_serializer=handler.response_serializer)


# On the service-side, errors can be signaled either by exceptions or by calling
# `set_code` on the `servicer_context`. This function checks for the latter and
# updates the span accordingly.
def _check_error_code(span, servicer_context):
    code = _get_error_code(servicer_context)
    if code != grpc.StatusCode.OK:
        span.set_tag('error', True)
        error_log = {'event': 'error', 'error.kind': str(code)}
        details = _details(servicer_context)
        if details is not None:
            error_log['message'] = details
        span.log_kv(error_log)


def _get_error_code(servicer_context):
    if servicer_context._state.client is _CANCELLED:
        return grpc.StatusCode.CANCELLED
    if servicer_context._state.code is None:
        return grpc.StatusCode.OK
    else:
        return servicer_context._state.code


def _details(servicer_context):
    return b'' if servicer_context._state is None else servicer_context._state


def _add_peer_tags(peer_str, tags):
    ipv4_re = r"ipv4:(?P<address>.+):(?P<port>\d+)"
    match = re.match(ipv4_re, peer_str)
    if match:
        tags[ot_tags.PEER_HOST_IPV4] = match.group('address')
        tags[ot_tags.PEER_PORT] = match.group('port')
        return
    ipv6_re = r"ipv6:\[(?P<address>.+)\]:(?P<port>\d+)"
    match = re.match(ipv6_re, peer_str)
    if match:
        tags[ot_tags.PEER_HOST_IPV6] = match.group('address')
        tags[ot_tags.PEER_PORT] = match.group('port')
        return
    logging.warning('Unrecognized peer: \"%s\"', peer_str)
