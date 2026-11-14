-- Minimal authentication table used by /api/auth/*.
-- New demo credentials are stored as a Werkzeug hash (scrypt). The API still
-- accepts legacy plain-text rows and upgrades them on the first successful
-- login, so older databases keep working.

CREATE TABLE IF NOT EXISTS accounts (
    username VARCHAR(100) PRIMARY KEY,
    password VARCHAR(255) NOT NULL
);

-- Demo account for local runs / defence: admin / admin123
-- Change or delete it before any real use.
INSERT INTO accounts (username, password)
VALUES (
    'admin',
    'scrypt:32768:8:1$CyUlAA8PIcuZUIR3$e6cceda994f1f782b901db34cb1daf9b484dc2615a5637d5bf25f4cef91c4ef42a79430f60a27c5a8071b30e7b897494269700812139a43489441368231e77b2'
)
ON CONFLICT (username) DO NOTHING;
