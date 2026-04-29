#!/usr/bin/env python3
"""
Backward-compatible entry; prefer :func:`docprinter.cli.main`.

Author: Vasiliy Zdanovskiy
email: vasilyvz@gmail.com
"""

from __future__ import annotations

from docprinter.cli import main

__all__ = ["main"]

if __name__ == "__main__":
    main()
