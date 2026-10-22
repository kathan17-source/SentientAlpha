BEGIN;

-- Running upgrade 0005_sentiment -> 0006_backtesting

CREATE TABLE backtest_runs (
    id VARCHAR(36) NOT NULL, 
    started_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    status VARCHAR(24) NOT NULL, 
    manifest JSON NOT NULL, 
    snapshot JSON NOT NULL, 
    metrics JSON NOT NULL, 
    diagnostics JSON NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT valid_backtest_status CHECK (status IN ('completed','insufficient_data','failed'))
);

CREATE TABLE backtest_artifacts (
    id SERIAL NOT NULL, 
    run_id VARCHAR(36) NOT NULL, 
    kind VARCHAR(24) NOT NULL, 
    sequence INTEGER NOT NULL, 
    payload JSON NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_backtest_artifact UNIQUE (run_id, kind, sequence), 
    CONSTRAINT valid_artifact_sequence CHECK (sequence >= 0), 
    FOREIGN KEY(run_id) REFERENCES backtest_runs (id)
);

CREATE INDEX ix_backtest_artifacts_run_id ON backtest_artifacts (run_id);

UPDATE alembic_version SET version_num='0006_backtesting' WHERE alembic_version.version_num = '0005_sentiment';

COMMIT;

