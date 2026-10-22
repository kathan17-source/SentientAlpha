BEGIN;

-- Running upgrade 0009_strategy_discovery -> 0010_investment_committee

CREATE TABLE committee_runs (
    id VARCHAR(36) NOT NULL, 
    idempotency_key VARCHAR(80) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    status VARCHAR(32) NOT NULL, 
    backtest_id VARCHAR(36), 
    manifest JSON NOT NULL, 
    inputs JSON NOT NULL, 
    result JSON NOT NULL, 
    PRIMARY KEY (id), 
    UNIQUE (idempotency_key), 
    FOREIGN KEY(backtest_id) REFERENCES backtest_runs (id)
);

CREATE TABLE committee_decisions (
    id VARCHAR(36) NOT NULL, 
    run_id VARCHAR(36) NOT NULL, 
    sequence INTEGER NOT NULL, 
    decision_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    payload JSON NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_committee_decision UNIQUE (run_id, sequence), 
    FOREIGN KEY(run_id) REFERENCES committee_runs (id)
);

CREATE INDEX ix_committee_decisions_run_id ON committee_decisions (run_id);

UPDATE alembic_version SET version_num='0010_investment_committee' WHERE alembic_version.version_num = '0009_strategy_discovery';

COMMIT;

