import sys
import os

# Monkeypatch starlette.middleware.gzip to fix streamlit compatibility
try:
    import starlette.middleware.gzip
    if not hasattr(starlette.middleware.gzip, "DEFAULT_EXCLUDED_CONTENT_TYPES"):
        starlette.middleware.gzip.DEFAULT_EXCLUDED_CONTENT_TYPES = ("text/event-stream",)
    if not hasattr(starlette.middleware.gzip, "IdentityResponder"):
        class IdentityResponder:
            def __init__(self, app) -> None:
                self.app = app
            async def __call__(self, scope, receive, send) -> None:
                await self.app(scope, receive, send)
        starlette.middleware.gzip.IdentityResponder = IdentityResponder
except ImportError:
    pass

import streamlit.web.cli as stcli

if __name__ == "__main__":
    # Ensure working directory is frontend
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    sys.argv = ["streamlit", "run", "Home.py"]
    sys.exit(stcli.main())
