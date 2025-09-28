from __future__ import annotations

import logging

from prometheus_client import start_http_server

logger = logging.getLogger(__name__)


class PrometheusExporter:
    def __init__(self, port: int = 8001) -> None:
        self.port = port
        self._started = False

    def ensure_started(self) -> None:
        if self._started:
            return
        start_http_server(self.port)
        logger.info("Prometheus exporter started on port %s", self.port)
        self._started = True

