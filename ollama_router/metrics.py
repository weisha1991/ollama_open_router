import threading
import time


class Metrics:
    """Thread-safe Prometheus-style metrics collector (zero dependencies)."""

    def __init__(self):
        self._lock = threading.Lock()
        self._counters: dict[str, dict[str, float]] = {}
        self._start_time = time.time()

    def inc(self, name: str, labels: dict[str, str] | None = None, value: float = 1.0):
        label_str = self._format_labels(labels)
        with self._lock:
            name_entry = self._counters.setdefault(name, {})
            name_entry[label_str] = name_entry.get(label_str, 0.0) + value

    def _format_labels(self, labels: dict[str, str] | None) -> str:
        if not labels:
            return ""
        return ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))

    def generate(self) -> str:
        with self._lock:
            lines = [
                "# HELP ollama_router_uptime_seconds Seconds since server start",
                "# TYPE ollama_router_uptime_seconds gauge",
                f"ollama_router_uptime_seconds {time.time() - self._start_time:.2f}",
            ]

            for name, label_values in sorted(self._counters.items()):
                lines.append(f"# HELP ollama_router_{name} Total count")
                lines.append(f"# TYPE ollama_router_{name} counter")
                for label_str, val in sorted(label_values.items()):
                    if label_str:
                        lines.append(f"ollama_router_{name}{{{label_str}}} {val:.0f}")
                    else:
                        lines.append(f"ollama_router_{name} {val:.0f}")

            return "\n".join(lines) + "\n"


metrics = Metrics()
