import logging
import threading

_thread_local = threading.local()


def get_active_span():
    return getattr(_thread_local, 'active_span', None)


def set_active_span(active_span):
    setattr(_thread_local, 'active_span', active_span)


def end_span():
    span = get_active_span()
    if span is None:
        logging.warning('No active span, cannot do end_span.')
        return
    span.finish()
