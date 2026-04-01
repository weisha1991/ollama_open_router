#!/usr/bin/env python3
"""Health check script for Docker.

Uses only stdlib (no curl needed).
"""

import sys
import urllib.request


def main() -> int:
    try:
        with urllib.request.urlopen(
            "http://localhost:11435/health",
            timeout=5,
        ) as response:
            if response.status == 200:
                return 0
            return 1
    except Exception:
        return 1


if __name__ == "__main__":
    sys.exit(main())
