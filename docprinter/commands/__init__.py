"""
Application commands (MCP proxy adapter ``Command`` subclasses).

Author: Vasiliy Zdanovskiy
email: vasilyvz@gmail.com
"""

from docprinter.commands.get_print_result_command import GetPrintResultCommand
from docprinter.commands.print_command import PrintCommand
from docprinter.commands.registration import (
    PRINT_LEGACY_DOCBYTPL_NOTE,
    PRINT_RESULT_COMPANION_NOTE,
    PRINT_SCHEMA_DISCOVERY_SHORT,
)

__all__ = [
    "PRINT_LEGACY_DOCBYTPL_NOTE",
    "PRINT_RESULT_COMPANION_NOTE",
    "PRINT_SCHEMA_DISCOVERY_SHORT",
    "GetPrintResultCommand",
    "PrintCommand",
]
