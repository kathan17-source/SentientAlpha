BEGIN;

-- Running upgrade 0007_optimization -> 0008_machine_learning

CREATE TABLE ml_experiments (
    id VARCHAR(36) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    status VARCHAR(32) NOT NULL, 
    manifest JSON NOT NULL, 
    inputs JSON NOT NULL, 
    result JSON NOT NULL, 
    PRIMARY KEY (id)
);

CREATE TABLE ml_models (
    id VARCHAR(36) NOT NULL, 
    experiment_id VARCHAR(36) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    version VARCHAR(64) NOT NULL, 
    payload JSON NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(experiment_id) REFERENCES ml_experiments (id)
);

CREATE TABLE ml_predictions (
    id VARCHAR(36) NOT NULL, 
    model_id VARCHAR(36) NOT NULL, 
    ticker VARCHAR(12) NOT NULL, 
    decision_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    generated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    payload JSON NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_ml_forecast_version UNIQUE (model_id, ticker, decision_at), 
    FOREIGN KEY(model_id) REFERENCES ml_models (id)
);

CREATE INDEX ix_ml_ticker_time ON ml_predictions (ticker, decision_at);

UPDATE alembic_version SET version_num='0008_machine_learning' WHERE alembic_version.version_num = '0007_optimization';

COMMIT;

