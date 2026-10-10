import os
from pathlib import Path
import tempfile
import unittest
from sqlalchemy import text
from sqlalchemy.orm import Mapped, mapped_column

from usfds_infra.database import (
    Base,
    close_db,
    create_session_factory,
    create_sqlite_engine,
    init_db,
    session_scope,
)


class DummyModel(Base):
    __tablename__ = "dummy_test_table"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column()


class TestDatabaseConnection(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="usfds_db_test_")
        self.db_path = Path(self.temp_dir) / "test_usfds.db"
        self.engine = create_sqlite_engine(db_path=self.db_path)
        self.session_factory = create_session_factory(self.engine)

    def tearDown(self):
        close_db(self.engine)
        if os.path.exists(self.temp_dir):
            import shutil
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_sqlite_pragmas_applied(self):
        """Verify WAL mode, busy_timeout, and foreign_keys are correctly applied."""
        with self.engine.connect() as conn:
            # WAL mode check
            wal_res = conn.execute(text("PRAGMA journal_mode;")).scalar()
            self.assertEqual(wal_res.lower(), "wal")

            # Foreign keys check
            fk_res = conn.execute(text("PRAGMA foreign_keys;")).scalar()
            self.assertEqual(fk_res, 1)

            # Busy timeout check
            timeout_res = conn.execute(text("PRAGMA busy_timeout;")).scalar()
            self.assertEqual(timeout_res, 5000)

    def test_init_db_and_session_scope(self):
        """Verify table creation and CRUD within session_scope."""
        init_db(self.engine)

        with session_scope(self.session_factory) as session:
            dummy = DummyModel(name="test_item")
            session.add(dummy)

        with session_scope(self.session_factory) as session:
            retrieved = session.query(DummyModel).filter_by(name="test_item").first()
            self.assertIsNotNone(retrieved)
            self.assertEqual(retrieved.name, "test_item")

    def test_session_rollback_on_error(self):
        """Verify automatic rollback on exception."""
        init_db(self.engine)

        with self.assertRaises(ValueError):
            with session_scope(self.session_factory) as session:
                dummy = DummyModel(name="will_fail")
                session.add(dummy)
                raise ValueError("Forced error")

        with session_scope(self.session_factory) as session:
            retrieved = session.query(DummyModel).filter_by(name="will_fail").first()
            self.assertIsNone(retrieved)


if __name__ == "__main__":
    unittest.main()
