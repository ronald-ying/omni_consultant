PRAGMA foreign_keys = ON;


CREATE TABLE IF NOT EXISTS repository_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);


INSERT OR IGNORE INTO repository_meta (
    key,
    value
)
VALUES (
    'schema_version',
    '1'
);


CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    client TEXT,
    location TEXT,
    created_at TEXT NOT NULL
);


CREATE INDEX IF NOT EXISTS idx_projects_name
ON projects(name);


CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    sha256 TEXT NOT NULL UNIQUE,
    file_name TEXT NOT NULL,
    extension TEXT,
    size_bytes INTEGER NOT NULL,
    extractable INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);


CREATE INDEX IF NOT EXISTS idx_documents_sha256
ON documents(sha256);


CREATE TABLE IF NOT EXISTS document_locations (
    document_id TEXT NOT NULL,
    file_path TEXT NOT NULL,
    modified_at TEXT,
    last_seen_at TEXT NOT NULL,

    PRIMARY KEY (
        document_id,
        file_path
    ),

    FOREIGN KEY (
        document_id
    )
    REFERENCES documents(id)
    ON DELETE CASCADE
);


CREATE TABLE IF NOT EXISTS project_documents (
    project_id TEXT NOT NULL,
    document_id TEXT NOT NULL,

    document_type TEXT NOT NULL DEFAULT 'unknown',
    discipline TEXT NOT NULL DEFAULT 'unknown',
    source_kind TEXT NOT NULL DEFAULT 'prior_work',
    notes TEXT,

    PRIMARY KEY (
        project_id,
        document_id
    ),

    FOREIGN KEY (
        project_id
    )
    REFERENCES projects(id)
    ON DELETE CASCADE,

    FOREIGN KEY (
        document_id
    )
    REFERENCES documents(id)
    ON DELETE CASCADE
);


CREATE TABLE IF NOT EXISTS knowledge_items (
    id TEXT PRIMARY KEY,
    project_id TEXT,

    item_type TEXT NOT NULL,
    discipline TEXT,
    title TEXT,
    content TEXT NOT NULL,

    support_level TEXT,
    status TEXT NOT NULL DEFAULT 'extracted',

    created_at TEXT NOT NULL,

    FOREIGN KEY (
        project_id
    )
    REFERENCES projects(id)
    ON DELETE CASCADE
);


CREATE TABLE IF NOT EXISTS knowledge_item_sources (
    knowledge_item_id TEXT NOT NULL,
    document_id TEXT NOT NULL,

    locator TEXT NOT NULL DEFAULT '',
    evidence_text TEXT,

    PRIMARY KEY (
        knowledge_item_id,
        document_id,
        locator
    ),

    FOREIGN KEY (
        knowledge_item_id
    )
    REFERENCES knowledge_items(id)
    ON DELETE CASCADE,

    FOREIGN KEY (
        document_id
    )
    REFERENCES documents(id)
    ON DELETE CASCADE
);