CREATE TABLE IF NOT EXISTS schema_migrations (
    filename TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE cards (
    id                  BIGINT PRIMARY KEY,
    name                TEXT NOT NULL,
    rarity              TEXT NOT NULL,
    elixir_cost         INT,
    max_level           INT,
    has_evolution       BOOLEAN NOT NULL,
    has_hero            BOOLEAN NOT NULL,
    icon_url            TEXT,
    evolution_icon_url  TEXT,
    hero_icon_url       TEXT
);

CREATE TABLE decks (
    id              BIGSERIAL PRIMARY KEY,
    hash            CHAR(64) NOT NULL UNIQUE,
    card_ids        BIGINT[] NOT NULL,
    evo_card_ids    BIGINT[] NOT NULL,
    hero_card_ids   BIGINT[] NOT NULL
);

CREATE INDEX decks_card_ids_gin ON decks USING GIN (card_ids);

CREATE TABLE players (
    tag     TEXT PRIMARY KEY,
    name    TEXT
);

CREATE TABLE battles (
    timestamp       TIMESTAMPTZ NOT NULL,
    team_tag        TEXT NOT NULL REFERENCES players(tag),
    opp_tag         TEXT REFERENCES players(tag),
    team_deck_id    BIGINT NOT NULL REFERENCES decks(id),
    opp_deck_id     BIGINT NOT NULL REFERENCES decks(id),
    team_rank       INT,
    opp_rank        INT,
    team_crowns     INT,
    opp_crowns      INT,
    PRIMARY KEY (timestamp, team_tag)
);

CREATE INDEX battles_timestamp_idx ON battles (timestamp DESC);
CREATE INDEX battles_team_deck_id_idx ON battles (team_deck_id);
