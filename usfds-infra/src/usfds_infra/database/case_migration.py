from sqlalchemy import MetaData, inspect
from sqlalchemy.schema import CreateIndex, CreateTable

from usfds_infra.database.case_models import CaseModel


def migrate_case_sources(engine) -> None:
	if engine.dialect.name != "sqlite":
		return
	with engine.connect() as connection:
		if inspect(connection).has_table("investigation_cases"):
			if connection.exec_driver_sql("SELECT COUNT(*) FROM investigation_cases").scalar_one():
				raise RuntimeError("Legacy investigation_cases contains data; migrate it before removing the table")
			connection.exec_driver_sql("DROP TABLE investigation_cases")
			connection.commit()
		columns = inspect(connection).get_columns("fraud_cases")
		if next(column for column in columns if column["name"] == "dataset_artifact_id")["nullable"]:
			return
		connection.commit()
		connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
		connection.commit()
		try:
			with connection.begin():
				connection.exec_driver_sql("BEGIN IMMEDIATE")
				target = CaseModel.__table__.to_metadata(MetaData(), name="fraud_cases_source_upgrade")
				connection.execute(CreateTable(target))
				quoted = ", ".join(connection.dialect.identifier_preparer.quote(column.name) for column in target.columns)
				connection.exec_driver_sql(f"INSERT INTO fraud_cases_source_upgrade ({quoted}) SELECT {quoted} FROM fraud_cases")
				connection.exec_driver_sql("DROP TABLE fraud_cases")
				connection.exec_driver_sql("ALTER TABLE fraud_cases_source_upgrade RENAME TO fraud_cases")
				for index in CaseModel.__table__.indexes:
					connection.execute(CreateIndex(index))
				if connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall():
					raise RuntimeError("Case source migration failed foreign key validation")
		finally:
			connection.exec_driver_sql("PRAGMA foreign_keys=ON")
			connection.commit()