"""Incumbent executable loop: one worker call, no extra context/tool requests."""


def next_action(state):
    return {"action": "finish" if state["worker_calls"] else "delegate",
            "query": "", "guidance": "", "memory": {}, "context": {},
            "omit_optional_context": []}
