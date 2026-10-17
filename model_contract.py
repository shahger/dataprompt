"""Shared model invocation contract, independent of FastAPI and database startup."""
import inspect


def invoke_model(function, path, submitted, timeout):
    deadline = submitted + timeout - min(10.0, timeout * 0.1)
    try:
        parameter = inspect.signature(function).parameters.get('deadline')
    except (TypeError, ValueError):
        parameter = None
    if parameter is None:
        return function(str(path))
    if parameter.kind == inspect.Parameter.POSITIONAL_ONLY:
        return function(str(path), deadline)
    return function(str(path), deadline=deadline)
