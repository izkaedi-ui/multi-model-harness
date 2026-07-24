# telemetry/server.py

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass

log = logging.getLogger(__name__)


@dataclass(slots=True)
class MetricsServer:
    port: int = 9464
    address: str = "127.0.0.1"
    _started: bool = False
    _lock: threading.Lock = threading.Lock()

    def start(self) -> bool:
        with self._lock:
            if self._started:
                return True

            try:
                from prometheus_client import start_http_server
                start_http_server(
                    port=self.port,
                    addr=self.address,
                )
                self._started = True
                log.info(f"Prometheus metrics server bound to http://{self.address}:{self.port}/metrics")
                return True
            except Exception:
                log.warning("telemetry.server_start_failed", exc_info=True)
                return False
