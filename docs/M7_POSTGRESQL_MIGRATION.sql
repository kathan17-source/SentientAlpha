BEGIN;

-- Running upgrade 0008_machine_learning -> 0009_strategy_discovery

CREATE TABLE strategy_discoveries (
    id VARCHAR(36) NOT NULL, 
    idempotency_key VARCHAR(80) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    status VARCHAR(32) NOT NULL, 
    manifest JSON NOT NULL, 
    inputs JSON NOT NULL, 
    result JSON NOT NULL, 
    PRIMARY KEY (id), 
    UNIQUE (idempotency_key)
);

CREATE TABLE strategy_candidates (
    id VARCHAR(36) NOT NULL, 
    discovery_id VARCHAR(36) NOT NULL, 
    fold INTEGER NOT NULL, 
    rule_hash VARCHAR(64) NOT NULL, 
    status VARCHAR(32) NOT NULL, 
    validation_score VARCHAR(64), 
    payload JSON NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_discovery_rule UNIQUE (discovery_id, fold, rule_hash), 
    FOREIGN KEY(discovery_id) REFERENCES strategy_discoveries (id)
);

CREATE TABLE strategy_holdouts (
    id VARCHAR(36) NOT NULL, 
    discovery_id VARCHAR(36) NOT NULL, 
    fold INTEGER NOT NULL, 
    provider VARCHAR(40) NOT NULL, 
    start DATE NOT NULL, 
    "end" DATE NOT NULL, 
    tickers JSON NOT NULL, 
    status VARCHAR(24) NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_discovery_holdout UNIQUE (discovery_id, fold), 
    FOREIGN KEY(discovery_id) REFERENCES strategy_discoveries (id)
);

UPDATE alembic_version SET version_num='0009_strategy_discovery' WHERE alembic_version.version_num = '0008_machine_learning';

COMMIT;

