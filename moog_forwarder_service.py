#!/usr/bin/env python3
"""
Shim module delegating to services.moog_forwarder_service.
This file exists to preserve backwards-compatible imports and local runs.
"""

from services.moog_forwarder_service import main  # type: ignore


if __name__ == '__main__':
    main()

