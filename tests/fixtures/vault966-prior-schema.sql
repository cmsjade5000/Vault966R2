-- Read-only observed schema definitions; contains no application rows.
CREATE TABLE ai_cache (
	cache_key VARCHAR(120) NOT NULL,
	value JSON NOT NULL,
	expires_at DATETIME,
	created_at DATETIME DEFAULT (CURRENT_TIMESTAMP) NOT NULL,
	PRIMARY KEY (cache_key)
);

CREATE TABLE alembic_version (
	version_num VARCHAR(32) NOT NULL,
	CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

CREATE TABLE app_setup (
	id INTEGER NOT NULL,
	completed BOOLEAN DEFAULT false NOT NULL,
	completed_at DATETIME,
	owner_profile_id INTEGER,
	created_at DATETIME DEFAULT (CURRENT_TIMESTAMP) NOT NULL,
	updated_at DATETIME DEFAULT (CURRENT_TIMESTAMP) NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(owner_profile_id) REFERENCES profiles (id) ON DELETE SET NULL
);

CREATE TABLE flic_memory (
	id INTEGER NOT NULL,
	movie_id INTEGER NOT NULL,
	created_at DATETIME DEFAULT (CURRENT_TIMESTAMP) NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(movie_id) REFERENCES movies (id) ON DELETE CASCADE
);

CREATE TABLE flic_presets (
	id INTEGER NOT NULL,
	name VARCHAR(100) NOT NULL,
	filters JSON NOT NULL,
	created_at DATETIME DEFAULT (CURRENT_TIMESTAMP) NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (name)
);

CREATE TABLE genres (
	id INTEGER NOT NULL,
	name VARCHAR(100) NOT NULL,
	PRIMARY KEY (id)
);

CREATE TABLE maintenance_jobs (
	id INTEGER NOT NULL,
	run_id VARCHAR(80) NOT NULL,
	task_id VARCHAR(40) NOT NULL,
	state VARCHAR(20) NOT NULL,
	started_by_profile_id INTEGER,
	started_at DATETIME NOT NULL,
	finished_at DATETIME,
	last_error TEXT,
	steps JSON,
	reports JSON,
	created_at DATETIME DEFAULT (CURRENT_TIMESTAMP) NOT NULL,
	updated_at DATETIME DEFAULT (CURRENT_TIMESTAMP) NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(started_by_profile_id) REFERENCES profiles (id) ON DELETE SET NULL
);

CREATE TABLE moods (
	id INTEGER NOT NULL,
	name VARCHAR(100) NOT NULL,
	description VARCHAR(300),
	emoji VARCHAR(10),
	PRIMARY KEY (id)
);

CREATE TABLE movie_cast (
	movie_id INTEGER NOT NULL,
	person_id INTEGER NOT NULL,
	character VARCHAR(300),
	order_index INTEGER,
	PRIMARY KEY (movie_id, person_id),
	FOREIGN KEY(movie_id) REFERENCES movies (id) ON DELETE CASCADE,
	FOREIGN KEY(person_id) REFERENCES people (id) ON DELETE CASCADE
);

CREATE TABLE movie_crew (
	movie_id INTEGER NOT NULL,
	person_id INTEGER NOT NULL,
	department VARCHAR(200),
	job VARCHAR(200),
	PRIMARY KEY (movie_id, person_id),
	FOREIGN KEY(movie_id) REFERENCES movies (id) ON DELETE CASCADE,
	FOREIGN KEY(person_id) REFERENCES people (id) ON DELETE CASCADE
);

CREATE TABLE movie_documents (
	movie_id INTEGER NOT NULL,
	doc_version INTEGER NOT NULL,
	content TEXT NOT NULL,
	embedding JSON NOT NULL,
	updated_at DATETIME DEFAULT (CURRENT_TIMESTAMP) NOT NULL,
	PRIMARY KEY (movie_id),
	FOREIGN KEY(movie_id) REFERENCES movies (id) ON DELETE CASCADE
);

CREATE TABLE movie_flags (
	movie_id INTEGER NOT NULL,
	reason TEXT,
	notes TEXT,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL, reported_by_profile_id INTEGER
                        REFERENCES profiles(id) ON DELETE SET NULL,
	PRIMARY KEY (movie_id),
	FOREIGN KEY(movie_id) REFERENCES movies (id) ON DELETE CASCADE
);

CREATE TABLE movie_genres (
	movie_id INTEGER NOT NULL,
	genre_id INTEGER NOT NULL,
	PRIMARY KEY (movie_id, genre_id),
	FOREIGN KEY(genre_id) REFERENCES genres (id) ON DELETE CASCADE,
	FOREIGN KEY(movie_id) REFERENCES movies (id) ON DELETE CASCADE
);

CREATE TABLE movie_identity_repairs (
	id INTEGER NOT NULL,
	movie_id INTEGER NOT NULL,
	applied_by_profile_id INTEGER,
	source VARCHAR(20) NOT NULL,
	search_title VARCHAR(300) NOT NULL,
	standardized_title VARCHAR(300) NOT NULL,
	selected_title VARCHAR(300) NOT NULL,
	selected_year INTEGER,
	selected_imdb_id VARCHAR(20),
	selected_tmdb_id INTEGER,
	before_values JSON,
	after_values JSON,
	applied_at DATETIME DEFAULT (CURRENT_TIMESTAMP) NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(movie_id) REFERENCES movies (id) ON DELETE CASCADE,
	FOREIGN KEY(applied_by_profile_id) REFERENCES profiles (id) ON DELETE SET NULL
);

CREATE TABLE movie_ingest_provenance (
	id INTEGER NOT NULL,
	movie_id INTEGER NOT NULL,
	provider VARCHAR(50) NOT NULL,
	provider_id VARCHAR(100),
	ingested_at DATETIME DEFAULT (CURRENT_TIMESTAMP) NOT NULL,
	payload_sha VARCHAR(128),
	etag VARCHAR(128),
	source_url VARCHAR(500),
	notes TEXT,
	PRIMARY KEY (id),
	FOREIGN KEY(movie_id) REFERENCES movies (id) ON DELETE CASCADE
);

CREATE TABLE movie_moods (
	movie_id INTEGER NOT NULL,
	mood_id INTEGER NOT NULL,
	PRIMARY KEY (movie_id, mood_id),
	FOREIGN KEY(mood_id) REFERENCES moods (id) ON DELETE CASCADE,
	FOREIGN KEY(movie_id) REFERENCES movies (id) ON DELETE CASCADE
);

CREATE TABLE movie_preferences (
	id INTEGER NOT NULL,
	profile_id INTEGER NOT NULL,
	movie_id INTEGER NOT NULL,
	liked BOOLEAN DEFAULT false NOT NULL,
	watchlist BOOLEAN DEFAULT false NOT NULL,
	created_at DATETIME DEFAULT (CURRENT_TIMESTAMP) NOT NULL,
	updated_at DATETIME DEFAULT (CURRENT_TIMESTAMP) NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_movie_preferences_profile_movie UNIQUE (profile_id, movie_id),
	FOREIGN KEY(profile_id) REFERENCES profiles (id) ON DELETE CASCADE,
	FOREIGN KEY(movie_id) REFERENCES movies (id) ON DELETE CASCADE
);

CREATE TABLE movie_review_checks (
	id INTEGER NOT NULL,
	movie_id INTEGER NOT NULL,
	issue_type VARCHAR(50) NOT NULL,
	issue_fingerprint VARCHAR(64) NOT NULL,
	decision VARCHAR(20) NOT NULL,
	checked_by_profile_id INTEGER,
	checked_at DATETIME DEFAULT (CURRENT_TIMESTAMP) NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(checked_by_profile_id) REFERENCES profiles (id) ON DELETE SET NULL,
	FOREIGN KEY(movie_id) REFERENCES movies (id) ON DELETE CASCADE,
	CONSTRAINT uq_movie_review_checks_issue UNIQUE (movie_id, issue_type, issue_fingerprint)
);

CREATE TABLE "movies" (
	id INTEGER NOT NULL,
	title VARCHAR(300) NOT NULL,
	year INTEGER,
	runtime INTEGER,
	plot TEXT,
	imdb_id VARCHAR(20),
	tmdb_id INTEGER,
	imdb_rating FLOAT,
	imdb_votes INTEGER,
	rt_score INTEGER,
	where_to_watch TEXT,
	languages TEXT,
	countries TEXT,
	collection TEXT,
	poster_url VARCHAR(500),
	backdrop_url VARCHAR(500),
	metascore INTEGER,
	tomato_meter INTEGER,
	tomato_audience INTEGER,
	awards TEXT,
	last_tmdb_fetch_at DATETIME,
	last_omdb_fetch_at DATETIME,
	tmdb_etag VARCHAR(128),
	tmdb_payload_sha VARCHAR(128),
	omdb_payload_sha VARCHAR(128), certificate VARCHAR(30), keywords JSON, vault_id VARCHAR(20), trailer_site TEXT, trailer_key TEXT, trailer_name TEXT, trailer_url TEXT, trailer_checked_at TIMESTAMP,
	PRIMARY KEY (id),
	UNIQUE (imdb_id)
);

CREATE TABLE owned_movie_copies (
	id INTEGER NOT NULL,
	movie_id INTEGER NOT NULL,
	snapshot_id INTEGER NOT NULL,
	source_row_id INTEGER NOT NULL,
	hd BOOLEAN,
	source_title VARCHAR(300) NOT NULL,
	source_year INTEGER,
	confirmed_at DATETIME DEFAULT (CURRENT_TIMESTAMP) NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(movie_id) REFERENCES movies (id) ON DELETE CASCADE,
	FOREIGN KEY(snapshot_id) REFERENCES source_snapshots (id) ON DELETE CASCADE,
	FOREIGN KEY(source_row_id) REFERENCES source_movie_rows (id) ON DELETE CASCADE,
	CONSTRAINT uq_owned_movie_copies_source_row UNIQUE (source_row_id)
);

CREATE TABLE people (
	id INTEGER NOT NULL,
	name VARCHAR(200) NOT NULL,
	tmdb_id INTEGER,
	imdb_id VARCHAR(20),
	PRIMARY KEY (id),
	CONSTRAINT uq_people_name_tmdb_id UNIQUE (name, tmdb_id)
);

CREATE TABLE profile_credentials (
	id INTEGER NOT NULL,
	profile_id INTEGER NOT NULL,
	access_key_salt VARCHAR(64) NOT NULL,
	access_key_hash VARCHAR(128) NOT NULL,
	passcode_salt VARCHAR(64) NOT NULL,
	passcode_hash VARCHAR(128) NOT NULL,
	kdf_name VARCHAR(40) DEFAULT 'pbkdf2_sha256' NOT NULL,
	kdf_iterations INTEGER DEFAULT 200000 NOT NULL,
	created_at DATETIME DEFAULT (CURRENT_TIMESTAMP) NOT NULL,
	updated_at DATETIME DEFAULT (CURRENT_TIMESTAMP) NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_profile_credentials_profile_id UNIQUE (profile_id),
	FOREIGN KEY(profile_id) REFERENCES profiles (id) ON DELETE CASCADE
);

CREATE TABLE profiles (
	id INTEGER NOT NULL,
	name VARCHAR(80) NOT NULL,
	created_at DATETIME DEFAULT (CURRENT_TIMESTAMP) NOT NULL, role VARCHAR(20) DEFAULT 'reviewer' NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (name)
);

CREATE TABLE retired_vault_ids (
	vault_id VARCHAR(20) NOT NULL,
	retired_at DATETIME DEFAULT (CURRENT_TIMESTAMP) NOT NULL,
	source VARCHAR(40) NOT NULL,
	reason TEXT,
	deleted_movie_id INTEGER,
	deleted_movie_title VARCHAR(300),
	PRIMARY KEY (vault_id)
);

CREATE TABLE roles (
	id INTEGER NOT NULL,
	movie_id INTEGER NOT NULL,
	person_id INTEGER NOT NULL,
	role_type VARCHAR(8) NOT NULL,
	character_name VARCHAR(200),
	billing_order INTEGER,
	PRIMARY KEY (id),
	FOREIGN KEY(movie_id) REFERENCES movies (id) ON DELETE CASCADE,
	FOREIGN KEY(person_id) REFERENCES people (id) ON DELETE CASCADE
);

CREATE TABLE "source_field_decisions" (
	id INTEGER NOT NULL,
	source_row_id INTEGER NOT NULL,
	movie_id INTEGER NOT NULL,
	field_name VARCHAR(30) NOT NULL,
	previous_value TEXT,
	source_value TEXT,
	selected_value TEXT,
	decision VARCHAR(30) NOT NULL,
	decided_by_profile_id INTEGER,
	decided_at DATETIME DEFAULT (CURRENT_TIMESTAMP) NOT NULL,
	resolved_at DATETIME,
	undone_by_profile_id INTEGER,
	undone_at DATETIME,
	PRIMARY KEY (id),
	CONSTRAINT fk_source_field_decisions_undone_by_profile FOREIGN KEY(undone_by_profile_id) REFERENCES profiles (id) ON DELETE SET NULL,
	FOREIGN KEY(movie_id) REFERENCES movies (id) ON DELETE CASCADE,
	FOREIGN KEY(source_row_id) REFERENCES source_movie_rows (id) ON DELETE CASCADE,
	FOREIGN KEY(decided_by_profile_id) REFERENCES profiles (id) ON DELETE SET NULL
);

CREATE TABLE source_movie_rows (
	id INTEGER NOT NULL,
	snapshot_id INTEGER NOT NULL,
	row_number INTEGER NOT NULL,
	title VARCHAR(300) NOT NULL,
	normalized_title VARCHAR(300) NOT NULL,
	runtime INTEGER,
	director VARCHAR(500),
	normalized_directors JSON,
	year INTEGER,
	genre VARCHAR(200),
	content_rating TEXT,
	release_date VARCHAR(80),
	hd BOOLEAN,
	duplicate_group VARCHAR(64),
	raw_data JSON,
	PRIMARY KEY (id),
	FOREIGN KEY(snapshot_id) REFERENCES source_snapshots (id) ON DELETE CASCADE,
	CONSTRAINT uq_source_movie_rows_snapshot_row UNIQUE (snapshot_id, row_number)
);

CREATE TABLE source_reconciliation_matches (
	id INTEGER NOT NULL,
	source_row_id INTEGER NOT NULL,
	movie_id INTEGER,
	match_type VARCHAR(30) NOT NULL,
	confidence FLOAT,
	candidate_movie_ids JSON,
	resolved_at DATETIME,
	PRIMARY KEY (id),
	FOREIGN KEY(movie_id) REFERENCES movies (id) ON DELETE SET NULL,
	FOREIGN KEY(source_row_id) REFERENCES source_movie_rows (id) ON DELETE CASCADE,
	CONSTRAINT uq_source_reconciliation_matches_row UNIQUE (source_row_id)
);

CREATE TABLE source_snapshots (
	id INTEGER NOT NULL,
	filename VARCHAR(255) NOT NULL,
	file_sha256 VARCHAR(64) NOT NULL,
	raw_csv TEXT NOT NULL,
	row_count INTEGER NOT NULL,
	status VARCHAR(20) NOT NULL,
	uploaded_by_profile_id INTEGER,
	uploaded_at DATETIME DEFAULT (CURRENT_TIMESTAMP) NOT NULL,
	confirmed_at DATETIME,
	PRIMARY KEY (id),
	FOREIGN KEY(uploaded_by_profile_id) REFERENCES profiles (id) ON DELETE SET NULL,
	UNIQUE (file_sha256)
);

CREATE TABLE usage_events (
	id INTEGER NOT NULL,
	event_name VARCHAR(40) NOT NULL,
	profile_id INTEGER,
	movie_id INTEGER,
	page VARCHAR(20) NOT NULL,
	context VARCHAR(40),
	created_at DATETIME DEFAULT (CURRENT_TIMESTAMP) NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(profile_id) REFERENCES profiles (id) ON DELETE SET NULL,
	FOREIGN KEY(movie_id) REFERENCES movies (id) ON DELETE SET NULL
);

CREATE INDEX ix_ai_cache_expires_at ON ai_cache (expires_at);

CREATE UNIQUE INDEX ix_genres_name ON genres (name);

CREATE UNIQUE INDEX ix_maintenance_jobs_run_id ON maintenance_jobs (run_id);

CREATE INDEX ix_maintenance_jobs_state ON maintenance_jobs (state);

CREATE INDEX ix_maintenance_jobs_task_started ON maintenance_jobs (task_id, started_at);

CREATE UNIQUE INDEX ix_moods_name ON moods (name);

CREATE INDEX ix_movie_cast_movie_id ON movie_cast (movie_id);

CREATE INDEX ix_movie_crew_movie_id ON movie_crew (movie_id);

CREATE INDEX ix_movie_documents_embedding ON movie_documents (embedding);

CREATE INDEX ix_movie_documents_movie_id ON movie_documents (movie_id);

CREATE INDEX ix_movie_identity_repairs_applied_at ON movie_identity_repairs (applied_at);

CREATE INDEX ix_movie_identity_repairs_movie_id ON movie_identity_repairs (movie_id);

CREATE INDEX ix_movie_ingest_provenance_movie_id ON movie_ingest_provenance (movie_id);

CREATE INDEX ix_movie_preferences_movie_id ON movie_preferences (movie_id);

CREATE INDEX ix_movie_preferences_profile_id ON movie_preferences (profile_id);

CREATE INDEX ix_movie_review_checks_movie_id ON movie_review_checks (movie_id);

CREATE INDEX ix_movies_id ON movies (id);

CREATE UNIQUE INDEX ix_movies_imdb_id ON movies (imdb_id)
                    ;

CREATE INDEX ix_movies_title ON movies (title);

CREATE UNIQUE INDEX ix_movies_tmdb_id ON movies (tmdb_id);

CREATE UNIQUE INDEX ix_movies_vault_id ON movies (vault_id);

CREATE INDEX ix_movies_year ON movies (year);

CREATE INDEX ix_owned_movie_copies_movie_id ON owned_movie_copies (movie_id);

CREATE INDEX ix_people_name ON people (name);

CREATE INDEX ix_retired_vault_ids_retired_at ON retired_vault_ids (retired_at);

CREATE INDEX ix_retired_vault_ids_source ON retired_vault_ids (source);

CREATE INDEX ix_roles_movie_id ON roles (movie_id);

CREATE INDEX ix_roles_person_id ON roles (person_id);

CREATE INDEX ix_roles_role_type ON roles (role_type);

CREATE INDEX ix_roles_role_type_movie_id ON roles (role_type, movie_id);

CREATE INDEX ix_source_field_decisions_decision ON source_field_decisions (decision);

CREATE INDEX ix_source_field_decisions_movie_id ON source_field_decisions (movie_id);

CREATE INDEX ix_source_field_decisions_row_field ON source_field_decisions (source_row_id, field_name);

CREATE INDEX ix_source_movie_rows_normalized_title ON source_movie_rows (normalized_title);

CREATE INDEX ix_source_movie_rows_snapshot_id ON source_movie_rows (snapshot_id);

CREATE INDEX ix_source_reconciliation_matches_movie_id ON source_reconciliation_matches (movie_id);

CREATE INDEX ix_source_reconciliation_matches_type ON source_reconciliation_matches (match_type);

CREATE INDEX ix_source_snapshots_status_uploaded ON source_snapshots (status, uploaded_at);

CREATE INDEX ix_usage_events_movie_id ON usage_events (movie_id);

CREATE INDEX ix_usage_events_name_created ON usage_events (event_name, created_at);

CREATE INDEX ix_usage_events_profile_id ON usage_events (profile_id);

CREATE UNIQUE INDEX uq_movie_ingest_provenance_movie_provider ON movie_ingest_provenance (movie_id, provider);

CREATE UNIQUE INDEX uq_people_name_tmdb_id ON people (name, tmdb_id);
