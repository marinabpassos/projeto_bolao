-- Schema do Bolão da Copa 2026 — rode no SQL Editor do Supabase.

create table if not exists users (
    id           bigint generated always as identity primary key,
    email        text not null unique,
    name         text not null default '',
    picture_url  text not null default '',
    is_admin     boolean not null default false,
    created_at   timestamptz not null default now()
);

create table if not exists matches (
    id             bigint generated always as identity primary key,
    stage          text not null,                 -- grupos/16avos/oitavas/quartas/semi/final
    round          int,                           -- 1-3 na fase de grupos
    home_team      text not null,
    away_team      text not null,
    teams_decided  boolean not null default true, -- mata-mata abre quando os times são definidos
    is_brazil      boolean not null default false,
    kickoff_at     timestamptz not null,
    home_score     int,
    away_score     int,
    neymar_played  boolean,                        -- só jogos do Brasil
    endrick_played boolean,
    finished       boolean not null default false,
    who_advanced   text,                             -- 'home' | 'away' | null (mata-mata: quem avançou)
    bracket_pos    int                               -- posição na chave (oitavas 1-8, quartas 1-4, semi 1-2, final 1)
);

create table if not exists predictions (
    id        bigint generated always as identity primary key,
    user_id   bigint not null references users(id) on delete cascade,
    match_id  bigint not null references matches(id) on delete cascade,
    home_pred int not null,
    away_pred int not null,
    points         int not null default 0,
    qualifier_pred text,                            -- 'home' | 'away' | null (mata-mata: quem o usuário acha que avança)
    unique (user_id, match_id)
);

create table if not exists brazil_match_predictions (
    id         bigint generated always as identity primary key,
    user_id    bigint not null references users(id) on delete cascade,
    match_id   bigint not null references matches(id) on delete cascade,
    neymar_in  boolean not null,
    endrick_in boolean not null,
    points     int not null default 0,
    unique (user_id, match_id)
);

create table if not exists artilheiro_predictions (
    id                  bigint generated always as identity primary key,
    user_id             bigint not null unique references users(id) on delete cascade,
    player              text not null,
    tier_points_at_edit int not null,
    updated_at          timestamptz not null default now(),
    points              int not null default 0
);

create table if not exists brazil_progress_predictions (
    id           bigint generated always as identity primary key,
    user_id      bigint not null unique references users(id) on delete cascade,
    phase_choice text not null,
    updated_at   timestamptz not null default now(),
    points       int not null default 0
);

create table if not exists settlement (
    id                 int primary key default 1,
    top_scorer         text not null default '',
    brazil_final_phase text not null default ''
);

-- Garante a linha única de gabaritos.
insert into settlement (id) values (1) on conflict (id) do nothing;

create index if not exists idx_predictions_match on predictions(match_id);
create index if not exists idx_brmatch_match on brazil_match_predictions(match_id);

-- Migração para bancos já criados (rodar uma vez no SQL Editor do Supabase):
-- alter table matches add column if not exists bracket_pos int;
