-- 001_ideas.sql — initial ideas-box schema.

CREATE TABLE IF NOT EXISTS ideas (
    id               bigserial PRIMARY KEY,
    title            text NOT NULL CHECK (length(title) BETWEEN 1 AND 200),
    body             text NOT NULL CHECK (length(body)  BETWEEN 1 AND 5000),
    submitter_email  text NOT NULL,
    submitter_name   text,
    category         text,
    store_id         integer,
    status           text NOT NULL DEFAULT 'new'
                     CHECK (status IN ('new','triaged','planned','in_progress',
                                       'shipped','declined','duplicate')),
    votes            integer NOT NULL DEFAULT 0,
    tags             text[]  NOT NULL DEFAULT '{}',
    triaged_by       text,
    resolution_note  text,
    resolved_at      timestamptz,
    created_at       timestamptz NOT NULL DEFAULT now(),
    updated_at       timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ideas_status_idx       ON ideas (status);
CREATE INDEX IF NOT EXISTS ideas_created_at_idx   ON ideas (created_at DESC);
CREATE INDEX IF NOT EXISTS ideas_submitter_idx    ON ideas (submitter_email);

CREATE OR REPLACE FUNCTION touch_updated_at() RETURNS trigger AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS ideas_touch ON ideas;
CREATE TRIGGER ideas_touch
BEFORE UPDATE ON ideas
FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
