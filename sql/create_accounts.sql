-- Minimal authentication table assumed by the Flask backend (/api/auth/*).
-- Credentials are stored in plain text because the assignment explicitly
-- states that the login/logout endpoints do not need to be secure.

CREATE TABLE IF NOT EXISTS accounts (
    username VARCHAR(100) PRIMARY KEY,
    password VARCHAR(255) NOT NULL
);

-- Demo account for local runs / defence. Change or delete it before any real use.
INSERT INTO accounts (username, password)
VALUES ('admin', 'admin123')
ON CONFLICT (username) DO NOTHING;
