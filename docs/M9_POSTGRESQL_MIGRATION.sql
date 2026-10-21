BEGIN;

-- Running upgrade 0010_investment_committee -> 0011_risk_management

CREATE TABLE risk_policy_versions (
    key VARCHAR(64) NOT NULL, 
    policy_id VARCHAR(80) NOT NULL, 
    version VARCHAR(80) NOT NULL, 
    effective_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    definition JSON NOT NULL, 
    PRIMARY KEY (key), 
    CONSTRAINT uq_risk_policy_version UNIQUE (policy_id, version)
);

CREATE TABLE risk_assessments (
    id VARCHAR(64) NOT NULL, 
    request_key VARCHAR(80), 
    policy_key VARCHAR(64) NOT NULL, 
    portfolio_id VARCHAR(80) NOT NULL, 
    at TIMESTAMP WITH TIME ZONE NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    status VARCHAR(40) NOT NULL, 
    phase VARCHAR(24) NOT NULL, 
    committee_id VARCHAR(36), 
    backtest_id VARCHAR(36), 
    sequence INTEGER, 
    manifest JSON NOT NULL, 
    inputs JSON NOT NULL, 
    payload JSON NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_risk_committee_event UNIQUE (committee_id, sequence), 
    UNIQUE (request_key), 
    FOREIGN KEY(policy_key) REFERENCES risk_policy_versions (key), 
    FOREIGN KEY(committee_id) REFERENCES committee_runs (id), 
    FOREIGN KEY(backtest_id) REFERENCES backtest_runs (id)
);

CREATE INDEX ix_risk_assessments_portfolio_id ON risk_assessments (portfolio_id);

CREATE INDEX ix_risk_assessments_at ON risk_assessments (at);

CREATE INDEX ix_risk_assessments_committee_id ON risk_assessments (committee_id);

CREATE TABLE risk_alerts (
    id VARCHAR(64) NOT NULL, 
    assessment_id VARCHAR(64) NOT NULL, 
    metric VARCHAR(240) NOT NULL, 
    payload JSON NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_risk_alert UNIQUE (assessment_id, metric), 
    FOREIGN KEY(assessment_id) REFERENCES risk_assessments (id)
);

CREATE INDEX ix_risk_alerts_assessment_id ON risk_alerts (assessment_id);

UPDATE alembic_version SET version_num='0011_risk_management' WHERE alembic_version.version_num = '0010_investment_committee';

COMMIT;

