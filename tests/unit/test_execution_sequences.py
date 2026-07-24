"""
Unit and state transition tests for execution sequences and recovery paths.
"""
import unittest

from adapters.base_adapter import BaseAdapter
from security_harness.errors import NonRetryableProviderError
from security_harness.types import ModelRequest, ModelResponse, TokenUsage


class MockSequenceAdapter(BaseAdapter):
    """Adapter that returns predetermined outcomes in exact call order."""

    provider_name = "mock"

    def __init__(self, outcomes: list[ModelResponse | Exception]):
        super().__init__(retry_config={"max_attempts": 2, "base_delay_seconds": 0.01})
        self._outcomes = outcomes
        self.call_count = 0

    async def _generate_raw(self, request: ModelRequest) -> ModelResponse:
        if self.call_count >= len(self._outcomes):
            raise RuntimeError("Exhausted mock sequence outcomes")
        outcome = self._outcomes[self.call_count]
        self.call_count += 1
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    async def health_check(self) -> bool:
        return True

    async def close(self) -> None:
        pass


class TestExecutionSequences(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.req = ModelRequest(
            model="mock-model",
            messages=[{"role": "user", "content": "Hello"}],
            temperature=0.7,
            max_output_tokens=100,
        )

    def _make_resp(self, text: str, msg_id: str) -> ModelResponse:
        return ModelResponse(
            provider="mock",
            model="mock-model",
            text=text,
            finish_reason="stop",
            tool_calls=(),
            usage=TokenUsage(10, 20, 30),
            latency_ms=15,
            raw_response={"id": msg_id},
        )

    async def test_fail_then_succeed_sequence(self):
        """
        Verify exact sequence: FAIL -> SUCCEED in that order.
        First call fails with NonRetryableProviderError, second call succeeds.
        """
        resp_success = self._make_resp("Hello", "msg_1")

        adapter = MockSequenceAdapter([
            NonRetryableProviderError("mock", 400, "Bad Request"),
            resp_success,
        ])

        # Step 1: Call 1 must FAIL
        with self.assertRaises(NonRetryableProviderError):
            await adapter.generate(self.req)
        self.assertEqual(adapter.call_count, 1)

        # Step 2: Call 2 must SUCCEED
        res2 = await adapter.generate(self.req)
        self.assertEqual(res2.text, "Hello")
        self.assertEqual(adapter.call_count, 2)

    async def test_succeed_fail_succeed_sequence(self):
        """
        Verify exact sequence: SUCCEED -> FAIL -> SUCCEED in that order.
        First call succeeds, second call fails with NonRetryableProviderError, third call succeeds.
        """
        resp_1 = self._make_resp("Resp 1", "msg_1")
        resp_3 = self._make_resp("Resp 3", "msg_3")

        adapter = MockSequenceAdapter([
            resp_1,
            NonRetryableProviderError("mock", 404, "Not Found"),
            resp_3,
        ])

        # Step 1: SUCCEED
        res1 = await adapter.generate(self.req)
        self.assertEqual(res1.text, "Resp 1")
        self.assertEqual(adapter.call_count, 1)

        # Step 2: FAIL
        with self.assertRaises(NonRetryableProviderError):
            await adapter.generate(self.req)
        self.assertEqual(adapter.call_count, 2)

        # Step 3: SUCCEED
        res3 = await adapter.generate(self.req)
        self.assertEqual(res3.text, "Resp 3")
        self.assertEqual(adapter.call_count, 3)


if __name__ == "__main__":
    unittest.main()
