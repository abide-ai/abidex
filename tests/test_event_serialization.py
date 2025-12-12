from dataclasses import dataclass

from abidex.client import Event, EventType


@dataclass
class NestedPayload:
    name: str
    count: int


@dataclass
class WrapperPayload:
    nested: NestedPayload
    notes: list
    flag: bool = True


def test_to_dict_serializes_nested_dataclasses():
    payload = WrapperPayload(
        nested=NestedPayload(name="inner", count=3),
        notes=["alpha", "beta"],
    )
    event = Event(
        event_type=EventType.LOG,
        metadata={"payload": payload},
    )

    event.set_action_info(
        action_type="tool_call",
        name="serialize_nested",
        input_data=payload,
        output_data={"result": payload},
    )

    result = event.to_dict()

    assert result["metadata"]["payload"]["nested"]["name"] == "inner"
    assert result["metadata"]["payload"]["notes"] == ["alpha", "beta"]
    assert result["action"]["input"]["nested"]["count"] == 3
    assert result["action"]["output"]["result"]["nested"]["name"] == "inner"


def test_truncation_preserves_structure():
    long_prompt = "p" * 260
    nested_input = {
        "request": {
            "prompt": long_prompt,
            "meta": {"hint": "h" * 520},
        }
    }

    event = Event(event_type=EventType.TOOL_CALL_START)
    event.set_action_info(
        action_type="tool_call",
        name="truncate_nested",
        input_data=nested_input,
        output_data={"response": {"text": "o" * 550}},
    )
    event.set_model_call_info(
        backend="backend",
        model="model-x",
        prompt=nested_input,
        completion={"text": "c" * 600},
    )

    result = event.to_dict()

    action_input = result["action"]["input"]
    assert isinstance(action_input["request"], dict)
    assert action_input["request"]["prompt"].endswith("...")
    assert len(action_input["request"]["prompt"]) <= 203

    model_prompt = result["model_call"]["prompt_preview"]
    assert model_prompt["request"]["meta"]["hint"].endswith("...")
    assert len(model_prompt["request"]["meta"]["hint"]) <= 503

    action_output_text = result["action"]["output"]["response"]["text"]
    assert action_output_text.endswith("...")
    assert len(action_output_text) <= 503
