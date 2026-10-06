"""Shared fixtures. The tests run against the warehouse built by `python -m pipeline.run build`."""
import os

import psycopg
import pytest

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres@localhost:5432/recruiting")
DATA_END = "2025-12-31"


class Db:
    def __init__(self, conn):
        self.conn = conn

    def scalar(self, sql, params=None):
        with self.conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchone()[0]

    def rows(self, sql, params=None):
        with self.conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()

    def execute(self, sql, params=None):
        with self.conn.cursor() as cur:
            cur.execute(sql, params)


@pytest.fixture(scope="session")
def db():
    with psycopg.connect(DATABASE_URL, autocommit=True) as conn:
        yield Db(conn)


@pytest.fixture()
def scratch():
    """A connection whose changes are always rolled back, for tests that plant bad data."""
    conn = psycopg.connect(DATABASE_URL)
    try:
        yield Db(conn)
    finally:
        conn.rollback()
        conn.close()
