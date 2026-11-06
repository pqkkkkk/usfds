-- Apache AGE: extension + default graph for fraud-ring / link analysis.
-- NOTE: do NOT set a database-wide search_path to ag_catalog; it would make
-- SQLAlchemy create relational tables inside ag_catalog. Sessions that run
-- Cypher must `LOAD 'age'; SET search_path = ag_catalog, "$user", public;` themselves.
CREATE EXTENSION IF NOT EXISTS age;
LOAD 'age';
SET search_path = ag_catalog, "$user", public;
SELECT create_graph('usfds_graph')
WHERE NOT EXISTS (SELECT 1 FROM ag_catalog.ag_graph WHERE name = 'usfds_graph');
