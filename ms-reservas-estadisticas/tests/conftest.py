"""SQL real optativo; la suite habitual no abre conexiones externas."""

import pytest


def pytest_addoption(parser):
    parser.addoption("--sql-server", action="store_true", help="Incluir lecturas de SQL Server local.")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--sql-server"):
        return
    for item in items:
        if "sql_server" in item.keywords:
            item.add_marker(pytest.mark.skip(reason="Requiere --sql-server para consultar SQL real."))
