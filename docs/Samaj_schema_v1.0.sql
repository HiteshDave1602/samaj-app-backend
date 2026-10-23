CREATE SCHEMA IF NOT EXISTS samaj;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS citext;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE SEQUENCE IF NOT EXISTS samaj.audit_log_audit_id_seq AS BIGINT;
CREATE SEQUENCE IF NOT EXISTS samaj.security_event_event_id_seq AS BIGINT;
CREATE OR REPLACE FUNCTION samaj.set_updated_at() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN NEW.updated_at := now(); RETURN NEW; END $$;

-- City: A city served by the deployment. Every member, household, City Admin and city-targeted content item belongs to exactly one city.
CREATE TABLE samaj.city (
    city_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        VARCHAR(80) NOT NULL,
    state       VARCHAR(60) NOT NULL,
    is_active   BOOLEAN NOT NULL DEFAULT true,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_city_name_state UNIQUE (name, state)
);

-- Admin User: A Super Admin or City Admin who signs in to the Admin Dashboard with password + TOTP. Exactly one active City Admin per city (FR-70).
CREATE TABLE samaj.admin_user (
    admin_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    role             VARCHAR(12) NOT NULL CHECK (role IN ('SUPER_ADMIN','CITY_ADMIN')),
    city_id          UUID,
    full_name        VARCHAR(120) NOT NULL,
    email            CITEXT NOT NULL UNIQUE,
    password_hash    VARCHAR(255) NOT NULL,
    totp_secret_enc  BYTEA,
    mfa_enrolled_at  TIMESTAMPTZ,
    status           VARCHAR(20) NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE','SUSPENDED','DEACTIVATED')),
    last_login_at    TIMESTAMPTZ,
    deactivated_at   TIMESTAMPTZ,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT fk_admin_user_city_id FOREIGN KEY (city_id) REFERENCES samaj.city (city_id) ON DELETE RESTRICT,
    CONSTRAINT ck_admin_user_1 CHECK ((role = 'SUPER_ADMIN' AND city_id IS NULL) OR (role = 'CITY_ADMIN' AND city_id IS NOT NULL))
);
CREATE UNIQUE INDEX ux_admin_user_one_city_admin ON samaj.admin_user (city_id) WHERE role = 'CITY_ADMIN' AND status = 'ACTIVE';
CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON samaj.admin_user FOR EACH ROW EXECUTE FUNCTION samaj.set_updated_at();

-- Household: A family unit in the directory. Members link to it; approved non-app relatives are family_member rows under it.
CREATE TABLE samaj.household (
    household_id  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    city_id       UUID NOT NULL,
    family_name   VARCHAR(120) NOT NULL,
    native_place  VARCHAR(120),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT fk_household_city_id FOREIGN KEY (city_id) REFERENCES samaj.city (city_id) ON DELETE RESTRICT
);
CREATE INDEX ix_household_city ON samaj.household (city_id);
CREATE INDEX ix_household_family_name_trgm ON samaj.household USING gin (family_name gin_trgm_ops);
CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON samaj.household FOR EACH ROW EXECUTE FUNCTION samaj.set_updated_at();

-- Member: A registered app user, identified by a unique mobile number. Lifecycle: PENDING → ACTIVE / REJECTED → ARCHIVED → purged (anonymised).
CREATE TABLE samaj.member (
    member_id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    city_id               UUID NOT NULL,
    household_id          UUID,
    is_household_head     BOOLEAN NOT NULL DEFAULT false,
    mobile_enc            BYTEA,
    mobile_hash           BYTEA NOT NULL UNIQUE,
    mobile_last4          CHAR(4),
    full_name             VARCHAR(120),
    gender                VARCHAR(10) CHECK (gender IN ('MALE','FEMALE','OTHER')),
    dob                   DATE,
    address_enc           BYTEA,
    status                VARCHAR(20) NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING','ACTIVE','REJECTED','ARCHIVED')),
    rejection_reason      VARCHAR(500),
    reviewed_by_admin_id  UUID,
    reviewed_at           TIMESTAMPTZ,
    hide_phone            BOOLEAN NOT NULL DEFAULT false,
    hide_address          BOOLEAN NOT NULL DEFAULT false,
    notify_news           BOOLEAN NOT NULL DEFAULT true,
    source                VARCHAR(10) NOT NULL DEFAULT 'APP' CHECK (source IN ('APP','IMPORT')),
    last_login_at         TIMESTAMPTZ,
    archive_notice_at     TIMESTAMPTZ,
    archived_at           TIMESTAMPTZ,
    deleted_at            TIMESTAMPTZ,
    erased_at             TIMESTAMPTZ,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT fk_member_city_id FOREIGN KEY (city_id) REFERENCES samaj.city (city_id) ON DELETE RESTRICT,
    CONSTRAINT fk_member_household_id FOREIGN KEY (household_id) REFERENCES samaj.household (household_id) ON DELETE SET NULL,
    CONSTRAINT fk_member_reviewed_by_admin_id FOREIGN KEY (reviewed_by_admin_id) REFERENCES samaj.admin_user (admin_id) ON DELETE SET NULL,
    CONSTRAINT ck_member_1 CHECK (status <> 'REJECTED' OR rejection_reason IS NOT NULL),
    CONSTRAINT ck_member_2 CHECK (dob <= CURRENT_DATE)
);
CREATE INDEX ix_member_city_status ON samaj.member (city_id, status, created_at);
CREATE INDEX ix_member_household ON samaj.member (household_id);
CREATE UNIQUE INDEX ux_member_one_head ON samaj.member (household_id) WHERE is_household_head;
CREATE INDEX ix_member_name_trgm ON samaj.member USING gin (full_name gin_trgm_ops) WHERE status = 'ACTIVE' AND deleted_at IS NULL;
CREATE INDEX ix_member_last_login ON samaj.member (last_login_at) WHERE status IN ('ACTIVE','ARCHIVED') AND erased_at IS NULL;
CREATE INDEX ix_member_reviewed_by ON samaj.member (reviewed_by_admin_id);
CREATE INDEX ix_member_deleted ON samaj.member (deleted_at) WHERE deleted_at IS NOT NULL;
CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON samaj.member FOR EACH ROW EXECUTE FUNCTION samaj.set_updated_at();

-- Family Member: A relative added to a household through a family-addition request (FR-17). Visible in the directory only once APPROVED.
CREATE TABLE samaj.family_member (
    family_member_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    household_id            UUID NOT NULL,
    requested_by_member_id  UUID NOT NULL,
    linked_member_id        UUID,
    full_name               VARCHAR(120) NOT NULL,
    relationship            VARCHAR(30) NOT NULL,
    gender                  VARCHAR(10) CHECK (gender IN ('MALE','FEMALE','OTHER')),
    dob                     DATE,
    status                  VARCHAR(20) NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING','APPROVED','REJECTED')),
    rejection_reason        VARCHAR(500),
    reviewed_by_admin_id    UUID,
    reviewed_at             TIMESTAMPTZ,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT fk_family_member_household_id FOREIGN KEY (household_id) REFERENCES samaj.household (household_id) ON DELETE CASCADE,
    CONSTRAINT fk_family_member_requested_by_member_id FOREIGN KEY (requested_by_member_id) REFERENCES samaj.member (member_id) ON DELETE RESTRICT,
    CONSTRAINT fk_family_member_linked_member_id FOREIGN KEY (linked_member_id) REFERENCES samaj.member (member_id) ON DELETE SET NULL,
    CONSTRAINT fk_family_member_reviewed_by_admin_id FOREIGN KEY (reviewed_by_admin_id) REFERENCES samaj.admin_user (admin_id) ON DELETE SET NULL,
    CONSTRAINT ck_family_member_1 CHECK (status <> 'REJECTED' OR rejection_reason IS NOT NULL)
);
CREATE INDEX ix_family_member_household ON samaj.family_member (household_id) WHERE status = 'APPROVED';
CREATE INDEX ix_family_member_pending ON samaj.family_member (status, created_at) WHERE status = 'PENDING';
CREATE INDEX ix_family_member_requested_by ON samaj.family_member (requested_by_member_id);
CREATE INDEX ix_family_member_linked ON samaj.family_member (linked_member_id);
CREATE INDEX ix_family_member_reviewed_by ON samaj.family_member (reviewed_by_admin_id);

-- Identity Document: Optional ID uploaded at registration (FR-09). The file sits in a private, KMS-encrypted bucket; this row holds only its key and metadata.
CREATE TABLE samaj.identity_document (
    document_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    member_id             UUID NOT NULL,
    storage_key           VARCHAR(255) NOT NULL,
    mime_type             VARCHAR(40) NOT NULL CHECK (mime_type IN ('image/jpeg','image/png','application/pdf')),
    size_bytes            INTEGER NOT NULL CHECK (size_bytes BETWEEN 1 AND 2097152),
    sha256                CHAR(64) NOT NULL,
    reviewed_by_admin_id  UUID,
    reviewed_at           TIMESTAMPTZ,
    purge_after           TIMESTAMPTZ,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT fk_identity_document_member_id FOREIGN KEY (member_id) REFERENCES samaj.member (member_id) ON DELETE CASCADE,
    CONSTRAINT fk_identity_document_reviewed_by_admin_id FOREIGN KEY (reviewed_by_admin_id) REFERENCES samaj.admin_user (admin_id) ON DELETE SET NULL
);
CREATE INDEX ix_identity_document_member ON samaj.identity_document (member_id);
CREATE INDEX ix_identity_document_reviewed_by ON samaj.identity_document (reviewed_by_admin_id);
CREATE INDEX ix_identity_document_purge ON samaj.identity_document (purge_after) WHERE purge_after IS NOT NULL;

-- Consent: Purpose-specific DPDP consent captured before a profile is created (FR-07). Append-style: a new notice version creates a new row.
CREATE TABLE samaj.consent (
    consent_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    member_id       UUID NOT NULL,
    purpose         VARCHAR(30) NOT NULL CHECK (purpose IN ('MEMBERSHIP','MATRIMONY','DIRECTORY','NOTIFICATIONS')),
    notice_version  VARCHAR(20) NOT NULL,
    granted_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    withdrawn_at    TIMESTAMPTZ,
    channel         VARCHAR(10) NOT NULL DEFAULT 'APP' CHECK (channel IN ('APP','IMPORT')),
    CONSTRAINT fk_consent_member_id FOREIGN KEY (member_id) REFERENCES samaj.member (member_id) ON DELETE RESTRICT,
    CONSTRAINT uq_consent_member_id_purpose_notice_version UNIQUE (member_id, purpose, notice_version)
);
CREATE INDEX ix_consent_member ON samaj.consent (member_id);

-- OTP Challenge: A one-time password sent for login, registration or erasure confirmation. Enforces 5-minute expiry, 3 attempts and 5 sends/hour (FR-03, FR-04).
CREATE TABLE samaj.otp_challenge (
    otp_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    mobile_hash  BYTEA NOT NULL,
    purpose      VARCHAR(12) NOT NULL CHECK (purpose IN ('LOGIN','REGISTER','ERASURE')),
    code_hash    VARCHAR(255) NOT NULL,
    attempts     SMALLINT NOT NULL DEFAULT 0 CHECK (attempts BETWEEN 0 AND 3),
    expires_at   TIMESTAMPTZ NOT NULL,
    consumed_at  TIMESTAMPTZ,
    request_ip   INET,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_otp_challenge_1 CHECK (expires_at > created_at)
);
CREATE INDEX ix_otp_challenge_mobile_time ON samaj.otp_challenge (mobile_hash, created_at DESC);
CREATE INDEX ix_otp_challenge_created ON samaj.otp_challenge USING brin (created_at);

-- Auth Session: A refresh-token session for a member (30-day rotating refresh, NFR-16) or an admin (30-min idle timeout, FR-73). Exactly one principal per row.
CREATE TABLE samaj.auth_session (
    session_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    member_id           UUID,
    admin_id            UUID,
    refresh_token_hash  BYTEA NOT NULL UNIQUE,
    mfa_verified        BOOLEAN NOT NULL DEFAULT false,
    device_label        VARCHAR(80),
    last_activity_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at          TIMESTAMPTZ NOT NULL,
    revoked_at          TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT fk_auth_session_member_id FOREIGN KEY (member_id) REFERENCES samaj.member (member_id) ON DELETE CASCADE,
    CONSTRAINT fk_auth_session_admin_id FOREIGN KEY (admin_id) REFERENCES samaj.admin_user (admin_id) ON DELETE CASCADE,
    CONSTRAINT ck_auth_session_1 CHECK ((member_id IS NULL) <> (admin_id IS NULL)),
    CONSTRAINT ck_auth_session_2 CHECK (admin_id IS NULL OR mfa_verified)
);
CREATE INDEX ix_auth_session_member ON samaj.auth_session (member_id) WHERE revoked_at IS NULL;
CREATE INDEX ix_auth_session_admin ON samaj.auth_session (admin_id) WHERE revoked_at IS NULL;
CREATE INDEX ix_auth_session_expires ON samaj.auth_session (expires_at);

-- Device Token: An FCM registration token for a member's device (FR-53). Marked invalid when FCM reports UNREGISTERED (FR-55).
CREATE TABLE samaj.device_token (
    device_token_id  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    member_id        UUID NOT NULL,
    platform         VARCHAR(8) NOT NULL CHECK (platform IN ('ANDROID','IOS')),
    fcm_token        VARCHAR(512) NOT NULL UNIQUE,
    app_version      VARCHAR(20),
    is_valid         BOOLEAN NOT NULL DEFAULT true,
    last_seen_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    invalidated_at   TIMESTAMPTZ,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT fk_device_token_member_id FOREIGN KEY (member_id) REFERENCES samaj.member (member_id) ON DELETE CASCADE
);
CREATE INDEX ix_device_token_member ON samaj.device_token (member_id) WHERE is_valid;
CREATE INDEX ix_device_token_invalidated ON samaj.device_token (invalidated_at) WHERE NOT is_valid;

-- Matrimony Profile: The public summary of a member's matrimony listing (FR-08, FR-20). Contains no biodata — that lives in the separately protected biodata table.
CREATE TABLE samaj.matrimony_profile (
    profile_id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    member_id              UUID NOT NULL UNIQUE,
    location_city_id       UUID NOT NULL,
    managed_by             VARCHAR(10) NOT NULL DEFAULT 'SELF' CHECK (managed_by IN ('SELF','PARENT','SIBLING','RELATIVE')),
    education_level        VARCHAR(20) NOT NULL CHECK (education_level IN ('SCHOOL','DIPLOMA','GRADUATE','POSTGRADUATE','DOCTORATE','OTHER')),
    education_detail       VARCHAR(120),
    occupation             VARCHAR(80),
    family_background      VARCHAR(20) NOT NULL,
    about                  VARCHAR(500),
    status                 VARCHAR(20) NOT NULL DEFAULT 'DRAFT' CHECK (status IN ('DRAFT','PENDING_MODERATION','APPROVED','REJECTED','ARCHIVED')),
    moderation_reason      VARCHAR(500),
    moderated_by_admin_id  UUID,
    moderated_at           TIMESTAMPTZ,
    created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT fk_matrimony_profile_member_id FOREIGN KEY (member_id) REFERENCES samaj.member (member_id) ON DELETE RESTRICT,
    CONSTRAINT fk_matrimony_profile_location_city_id FOREIGN KEY (location_city_id) REFERENCES samaj.city (city_id) ON DELETE RESTRICT,
    CONSTRAINT fk_matrimony_profile_moderated_by_admin_id FOREIGN KEY (moderated_by_admin_id) REFERENCES samaj.admin_user (admin_id) ON DELETE SET NULL,
    CONSTRAINT ck_matrimony_profile_1 CHECK (status <> 'REJECTED' OR moderation_reason IS NOT NULL)
);
CREATE INDEX ix_matrimony_profile_moderation ON samaj.matrimony_profile (status, created_at) WHERE status = 'PENDING_MODERATION';
CREATE INDEX ix_matrimony_profile_location ON samaj.matrimony_profile (location_city_id);
CREATE INDEX ix_matrimony_profile_moderated_by ON samaj.matrimony_profile (moderated_by_admin_id);
CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON samaj.matrimony_profile FOR EACH ROW EXECUTE FUNCTION samaj.set_updated_at();

-- Biodata: The private biodata of a matrimony profile, stored as one AES-256-GCM encrypted JSON document. Readable only through samaj.get_biodata(), which enforces the accepted-pair rule.
CREATE TABLE samaj.biodata (
    profile_id      UUID PRIMARY KEY,
    payload_enc     BYTEA NOT NULL,
    key_id          VARCHAR(64) NOT NULL,
    schema_version  SMALLINT NOT NULL DEFAULT 1,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT fk_biodata_profile_id FOREIGN KEY (profile_id) REFERENCES samaj.matrimony_profile (profile_id) ON DELETE CASCADE
);
CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON samaj.biodata FOR EACH ROW EXECUTE FUNCTION samaj.set_updated_at();

-- Matrimony Photo: A photo on a matrimony profile, moderated against community guidelines before it is shown (FR-09, FR-23). Maximum 5 per profile.
CREATE TABLE samaj.matrimony_photo (
    photo_id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id             UUID NOT NULL,
    storage_key            VARCHAR(255) NOT NULL,
    mime_type              VARCHAR(20) NOT NULL CHECK (mime_type IN ('image/jpeg','image/png')),
    size_bytes             INTEGER NOT NULL CHECK (size_bytes BETWEEN 1 AND 2097152),
    sort_order             SMALLINT NOT NULL CHECK (sort_order BETWEEN 1 AND 5),
    status                 VARCHAR(20) NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING','APPROVED','REJECTED')),
    rejection_reason       VARCHAR(500),
    moderated_by_admin_id  UUID,
    moderated_at           TIMESTAMPTZ,
    created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT fk_matrimony_photo_profile_id FOREIGN KEY (profile_id) REFERENCES samaj.matrimony_profile (profile_id) ON DELETE CASCADE,
    CONSTRAINT fk_matrimony_photo_moderated_by_admin_id FOREIGN KEY (moderated_by_admin_id) REFERENCES samaj.admin_user (admin_id) ON DELETE SET NULL,
    CONSTRAINT uq_matrimony_photo_profile_id_sort_order UNIQUE (profile_id, sort_order),
    CONSTRAINT ck_matrimony_photo_1 CHECK (status <> 'REJECTED' OR rejection_reason IS NOT NULL)
);
CREATE INDEX ix_matrimony_photo_pending ON samaj.matrimony_photo (created_at) WHERE status = 'PENDING';
CREATE INDEX ix_matrimony_photo_moderated_by ON samaj.matrimony_photo (moderated_by_admin_id);
CREATE MATERIALIZED VIEW samaj.matrimony_search_mv AS
SELECT p.profile_id, p.member_id, m.gender,
       date_part('year', age(m.dob))::int AS age_years,
       p.education_level, p.location_city_id, p.family_background,
       p.education_detail, p.occupation,
       (SELECT ph.storage_key FROM samaj.matrimony_photo ph
         WHERE ph.profile_id = p.profile_id AND ph.status = 'APPROVED'
         ORDER BY ph.sort_order LIMIT 1) AS cover_photo_key
  FROM samaj.matrimony_profile p
  JOIN samaj.member m ON m.member_id = p.member_id
 WHERE p.status = 'APPROVED' AND m.status = 'ACTIVE' AND m.deleted_at IS NULL
WITH DATA;
CREATE UNIQUE INDEX ux_matrimony_search_mv_profile ON samaj.matrimony_search_mv (profile_id);
CREATE INDEX ix_matrimony_search_mv_filters ON samaj.matrimony_search_mv (gender, age_years, location_city_id, education_level, family_background);

-- Biodata Request: User A's request to exchange biodata with User B (SOP §6.2). ACCEPTED grants mutual access to that pair only. At most one PENDING or ACCEPTED request per pair, in either direction (FR-30).
CREATE TABLE samaj.biodata_request (
    request_id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    requester_profile_id     UUID NOT NULL,
    recipient_profile_id     UUID NOT NULL,
    pair_low                 UUID GENERATED ALWAYS AS (LEAST(requester_profile_id, recipient_profile_id)) STORED NOT NULL,
    pair_high                UUID GENERATED ALWAYS AS (GREATEST(requester_profile_id, recipient_profile_id)) STORED NOT NULL,
    status                   VARCHAR(20) NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING','ACCEPTED','DECLINED','WITHDRAWN')),
    responded_at             TIMESTAMPTZ,
    resend_allowed_at        TIMESTAMPTZ,
    withdrawn_at             TIMESTAMPTZ,
    withdrawn_by_profile_id  UUID,
    created_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT fk_biodata_request_requester_profile_id FOREIGN KEY (requester_profile_id) REFERENCES samaj.matrimony_profile (profile_id) ON DELETE CASCADE,
    CONSTRAINT fk_biodata_request_recipient_profile_id FOREIGN KEY (recipient_profile_id) REFERENCES samaj.matrimony_profile (profile_id) ON DELETE CASCADE,
    CONSTRAINT fk_biodata_request_withdrawn_by_profile_id FOREIGN KEY (withdrawn_by_profile_id) REFERENCES samaj.matrimony_profile (profile_id) ON DELETE SET NULL,
    CONSTRAINT ck_biodata_request_1 CHECK (requester_profile_id <> recipient_profile_id),
    CONSTRAINT ck_biodata_request_2 CHECK (status = 'PENDING' OR responded_at IS NOT NULL),
    CONSTRAINT ck_biodata_request_3 CHECK (status <> 'WITHDRAWN' OR (withdrawn_at IS NOT NULL AND withdrawn_by_profile_id IS NOT NULL))
);
CREATE UNIQUE INDEX ux_biodata_request_open_pair ON samaj.biodata_request (pair_low, pair_high) WHERE status IN ('PENDING','ACCEPTED');
CREATE INDEX ix_biodata_request_recipient ON samaj.biodata_request (recipient_profile_id, status, created_at DESC);
CREATE INDEX ix_biodata_request_requester ON samaj.biodata_request (requester_profile_id, created_at DESC);
CREATE INDEX ix_biodata_request_declined_pair ON samaj.biodata_request (pair_low, pair_high, resend_allowed_at) WHERE status = 'DECLINED';
CREATE INDEX ix_biodata_request_withdrawn_by ON samaj.biodata_request (withdrawn_by_profile_id);

-- Content Item: A news item or ad campaign scheduled in Content Management (SOP §6.3). Goes live at start_at and expires at end_at automatically (FR-47).
CREATE TABLE samaj.content_item (
    content_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content_type         VARCHAR(4) NOT NULL CHECK (content_type IN ('NEWS','AD')),
    city_id              UUID,
    title                VARCHAR(200) NOT NULL,
    body                 TEXT,
    media_key            VARCHAR(255),
    creative_format      VARCHAR(10) CHECK (creative_format IN ('BANNER','FULLSCREEN')),
    media_width          SMALLINT,
    media_height         SMALLINT,
    start_at             TIMESTAMPTZ NOT NULL,
    end_at               TIMESTAMPTZ NOT NULL,
    status               VARCHAR(20) NOT NULL DEFAULT 'DRAFT' CHECK (status IN ('DRAFT','SCHEDULED','LIVE','EXPIRED','CANCELLED')),
    created_by_admin_id  UUID NOT NULL,
    published_at         TIMESTAMPTZ,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT fk_content_item_city_id FOREIGN KEY (city_id) REFERENCES samaj.city (city_id) ON DELETE RESTRICT,
    CONSTRAINT fk_content_item_created_by_admin_id FOREIGN KEY (created_by_admin_id) REFERENCES samaj.admin_user (admin_id) ON DELETE RESTRICT,
    CONSTRAINT ck_content_item_1 CHECK (end_at > start_at),
    CONSTRAINT ck_content_item_2 CHECK (content_type = 'NEWS' OR (creative_format IS NOT NULL AND media_key IS NOT NULL)),
    CONSTRAINT ck_content_item_3 CHECK (creative_format IS DISTINCT FROM 'FULLSCREEN' OR (media_width = 1080 AND media_height = 1920)),
    CONSTRAINT ck_content_item_4 CHECK (content_type = 'AD' OR body IS NOT NULL)
);
CREATE INDEX ix_content_item_feed ON samaj.content_item (status, city_id, start_at DESC) WHERE status = 'LIVE';
CREATE INDEX ix_content_item_due ON samaj.content_item (start_at) WHERE status = 'SCHEDULED';
CREATE INDEX ix_content_item_expiring ON samaj.content_item (end_at) WHERE status = 'LIVE';
CREATE INDEX ix_content_item_city ON samaj.content_item (city_id);
CREATE INDEX ix_content_item_created_by ON samaj.content_item (created_by_admin_id);
CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON samaj.content_item FOR EACH ROW EXECUTE FUNCTION samaj.set_updated_at();

-- Layout Setting: Key/value configuration for ad dimensions and feed placement (FR-50, FR-51), e.g. ad_every_n_items = 5.
CREATE TABLE samaj.layout_setting (
    setting_key          VARCHAR(60) PRIMARY KEY,
    value                JSONB NOT NULL,
    updated_by_admin_id  UUID,
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT fk_layout_setting_updated_by_admin_id FOREIGN KEY (updated_by_admin_id) REFERENCES samaj.admin_user (admin_id) ON DELETE SET NULL
);
CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON samaj.layout_setting FOR EACH ROW EXECUTE FUNCTION samaj.set_updated_at();

-- Panchang: The effective Tithi, Nakshatra and Yoga for one date and reference location (SOP §6.4). A manual entry overrides API values (FR-62).
CREATE TABLE samaj.panchang_day (
    panchang_id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    panchang_date              DATE NOT NULL,
    location_code              VARCHAR(20) NOT NULL DEFAULT 'DEFAULT',
    tithi                      VARCHAR(40) NOT NULL,
    nakshatra                  VARCHAR(40) NOT NULL,
    yoga                       VARCHAR(40) NOT NULL,
    source                     VARCHAR(6) NOT NULL CHECK (source IN ('API','MANUAL')),
    verified_against_calendar  BOOLEAN NOT NULL DEFAULT false,
    edited_by_admin_id         UUID,
    fetched_at                 TIMESTAMPTZ,
    published_at               TIMESTAMPTZ,
    updated_at                 TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT fk_panchang_day_edited_by_admin_id FOREIGN KEY (edited_by_admin_id) REFERENCES samaj.admin_user (admin_id) ON DELETE SET NULL,
    CONSTRAINT uq_panchang_day_location_code_panchang_date UNIQUE (location_code, panchang_date),
    CONSTRAINT ck_panchang_day_1 CHECK (source = 'API' OR (edited_by_admin_id IS NOT NULL AND verified_against_calendar))
);
CREATE INDEX ix_panchang_day_edited_by ON samaj.panchang_day (edited_by_admin_id);
CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON samaj.panchang_day FOR EACH ROW EXECUTE FUNCTION samaj.set_updated_at();

-- Panchang Revision: Append-only history of every API fetch and manual edit of a Panchang day: the edit history shown in the dashboard (FR-62).
CREATE TABLE samaj.panchang_revision (
    revision_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    panchang_id         UUID NOT NULL,
    tithi               VARCHAR(40) NOT NULL,
    nakshatra           VARCHAR(40) NOT NULL,
    yoga                VARCHAR(40) NOT NULL,
    source              VARCHAR(6) NOT NULL CHECK (source IN ('API','MANUAL')),
    edited_by_admin_id  UUID,
    api_status          VARCHAR(20),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT fk_panchang_revision_panchang_id FOREIGN KEY (panchang_id) REFERENCES samaj.panchang_day (panchang_id) ON DELETE RESTRICT,
    CONSTRAINT fk_panchang_revision_edited_by_admin_id FOREIGN KEY (edited_by_admin_id) REFERENCES samaj.admin_user (admin_id) ON DELETE SET NULL
);
CREATE INDEX ix_panchang_revision_day ON samaj.panchang_revision (panchang_id, created_at DESC);
CREATE INDEX ix_panchang_revision_edited_by ON samaj.panchang_revision (edited_by_admin_id);

-- Notification: Transactional outbox for push / SMS / email. Written in the same transaction as the business change, then delivered by the worker (≤ 30 s target, NFR-05).
CREATE TABLE samaj.notification_outbox (
    notification_id  UUID NOT NULL DEFAULT gen_random_uuid(),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    kind             VARCHAR(30) NOT NULL CHECK (kind IN ('ACCOUNT_DECISION','NEWS_LIVE','BIODATA_REQUEST','BIODATA_RESPONSE','FAMILY_DECISION','PROFILE_DECISION','PANCHANG_ALERT','ARCHIVE_NOTICE','ESCALATION','IMPORT_REPORT')),
    channel          VARCHAR(6) NOT NULL CHECK (channel IN ('PUSH','SMS','EMAIL')),
    audience         VARCHAR(10) NOT NULL CHECK (audience IN ('MEMBER','CITY','ALL','ADMIN')),
    member_id        UUID,
    city_id          UUID,
    admin_id         UUID,
    content_id       UUID,
    payload          JSONB NOT NULL DEFAULT '{}'::jsonb,
    state            VARCHAR(10) NOT NULL DEFAULT 'QUEUED' CHECK (state IN ('QUEUED','SENDING','SENT','PARTIAL','FAILED')),
    attempts         SMALLINT NOT NULL DEFAULT 0,
    sent_at          TIMESTAMPTZ,
    success_count    INTEGER,
    failure_count    INTEGER,
    CONSTRAINT pk_notification_outbox PRIMARY KEY (notification_id, created_at),
    CONSTRAINT fk_notification_outbox_member_id FOREIGN KEY (member_id) REFERENCES samaj.member (member_id) ON DELETE CASCADE,
    CONSTRAINT fk_notification_outbox_city_id FOREIGN KEY (city_id) REFERENCES samaj.city (city_id) ON DELETE RESTRICT,
    CONSTRAINT fk_notification_outbox_admin_id FOREIGN KEY (admin_id) REFERENCES samaj.admin_user (admin_id) ON DELETE RESTRICT,
    CONSTRAINT fk_notification_outbox_content_id FOREIGN KEY (content_id) REFERENCES samaj.content_item (content_id) ON DELETE SET NULL,
    CONSTRAINT ck_notification_outbox_1 CHECK (member_id IS NOT NULL OR audience <> 'MEMBER')
)
PARTITION BY RANGE (created_at);
CREATE INDEX ix_notification_outbox_queue ON samaj.notification_outbox (state, created_at) WHERE state IN ('QUEUED','SENDING');
CREATE INDEX ix_notification_outbox_member ON samaj.notification_outbox (member_id);
CREATE INDEX ix_notification_outbox_content ON samaj.notification_outbox (content_id);
CREATE INDEX ix_notification_outbox_city ON samaj.notification_outbox (city_id);
CREATE INDEX ix_notification_outbox_admin ON samaj.notification_outbox (admin_id);

-- Import Job: A CSV/XLSX member-list upload (SOP §6.5). Validated → dry-run report → committed. A header mismatch rejects the file before any write (FR-76).
CREATE TABLE samaj.import_job (
    import_job_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    city_id               UUID NOT NULL,
    uploaded_by_admin_id  UUID NOT NULL,
    file_key              VARCHAR(255) NOT NULL,
    file_format           VARCHAR(4) NOT NULL CHECK (file_format IN ('CSV','XLSX')),
    template_version      VARCHAR(20) NOT NULL,
    status                VARCHAR(20) NOT NULL DEFAULT 'VALIDATING' CHECK (status IN ('VALIDATING','REJECTED','DRY_RUN_READY','COMMITTING','COMMITTED','FAILED')),
    total_rows            INTEGER CHECK (total_rows <= 50000),
    new_count             INTEGER NOT NULL DEFAULT 0,
    updated_count         INTEGER NOT NULL DEFAULT 0,
    conflict_count        INTEGER NOT NULL DEFAULT 0,
    error_count           INTEGER NOT NULL DEFAULT 0,
    report_key            VARCHAR(255),
    committed_at          TIMESTAMPTZ,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT fk_import_job_city_id FOREIGN KEY (city_id) REFERENCES samaj.city (city_id) ON DELETE RESTRICT,
    CONSTRAINT fk_import_job_uploaded_by_admin_id FOREIGN KEY (uploaded_by_admin_id) REFERENCES samaj.admin_user (admin_id) ON DELETE RESTRICT
);
CREATE INDEX ix_import_job_city_time ON samaj.import_job (city_id, created_at DESC);
CREATE INDEX ix_import_job_uploaded_by ON samaj.import_job (uploaded_by_admin_id);

-- Import Row: One validated row of an import, with its dedup outcome (NEW / UPDATE / CONFLICT / ERROR). Staged data is encrypted and wiped 30 days after commit.
CREATE TABLE samaj.import_row (
    import_job_id      UUID NOT NULL,
    row_number         INTEGER NOT NULL,
    outcome            VARCHAR(8) NOT NULL CHECK (outcome IN ('NEW','UPDATE','CONFLICT','ERROR')),
    mobile_hash        BYTEA,
    matched_member_id  UUID,
    payload_enc        BYTEA,
    error_message      VARCHAR(500),
    resolution         VARCHAR(10) CHECK (resolution IN ('APPLIED','SKIPPED')),
    CONSTRAINT pk_import_row PRIMARY KEY (import_job_id, row_number),
    CONSTRAINT fk_import_row_import_job_id FOREIGN KEY (import_job_id) REFERENCES samaj.import_job (import_job_id) ON DELETE CASCADE,
    CONSTRAINT fk_import_row_matched_member_id FOREIGN KEY (matched_member_id) REFERENCES samaj.member (member_id) ON DELETE SET NULL
);
CREATE INDEX ix_import_row_conflicts ON samaj.import_row (import_job_id) WHERE outcome = 'CONFLICT' AND resolution IS NULL;
CREATE INDEX ix_import_row_member ON samaj.import_row (matched_member_id);

-- Export Job: Record of an 'Export Filtered' (FR-82). The password and the file are never stored; only who exported what, and how many rows.
CREATE TABLE samaj.export_job (
    export_job_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    city_id               UUID,
    exported_by_admin_id  UUID NOT NULL,
    filters               JSONB NOT NULL,
    columns_exported      TEXT[] NOT NULL,
    row_count             INTEGER NOT NULL CHECK (row_count >= 0),
    file_format           VARCHAR(4) NOT NULL CHECK (file_format IN ('CSV','XLSX')),
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT fk_export_job_city_id FOREIGN KEY (city_id) REFERENCES samaj.city (city_id) ON DELETE RESTRICT,
    CONSTRAINT fk_export_job_exported_by_admin_id FOREIGN KEY (exported_by_admin_id) REFERENCES samaj.admin_user (admin_id) ON DELETE RESTRICT
);
CREATE INDEX ix_export_job_admin_time ON samaj.export_job (exported_by_admin_id, created_at DESC);
CREATE INDEX ix_export_job_city ON samaj.export_job (city_id);

-- Audit Log: Append-only record of every admin action and data-principal event (FR-86, FR-87). No FKs, so log rows outlive the objects they describe.
CREATE TABLE samaj.audit_log (
    audit_id      BIGINT NOT NULL DEFAULT nextval('samaj.audit_log_audit_id_seq'),
    occurred_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    actor_type    VARCHAR(8) NOT NULL CHECK (actor_type IN ('ADMIN','MEMBER','SYSTEM')),
    actor_id      UUID,
    action        VARCHAR(40) NOT NULL,
    target_table  VARCHAR(40),
    target_id     VARCHAR(64),
    city_id       UUID,
    before_state  JSONB,
    after_state   JSONB,
    source_ip     INET,
    request_id    UUID,
    CONSTRAINT pk_audit_log PRIMARY KEY (audit_id, occurred_at)
)
PARTITION BY RANGE (occurred_at);
CREATE INDEX ix_audit_log_occurred ON samaj.audit_log USING brin (occurred_at);
CREATE INDEX ix_audit_log_actor ON samaj.audit_log (actor_id, occurred_at DESC);
CREATE INDEX ix_audit_log_city_action ON samaj.audit_log (city_id, action, occurred_at DESC);
CREATE INDEX ix_audit_log_target ON samaj.audit_log (target_table, target_id);

-- Security Event: Denied or suspicious access, above all every denied biodata read (FR-37), plus OTP lockouts, MFA failures (ERR_AUTH_01) and cross-city 403s.
CREATE TABLE samaj.security_event (
    event_id     BIGINT NOT NULL DEFAULT nextval('samaj.security_event_event_id_seq'),
    occurred_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    event_type   VARCHAR(30) NOT NULL CHECK (event_type IN ('BIODATA_DENIED','CROSS_CITY_DENIED','ID_DOC_DENIED','OTP_LOCKED','OTP_RATE_LIMIT','MFA_FAILED','TOKEN_REUSE')),
    actor_type   VARCHAR(8) NOT NULL CHECK (actor_type IN ('ADMIN','MEMBER','ANONYMOUS')),
    actor_id     UUID,
    endpoint     VARCHAR(120) NOT NULL,
    target_id    VARCHAR(64),
    reason       VARCHAR(200),
    source_ip    INET,
    CONSTRAINT pk_security_event PRIMARY KEY (event_id, occurred_at)
)
PARTITION BY RANGE (occurred_at);
CREATE INDEX ix_security_event_occurred ON samaj.security_event USING brin (occurred_at);
CREATE INDEX ix_security_event_type ON samaj.security_event (event_type, occurred_at DESC);
CREATE INDEX ix_security_event_actor ON samaj.security_event (actor_id, occurred_at DESC);

-- Feedback / Report: In-app feedback, a profile report (FR-91) or a DPDP grievance (FR-100), reviewed daily in the dashboard.
CREATE TABLE samaj.feedback_report (
    feedback_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    member_id            UUID,
    category             VARCHAR(16) NOT NULL CHECK (category IN ('FEEDBACK','PROFILE_REPORT','GRIEVANCE')),
    target_profile_id    UUID,
    message              VARCHAR(2000) NOT NULL,
    status               VARCHAR(20) NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN','IN_REVIEW','RESOLVED','DISMISSED')),
    handled_by_admin_id  UUID,
    resolved_at          TIMESTAMPTZ,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT fk_feedback_report_member_id FOREIGN KEY (member_id) REFERENCES samaj.member (member_id) ON DELETE SET NULL,
    CONSTRAINT fk_feedback_report_target_profile_id FOREIGN KEY (target_profile_id) REFERENCES samaj.matrimony_profile (profile_id) ON DELETE SET NULL,
    CONSTRAINT fk_feedback_report_handled_by_admin_id FOREIGN KEY (handled_by_admin_id) REFERENCES samaj.admin_user (admin_id) ON DELETE SET NULL,
    CONSTRAINT ck_feedback_report_1 CHECK (category <> 'PROFILE_REPORT' OR target_profile_id IS NOT NULL)
);
CREATE INDEX ix_feedback_report_open ON samaj.feedback_report (category, created_at) WHERE status IN ('OPEN','IN_REVIEW');
CREATE INDEX ix_feedback_report_member ON samaj.feedback_report (member_id);
CREATE INDEX ix_feedback_report_target ON samaj.feedback_report (target_profile_id);
CREATE INDEX ix_feedback_report_handler ON samaj.feedback_report (handled_by_admin_id);

-- Data Rights Request: A DPDP data-principal request: access copy, erasure (OTP-confirmed) or consent withdrawal, which triggers erasure. Completed within 30 days (FR-98, FR-99).
CREATE TABLE samaj.data_rights_request (
    rights_request_id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    member_id            UUID NOT NULL,
    request_type         VARCHAR(20) NOT NULL CHECK (request_type IN ('ACCESS','ERASURE','CONSENT_WITHDRAWAL','RETENTION_PURGE')),
    status               VARCHAR(20) NOT NULL DEFAULT 'RECEIVED' CHECK (status IN ('RECEIVED','OTP_CONFIRMED','IN_PROGRESS','COMPLETED','REJECTED')),
    otp_confirmed_at     TIMESTAMPTZ,
    requested_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    due_at               TIMESTAMPTZ NOT NULL DEFAULT now() + INTERVAL '30 days',
    completed_at         TIMESTAMPTZ,
    handled_by_admin_id  UUID,
    CONSTRAINT fk_data_rights_request_member_id FOREIGN KEY (member_id) REFERENCES samaj.member (member_id) ON DELETE RESTRICT,
    CONSTRAINT fk_data_rights_request_handled_by_admin_id FOREIGN KEY (handled_by_admin_id) REFERENCES samaj.admin_user (admin_id) ON DELETE SET NULL,
    CONSTRAINT ck_data_rights_request_1 CHECK (status <> 'COMPLETED' OR completed_at IS NOT NULL)
);
CREATE INDEX ix_data_rights_request_due ON samaj.data_rights_request (due_at) WHERE status NOT IN ('COMPLETED','REJECTED');
CREATE INDEX ix_data_rights_request_member ON samaj.data_rights_request (member_id);
CREATE INDEX ix_data_rights_request_handler ON samaj.data_rights_request (handled_by_admin_id);
