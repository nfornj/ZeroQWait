-- Reset all user passwords to: password123
-- Password hash: $2b$12$RP7Mw0f/YbZ1THG9HnfxF.H8TrXvJWmCyNiUiyMqTsWxcZTIZiHhG
UPDATE users SET hashed_password = E'$2b$12$RP7Mw0f/YbZ1THG9HnfxF.H8TrXvJWmCyNiUiyMqTsWxcZTIZiHhG';
