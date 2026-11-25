-- Reference schema for alembic revision 0001 (backend/alembic/versions/0001_services_and_admins.py).
-- Alembic is the source of truth for applying it; keep this file in sync by hand.

CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TYPE service_category AS ENUM ('hospital', 'atm', 'shop', 'other');

CREATE TABLE services (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        VARCHAR(200) NOT NULL,
    category    service_category NOT NULL,
    -- geography => distances in metres. Point order is (X = longitude, Y = latitude).
    location    GEOGRAPHY(POINT, 4326) NOT NULL,
    rating      NUMERIC(2, 1),
    metadata    JSONB,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_services_name_length CHECK (char_length(btrim(name)) BETWEEN 1 AND 200),
    CONSTRAINT ck_services_rating_range CHECK (rating IS NULL OR (rating >= 0 AND rating <= 5)),
    CONSTRAINT ck_services_metadata_object CHECK (metadata IS NULL OR jsonb_typeof(metadata) = 'object')
);

CREATE INDEX ix_services_location   ON services USING gist (location);
CREATE INDEX ix_services_category   ON services (category);
CREATE INDEX ix_services_created_at ON services (created_at);

CREATE TABLE admins (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email         VARCHAR(320) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,  -- bcrypt / argon2 hash, never plaintext
    is_active     BOOLEAN NOT NULL DEFAULT true,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_admins_email_lowercase CHECK (email = lower(email))
);
