#!/usr/bin/env python3
"""
Shim module delegating to services.web_ui_service.
This file exists to preserve backwards-compatible imports and local runs.
"""

import os

from services.web_ui_service import create_app  # type: ignore
try:
    from services.web_ui_service import setup_signal_handlers  # type: ignore
except Exception:
    def setup_signal_handlers(app):
        return None


if __name__ == '__main__':
    app = create_app()
    setup_signal_handlers(app)
    port = int(os.environ.get('SERVER_PORT_WEBUI', os.environ.get('WEBUI_PORT', 8090)))
    app.run(host='0.0.0.0', port=port, debug=True)

