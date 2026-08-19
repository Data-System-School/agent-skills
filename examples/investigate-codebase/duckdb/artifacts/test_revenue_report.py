"""Tests for revenue_report.monthly_segment_revenue (generated alongside it)."""

from decimal import Decimal

import duckdb
import pytest

from revenue_report import SCHEMA, monthly_segment_revenue


@pytest.fixture()
def con():
    c = duckdb.connect()
    c.execute(SCHEMA)
    c.execute("""
        INSERT INTO customers VALUES
            (1, 'enterprise', '2023-01-05'),
            (2, 'smb',        '2023-02-11'),
            (3, 'enterprise', '2023-03-02');
    """)
    c.execute("""
        INSERT INTO orders VALUES
            (10, 1, '2024-03-04 10:00:00', 100.00, 'shipped'),
            (11, 2, '2024-03-15 09:30:00',  40.00, 'shipped'),
            (12, 3, '2024-03-20 17:45:00',  60.00, 'cancelled'),
            (13, 1, '2024-04-02 08:00:00', 999.00, 'shipped');
    """)
    c.execute("""
        INSERT INTO order_items VALUES
            (10, 'sku-a', 2, 50.00),
            (11, 'sku-b', 4, 10.00),
            (12, 'sku-c', 1, 60.00),
            (13, 'sku-d', 3, 333.00);
    """)
    yield c
    c.close()


def test_groups_by_segment(con):
    rows = monthly_segment_revenue(con, '2024-03')
    assert [r[0] for r in rows] == ['enterprise', 'smb']


def test_revenue_per_segment(con):
    rows = dict((r[0], r[1]) for r in monthly_segment_revenue(con, '2024-03'))
    assert rows['enterprise'] == Decimal('100.00')
    assert rows['smb'] == Decimal('40.00')


def test_excludes_cancelled_orders(con):
    rows = dict((r[0], r[1]) for r in monthly_segment_revenue(con, '2024-03'))
    assert rows['enterprise'] == Decimal('100.00')          # order 12 not counted


def test_excludes_other_months(con):
    rows = dict((r[0], r[1]) for r in monthly_segment_revenue(con, '2024-03'))
    assert Decimal('999.00') not in rows.values()


def test_order_count_and_units(con):
    rows = dict((r[0], (r[2], r[3])) for r in monthly_segment_revenue(con, '2024-03'))
    assert rows['enterprise'] == (1, 2)
    assert rows['smb'] == (1, 4)


def test_empty_month_returns_no_rows(con):
    assert monthly_segment_revenue(con, '2024-12') == []
