"""Deterministic, credential-free environment for worker/public test execution."""


def public_environment():
    return {"HOME": "/tmp/hx-home", "HF_HOME": "/tmp/hx-home/.cache/huggingface",
        "HF_HUB_CACHE": "/tmp/hx-home/.cache/huggingface/hub",
        "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1",
        "BABEL_DISABLE_CACHE": "1"}


def docker_environment():
    return [item for key, value in public_environment().items() for item in ("-e", key + "=" + value)]
