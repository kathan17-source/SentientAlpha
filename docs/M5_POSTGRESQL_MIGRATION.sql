BEGIN;

-- Running upgrade 0006_backtesting -> 0007_optimization

CREATE TABLE optimization_runs (
    id VARCHAR(36) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    kind VARCHAR(24) NOT NULL, 
    status VARCHAR(32) NOT NULL, 
    manifest JSON NOT NULL, 
    inputs JSON NOT NULL, 
    result JSON NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT valid_optimization_kind CHECK (kind IN ('optimization','frontier','comparison','walk_forward'))
);

UPDATE alembic_version SET version_num='0007_optimization' WHERE alembic_version.version_num = '0006_backtesting';

COMMIT;

