from grpc_opentracing import scope


class _LoggingIterator(object):

    def __init__(self, key, iterator, span):
        self._key = key
        self._iterator = iterator
        self._span = span

    def __iter__(self):
        return self

    def next(self):
        request = next(self._iterator)
        self._span.log_kv({self._key: request})
        return request

    def __next__(self):
        return self.next()


def log_or_wrap_request_or_iterator(span, is_client_stream,
                                    request_or_iterator):
    if is_client_stream:
        return _LoggingIterator('request', request_or_iterator, span)
    else:
        span.log_kv({'request': request_or_iterator})
        return request_or_iterator


def log_or_wrap_response_or_iterator(span, is_service_stream,
                                     response_or_iterator):
    if is_service_stream:
        return _LoggingIterator('response', response_or_iterator, span)
    else:
        span.log_kv({'response': response_or_iterator})
        return response_or_iterator


def wrap_iter_with_end_span(response_iter):
    for response in response_iter:
        yield response
    scope.end_span()
