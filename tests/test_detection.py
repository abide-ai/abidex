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

def test_llama_index_patch_registered():
    from abidex.patches.llama_index import apply_llama_index_patch
    out = apply_llama_index_patch()
    assert isinstance(out, bool)

def test_n8n_sdk_python_patch_registered():
    from abidex.patches.n8n_sdk_python import apply_n8n_sdk_python_patch
    out = apply_n8n_sdk_python_patch()
    assert isinstance(out, bool)