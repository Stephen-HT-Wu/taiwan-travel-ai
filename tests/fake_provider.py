from providers.base import TextBlock, ToolUseBlock, TurnResult


def make_fake_provider(turn_specs):
    state = {"index": 0}

    class FakeProvider:
        def stream_turn(self, **kwargs):
            spec = turn_specs[state["index"]]
            state["index"] += 1

            def generator():
                for event in spec.get("events", []):
                    yield event
                return spec["result"]

            return generator()

        def create_turn(self, **kwargs):
            spec = turn_specs[state["index"]]
            state["index"] += 1
            return spec["result"]

    return FakeProvider()
