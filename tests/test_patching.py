import pytest

def test_patch_all_detected_returns_list():
    import abidex
    result = abidex.patch_all_detected()
    assert isinstance(result, list)
    assert all((isinstance(x, str) for x in result))

def test_init_returns_list():
    import abidex
    result = abidex.init(auto_patch=True)
    assert isinstance(result, list)

def test_get_tracer():
    from abidex.otel_setup import get_tracer
    t = get_tracer('test')
    assert t is not None
    t2 = get_tracer()
    assert t2 is not None