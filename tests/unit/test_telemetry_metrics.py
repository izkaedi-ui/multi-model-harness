# tests/unit/test_telemetry_metrics.py

from telemetry.metrics import MetricsRuntime


class FakeLabelSet:
    def __init__(self) -> None:
        self.count = 0
        self.observed: list[float] = []

    def inc(self, amount: float = 1) -> None:
        self.count += amount

    def dec(self, amount: float = 1) -> None:
        self.count -= amount

    def observe(self, amount: float) -> None:
        self.observed.append(amount)


class FakeMetric:
    def __init__(self) -> None:
        self.labels_called: list[dict[str, str]] = []
        self.label_set = FakeLabelSet()

    def labels(self, **kwargs: str) -> FakeLabelSet:
        self.labels_called.append(kwargs)
        return self.label_set


def test_metrics_runtime_recording() -> None:
    fake_req = FakeMetric()
    fake_retry = FakeMetric()
    runtime = MetricsRuntime(requests=fake_req, retries=fake_retry)

    runtime.record_request(provider="openai", model="gpt-4o", status="success")
    assert fake_req.label_set.count == 1
    assert fake_req.labels_called[0] == {"provider": "openai", "model": "gpt-4o", "status": "success"}

    runtime.record_retry(provider="openai", model="gpt-4o", reason="arbitrary_text")
    assert fake_retry.labels_called[0]["reason"] == "other"
