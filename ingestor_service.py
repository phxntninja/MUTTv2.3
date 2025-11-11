#!/usr/bin/env python3
"""
Shim module delegating to services.ingestor_service.
This file exists to preserve backwards-compatible imports and local runs.
"""

import os

from services.ingestor_service import create_app  # type: ignore


if __name__ == '__main__':
    app = create_app()
    port = int(os.environ.get('SERVER_PORT_INGESTOR', os.environ.get('INGESTOR_PORT', 8080)))
    app.run(host='0.0.0.0', port=port, debug=True)

