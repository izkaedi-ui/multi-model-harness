"""Response store — in-memory write-through cache for responses during a run."""
from __future__ import annotations
from security_harness.types import ModelResponse

class ResponseStore:
    def __init__(self) -> None:
        self._data: dict[str, ModelResponse] = {}

    def put(self, execution_id: str, response: ModelResponse) -> None:
        self._data[execution_id] = response

    def get(self, execution_id: str) -> ModelResponse | None:
        return self._data.get(execution_id)

    def all(self) -> dict[str, ModelResponse]:
        return dict(self._data)
