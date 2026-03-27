# Ref: feat-projects
import pytest
pytest.skip("legacy gitstatus adapter test target not present", allow_module_level=True)


def test_gitstatus_adapter_handles_attribute_and_dict():
    # object with attributes
    class FakeGitStatus:
        def __init__(self):
            self.branch = "main"
            self.dirty = False

    obj = FakeGitStatus()

    normalized = normalize_gitstatus(obj)
    assert normalized.get("branch") == "main"
    assert normalized.get("dirty") is False


def test_gitstatus_adapter_handles_mapping():
    mapping = {"branch": "dev", "dirty": True}
    normalized = normalize_gitstatus(mapping)
    assert normalized.get("branch") == "dev"
    assert normalized.get("dirty") is True
