import pytest


def test_crewai_patch_registered():
    from abidex.patches.crewai import apply_crewai_patch
    out = apply_crewai_patch()
    assert isinstance(out, bool)


def test_langgraph_patch_registered():
    from abidex.patches.langgraph import apply_langgraph_patch
    out = apply_langgraph_patch()
    assert isinstance(out, bool)


def test_pydantic_ai_patch_registered():
    from abidex.patches.pydantic_ai import apply_pydantic_ai_patch
    out = apply_pydantic_ai_patch()
    assert isinstance(out, bool)


def test_stubs_return_false():
    from abidex.patches.autogen_stub import apply_autogen_patch
    from abidex.patches.llamaindex_stub import apply_llamaindex_patch
    assert apply_autogen_patch() is False
    assert apply_llamaindex_patch() is False
