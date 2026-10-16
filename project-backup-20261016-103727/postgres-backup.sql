--
-- PostgreSQL database dump
--

\restrict msWB7TwxfsIGKkfIP49PnGkeMvecXtdz8goSGIkfNYMQXicYK0kQUdqutfkNDup

-- Dumped from database version 16.15
-- Dumped by pg_dump version 16.15

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: alerts; Type: TABLE; Schema: public; Owner: cctv_user
--

CREATE TABLE public.alerts (
    id character varying(36) NOT NULL,
    camera_id integer NOT NULL,
    organization_id character varying(36),
    site_id character varying(36),
    module character varying(50) NOT NULL,
    class_name character varying(50) NOT NULL,
    state character varying(30) NOT NULL,
    consecutive_frames integer NOT NULL,
    duration_seconds double precision NOT NULL,
    max_confidence double precision NOT NULL,
    latest_confidence double precision NOT NULL,
    start_time timestamp with time zone NOT NULL,
    cleared_time timestamp with time zone,
    remedial_action character varying(100),
    remedy_notes character varying(500),
    resolved_by character varying(100),
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL
);


ALTER TABLE public.alerts OWNER TO cctv_user;

--
-- Name: audit_logs; Type: TABLE; Schema: public; Owner: cctv_user
--

CREATE TABLE public.audit_logs (
    id character varying(36) NOT NULL,
    event_type character varying(50) NOT NULL,
    actor_id character varying(36),
    username character varying(100),
    ip_address character varying(45),
    user_agent character varying(255),
    status character varying(20) NOT NULL,
    details text,
    created_at timestamp with time zone NOT NULL
);


ALTER TABLE public.audit_logs OWNER TO cctv_user;

--
-- Name: cameras; Type: TABLE; Schema: public; Owner: cctv_user
--

CREATE TABLE public.cameras (
    id integer NOT NULL,
    name character varying(150) NOT NULL,
    camera_number character varying(50) NOT NULL,
    organization_id character varying(36),
    site_id character varying(36),
    dvr_id integer,
    dvr_channel integer,
    channel_name character varying(100),
    dvr_address character varying(100),
    rtsp_url character varying(500) NOT NULL,
    source_type character varying(20) NOT NULL,
    location character varying(200),
    latitude double precision,
    longitude double precision,
    enabled boolean NOT NULL,
    fire_smoke_enabled boolean NOT NULL,
    ppe_enabled boolean NOT NULL,
    person_enabled boolean NOT NULL,
    zone_enabled boolean NOT NULL,
    ppe_inference_interval_sec double precision NOT NULL,
    priority character varying(20) NOT NULL,
    capture_fps integer NOT NULL,
    target_ai_fps integer NOT NULL,
    frame_skip integer NOT NULL,
    gpu_device_id integer NOT NULL,
    fps_limit integer NOT NULL,
    connection_timeout integer NOT NULL,
    reconnect_interval integer NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL
);


ALTER TABLE public.cameras OWNER TO cctv_user;

--
-- Name: cameras_id_seq; Type: SEQUENCE; Schema: public; Owner: cctv_user
--

CREATE SEQUENCE public.cameras_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.cameras_id_seq OWNER TO cctv_user;

--
-- Name: cameras_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: cctv_user
--

ALTER SEQUENCE public.cameras_id_seq OWNED BY public.cameras.id;


--
-- Name: detections; Type: TABLE; Schema: public; Owner: cctv_user
--

CREATE TABLE public.detections (
    id character varying(36) NOT NULL,
    camera_id integer NOT NULL,
    module character varying(50) NOT NULL,
    class_name character varying(50) NOT NULL,
    confidence double precision NOT NULL,
    bounding_box json NOT NULL,
    frame_number integer NOT NULL,
    fps double precision NOT NULL,
    "timestamp" timestamp with time zone NOT NULL
);


ALTER TABLE public.detections OWNER TO cctv_user;

--
-- Name: dvrs; Type: TABLE; Schema: public; Owner: cctv_user
--

CREATE TABLE public.dvrs (
    id integer NOT NULL,
    name character varying(150) NOT NULL,
    management_host character varying(100) NOT NULL,
    management_port integer NOT NULL,
    rtsp_port integer NOT NULL,
    username character varying(100) NOT NULL,
    credential_reference text NOT NULL,
    manufacturer character varying(50) NOT NULL,
    channels_count integer NOT NULL,
    enabled boolean NOT NULL,
    status character varying(30) NOT NULL,
    last_health_check_at timestamp with time zone,
    last_successful_health_check_at timestamp with time zone,
    health_check_error text,
    version_id integer NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL
);


ALTER TABLE public.dvrs OWNER TO cctv_user;

--
-- Name: dvrs_id_seq; Type: SEQUENCE; Schema: public; Owner: cctv_user
--

CREATE SEQUENCE public.dvrs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.dvrs_id_seq OWNER TO cctv_user;

--
-- Name: dvrs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: cctv_user
--

ALTER SEQUENCE public.dvrs_id_seq OWNED BY public.dvrs.id;


--
-- Name: evidence; Type: TABLE; Schema: public; Owner: cctv_user
--

CREATE TABLE public.evidence (
    id character varying(36) NOT NULL,
    evidence_id character varying(64) NOT NULL,
    alert_id character varying(36) NOT NULL,
    camera_id integer NOT NULL,
    organization_id character varying(36),
    site_id character varying(36),
    snapshot_relative_path character varying(500) NOT NULL,
    video_relative_path character varying(500),
    metadata_relative_path character varying(500),
    file_size_bytes integer NOT NULL,
    metadata_envelope json,
    retention_until timestamp with time zone,
    created_at timestamp with time zone NOT NULL
);


ALTER TABLE public.evidence OWNER TO cctv_user;

--
-- Name: incidents; Type: TABLE; Schema: public; Owner: cctv_user
--

CREATE TABLE public.incidents (
    id character varying(36) NOT NULL,
    camera_id integer NOT NULL,
    zone_id integer,
    organization_id character varying(36),
    site_id character varying(36),
    incident_type character varying(50) NOT NULL,
    events json NOT NULL,
    severity character varying(20) NOT NULL,
    status character varying(30) NOT NULL,
    person_id integer,
    evidence_id character varying(64),
    start_time timestamp with time zone NOT NULL,
    cleared_time timestamp with time zone,
    metadata_json json NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL
);


ALTER TABLE public.incidents OWNER TO cctv_user;

--
-- Name: licenses; Type: TABLE; Schema: public; Owner: cctv_user
--

CREATE TABLE public.licenses (
    id character varying(36) NOT NULL,
    organization_id character varying(36) NOT NULL,
    license_key character varying(64) NOT NULL,
    tier character varying(30) NOT NULL,
    max_cameras integer NOT NULL,
    enabled_modules json NOT NULL,
    status character varying(20) NOT NULL,
    expires_at timestamp with time zone,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL
);


ALTER TABLE public.licenses OWNER TO cctv_user;

--
-- Name: notifications; Type: TABLE; Schema: public; Owner: cctv_user
--

CREATE TABLE public.notifications (
    id character varying(36) NOT NULL,
    alert_id character varying(36) NOT NULL,
    channel character varying(30) NOT NULL,
    recipient character varying(255) NOT NULL,
    status character varying(30) NOT NULL,
    error_message text,
    sent_at timestamp with time zone NOT NULL
);


ALTER TABLE public.notifications OWNER TO cctv_user;

--
-- Name: organization_users; Type: TABLE; Schema: public; Owner: cctv_user
--

CREATE TABLE public.organization_users (
    id character varying(36) NOT NULL,
    organization_id character varying(36) NOT NULL,
    user_id character varying(36) NOT NULL,
    role character varying(50) NOT NULL,
    created_at timestamp with time zone NOT NULL
);


ALTER TABLE public.organization_users OWNER TO cctv_user;

--
-- Name: organizations; Type: TABLE; Schema: public; Owner: cctv_user
--

CREATE TABLE public.organizations (
    id character varying(36) NOT NULL,
    name character varying(150) NOT NULL,
    slug character varying(100) NOT NULL,
    is_active boolean NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL
);


ALTER TABLE public.organizations OWNER TO cctv_user;

--
-- Name: person_detections; Type: TABLE; Schema: public; Owner: cctv_user
--

CREATE TABLE public.person_detections (
    id character varying(36) NOT NULL,
    camera_id integer NOT NULL,
    person_id integer NOT NULL,
    bounding_box json NOT NULL,
    confidence double precision NOT NULL,
    "timestamp" timestamp with time zone NOT NULL
);


ALTER TABLE public.person_detections OWNER TO cctv_user;

--
-- Name: ppe_profiles; Type: TABLE; Schema: public; Owner: cctv_user
--

CREATE TABLE public.ppe_profiles (
    id integer NOT NULL,
    name character varying(100) NOT NULL,
    description character varying(255),
    required_equipment json NOT NULL,
    optional_equipment json NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL
);


ALTER TABLE public.ppe_profiles OWNER TO cctv_user;

--
-- Name: ppe_profiles_id_seq; Type: SEQUENCE; Schema: public; Owner: cctv_user
--

CREATE SEQUENCE public.ppe_profiles_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.ppe_profiles_id_seq OWNER TO cctv_user;

--
-- Name: ppe_profiles_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: cctv_user
--

ALTER SEQUENCE public.ppe_profiles_id_seq OWNED BY public.ppe_profiles.id;


--
-- Name: ppe_requirements; Type: TABLE; Schema: public; Owner: cctv_user
--

CREATE TABLE public.ppe_requirements (
    id integer NOT NULL,
    profile_id integer NOT NULL,
    equipment_type character varying(50) NOT NULL,
    is_required boolean NOT NULL,
    severity character varying(20) NOT NULL,
    created_at timestamp with time zone NOT NULL
);


ALTER TABLE public.ppe_requirements OWNER TO cctv_user;

--
-- Name: ppe_requirements_id_seq; Type: SEQUENCE; Schema: public; Owner: cctv_user
--

CREATE SEQUENCE public.ppe_requirements_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.ppe_requirements_id_seq OWNER TO cctv_user;

--
-- Name: ppe_requirements_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: cctv_user
--

ALTER SEQUENCE public.ppe_requirements_id_seq OWNED BY public.ppe_requirements.id;


--
-- Name: ppe_violations; Type: TABLE; Schema: public; Owner: cctv_user
--

CREATE TABLE public.ppe_violations (
    id character varying(36) NOT NULL,
    camera_id integer NOT NULL,
    zone_id integer,
    person_id integer NOT NULL,
    profile_id integer,
    status character varying(20) NOT NULL,
    severity character varying(20) NOT NULL,
    missing_items json NOT NULL,
    detected_items json NOT NULL,
    required_items json NOT NULL,
    confidence double precision NOT NULL,
    "timestamp" timestamp with time zone NOT NULL,
    evidence_id character varying(64),
    created_at timestamp with time zone NOT NULL
);


ALTER TABLE public.ppe_violations OWNER TO cctv_user;

--
-- Name: refresh_tokens; Type: TABLE; Schema: public; Owner: cctv_user
--

CREATE TABLE public.refresh_tokens (
    id character varying(36) NOT NULL,
    family_id character varying(36) NOT NULL,
    user_id character varying(36) NOT NULL,
    token_hash character varying(128) NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    is_revoked boolean NOT NULL,
    replaced_by_id character varying(36),
    created_at timestamp with time zone NOT NULL
);


ALTER TABLE public.refresh_tokens OWNER TO cctv_user;

--
-- Name: safety_zones; Type: TABLE; Schema: public; Owner: cctv_user
--

CREATE TABLE public.safety_zones (
    id integer NOT NULL,
    camera_id integer NOT NULL,
    organization_id character varying(36),
    site_id character varying(36),
    name character varying(100) NOT NULL,
    zone_type character varying(30) NOT NULL,
    polygon_coordinates json NOT NULL,
    ppe_profile_id integer,
    enabled boolean NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL
);


ALTER TABLE public.safety_zones OWNER TO cctv_user;

--
-- Name: safety_zones_id_seq; Type: SEQUENCE; Schema: public; Owner: cctv_user
--

CREATE SEQUENCE public.safety_zones_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.safety_zones_id_seq OWNER TO cctv_user;

--
-- Name: safety_zones_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: cctv_user
--

ALTER SEQUENCE public.safety_zones_id_seq OWNED BY public.safety_zones.id;


--
-- Name: sites; Type: TABLE; Schema: public; Owner: cctv_user
--

CREATE TABLE public.sites (
    id character varying(36) NOT NULL,
    organization_id character varying(36) NOT NULL,
    name character varying(150) NOT NULL,
    address character varying(255),
    is_active boolean NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL
);


ALTER TABLE public.sites OWNER TO cctv_user;

--
-- Name: system_logs; Type: TABLE; Schema: public; Owner: cctv_user
--

CREATE TABLE public.system_logs (
    id character varying(36) NOT NULL,
    level character varying(20) NOT NULL,
    module character varying(100) NOT NULL,
    message text NOT NULL,
    correlation_id character varying(64),
    camera_id integer,
    created_at timestamp with time zone NOT NULL
);


ALTER TABLE public.system_logs OWNER TO cctv_user;

--
-- Name: users; Type: TABLE; Schema: public; Owner: cctv_user
--

CREATE TABLE public.users (
    id character varying(36) NOT NULL,
    username character varying(100) NOT NULL,
    email character varying(255) NOT NULL,
    hashed_password character varying(255) NOT NULL,
    full_name character varying(150),
    role character varying(50) NOT NULL,
    is_active boolean NOT NULL,
    is_superuser boolean NOT NULL,
    organization_id character varying(36),
    failed_login_attempts integer NOT NULL,
    locked_until timestamp with time zone,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL
);


ALTER TABLE public.users OWNER TO cctv_user;

--
-- Name: cameras id; Type: DEFAULT; Schema: public; Owner: cctv_user
--

ALTER TABLE ONLY public.cameras ALTER COLUMN id SET DEFAULT nextval('public.cameras_id_seq'::regclass);


--
-- Name: dvrs id; Type: DEFAULT; Schema: public; Owner: cctv_user
--

ALTER TABLE ONLY public.dvrs ALTER COLUMN id SET DEFAULT nextval('public.dvrs_id_seq'::regclass);


--
-- Name: ppe_profiles id; Type: DEFAULT; Schema: public; Owner: cctv_user
--

ALTER TABLE ONLY public.ppe_profiles ALTER COLUMN id SET DEFAULT nextval('public.ppe_profiles_id_seq'::regclass);


--
-- Name: ppe_requirements id; Type: DEFAULT; Schema: public; Owner: cctv_user
--

ALTER TABLE ONLY public.ppe_requirements ALTER COLUMN id SET DEFAULT nextval('public.ppe_requirements_id_seq'::regclass);


--
-- Name: safety_zones id; Type: DEFAULT; Schema: public; Owner: cctv_user
--

ALTER TABLE ONLY public.safety_zones ALTER COLUMN id SET DEFAULT nextval('public.safety_zones_id_seq'::regclass);


--
-- Data for Name: alerts; Type: TABLE DATA; Schema: public; Owner: cctv_user
--

COPY public.alerts (id, camera_id, organization_id, site_id, module, class_name, state, consecutive_frames, duration_seconds, max_confidence, latest_confidence, start_time, cleared_time, remedial_action, remedy_notes, resolved_by, created_at, updated_at) FROM stdin;
04bb3d81-4abf-4066-8146-e434286ca957	1	\N	\N	FIRE_SMOKE	zone_violation	ALERT_SENT	1	0	0.99	0.99	2026-10-13 09:44:03.06606+00	\N	\N	\N	\N	2026-10-13 09:44:06.207741+00	2026-10-13 09:44:06.207746+00
a30c037b-62f7-49f6-8f07-323f3724f658	1	\N	\N	FIRE_SMOKE	zone_violation	ALERT_SENT	1	0	0.9095	0.9095	2026-10-13 09:46:29.135591+00	\N	\N	\N	\N	2026-10-13 09:46:31.851457+00	2026-10-13 09:46:31.851461+00
ppe_evt_de7c046000	1	\N	\N	FIRE_SMOKE	ppe_violation	ALERT_SENT	6	14.31	0.96	0.96	2026-10-14 04:20:16.858604+00	\N	\N	\N	\N	2026-10-14 04:20:19.484082+00	2026-10-14 04:20:19.484086+00
ppe_evt_da92ec3b31	1	\N	\N	FIRE_SMOKE	ppe_violation	ALERT_SENT	6	17.72	0.8464	0.8464	2026-10-14 04:29:30.625264+00	\N	\N	\N	\N	2026-10-14 04:29:33.968652+00	2026-10-14 04:29:33.968656+00
ppe_evt_f25dad12a0	1	\N	\N	FIRE_SMOKE	ppe_violation	ALERT_SENT	6	14.94	0.96	0.96	2026-10-14 04:32:43.841291+00	\N	\N	\N	\N	2026-10-14 04:32:47.728668+00	2026-10-14 04:32:47.728672+00
ppe_evt_acf4543c37	1	\N	\N	FIRE_SMOKE	ppe_violation	ALERT_SENT	6	16.4	0.96	0.96	2026-10-14 04:37:01.067755+00	\N	\N	\N	\N	2026-10-14 04:37:04.979166+00	2026-10-14 04:37:04.979172+00
ppe_evt_4c243f0790	1	\N	\N	FIRE_SMOKE	ppe_violation	ALERT_SENT	6	16.58	0.96	0.96	2026-10-14 04:43:18.788338+00	\N	\N	\N	\N	2026-10-14 04:43:22.412911+00	2026-10-14 04:43:22.412915+00
ppe_evt_d0a84191ee	1	\N	\N	FIRE_SMOKE	ppe_violation	ALERT_SENT	6	24.97	0.96	0.96	2026-10-14 04:44:29.173714+00	\N	\N	\N	\N	2026-10-14 04:44:34.433901+00	2026-10-14 04:44:34.433906+00
test_ev_d71d49	1	\N	\N	SAFETY_ANALYSIS	no_helmet	ALERT_SENT	5	5	0.95	0.95	2026-10-15 11:40:22.954156+00	\N	\N	\N	\N	2026-10-15 11:40:22.954156+00	2026-10-15 11:40:22.954156+00
\.


--
-- Data for Name: audit_logs; Type: TABLE DATA; Schema: public; Owner: cctv_user
--

COPY public.audit_logs (id, event_type, actor_id, username, ip_address, user_agent, status, details, created_at) FROM stdin;
dcb4423b-88f6-4669-b409-98ee25edbed0	LOGIN_SUCCESS	7cfa0577-7f0e-4a34-91db-730773f49c61	admin	172.19.0.4	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36	SUCCESS	\N	2026-10-12 11:07:14.457983+00
5956c2f4-4fd2-49bb-8dfc-54802e88bd72	TOKEN_REFRESH	7cfa0577-7f0e-4a34-91db-730773f49c61	admin	172.19.0.4	\N	SUCCESS	\N	2026-10-12 11:38:13.172168+00
d63530af-85f4-4703-bf73-6193183204d4	TOKEN_REFRESH	7cfa0577-7f0e-4a34-91db-730773f49c61	admin	172.19.0.4	\N	SUCCESS	\N	2026-10-12 12:09:13.159264+00
981f2f18-cacb-4f50-8987-4c23debad866	TOKEN_REFRESH	7cfa0577-7f0e-4a34-91db-730773f49c61	admin	172.19.0.4	\N	SUCCESS	\N	2026-10-12 12:09:13.163818+00
b7c05d8b-a0db-455f-b27e-f34eb388df45	LOGIN_SUCCESS	7cfa0577-7f0e-4a34-91db-730773f49c61	admin	172.19.0.3	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36	SUCCESS	\N	2026-10-13 07:12:46.248097+00
37b602ef-24d5-4cc7-997b-dca725b582ae	LOGIN_SUCCESS	7cfa0577-7f0e-4a34-91db-730773f49c61	admin	172.19.0.3	Mozilla/5.0 (Windows NT; Windows NT 10.0; en-IN) WindowsPowerShell/5.1.26100.9549	SUCCESS	\N	2026-10-13 07:16:09.444354+00
cb072532-e343-4535-8c0c-8817edb6cdff	LOGIN_SUCCESS	7cfa0577-7f0e-4a34-91db-730773f49c61	admin	172.19.0.3	Mozilla/5.0 (Windows NT; Windows NT 10.0; en-IN) WindowsPowerShell/5.1.26100.9549	SUCCESS	\N	2026-10-13 07:19:42.017548+00
d0f0ea11-9211-4519-9aa8-ad35aabd4665	TOKEN_REFRESH	7cfa0577-7f0e-4a34-91db-730773f49c61	admin	172.19.0.3	\N	SUCCESS	\N	2026-10-13 07:44:11.707198+00
dff2bde0-2c5f-402e-947c-d1a858989710	TOKEN_REFRESH	7cfa0577-7f0e-4a34-91db-730773f49c61	admin	172.19.0.3	\N	SUCCESS	\N	2026-10-13 08:14:12.285621+00
7d90f903-a081-4662-9bd4-c83570fb06b0	TOKEN_REFRESH	7cfa0577-7f0e-4a34-91db-730773f49c61	admin	172.19.0.3	\N	SUCCESS	\N	2026-10-13 08:45:12.453931+00
fc4b2009-0995-4bc3-9685-8a20058d073f	TOKEN_REFRESH	7cfa0577-7f0e-4a34-91db-730773f49c61	admin	172.19.0.3	\N	SUCCESS	\N	2026-10-13 09:18:12.460992+00
167ba87c-14f2-486f-aead-d6b847923184	LOGIN_SUCCESS	7cfa0577-7f0e-4a34-91db-730773f49c61	admin	172.19.0.3	Mozilla/5.0 (Windows NT; Windows NT 10.0; en-IN) WindowsPowerShell/5.1.26100.9549	SUCCESS	\N	2026-10-14 04:26:03.270921+00
eaa1fb50-7936-4ef7-8321-797f03d0fba3	TOKEN_REFRESH	7cfa0577-7f0e-4a34-91db-730773f49c61	admin	172.19.0.3	\N	SUCCESS	\N	2026-10-14 04:51:24.777238+00
7eca96e9-5700-4d42-b976-e1f63181b59a	TOKEN_REFRESH	7cfa0577-7f0e-4a34-91db-730773f49c61	admin	172.19.0.3	\N	SUCCESS	\N	2026-10-14 05:23:10.33799+00
5da7d514-f72d-482c-8979-ad7ef6587c04	TOKEN_REFRESH	7cfa0577-7f0e-4a34-91db-730773f49c61	admin	172.19.0.3	\N	SUCCESS	\N	2026-10-14 05:55:10.356865+00
908a7306-044d-4bf0-9c70-beef1aaca599	TOKEN_REFRESH	7cfa0577-7f0e-4a34-91db-730773f49c61	admin	172.19.0.3	\N	SUCCESS	\N	2026-10-14 06:27:10.338196+00
113abef0-7c1f-4ac8-940d-60ba2e268ca1	TOKEN_REFRESH	7cfa0577-7f0e-4a34-91db-730773f49c61	admin	172.19.0.3	\N	SUCCESS	\N	2026-10-14 06:59:10.347592+00
caf1ea27-6ff4-4371-8880-9ba74df24249	TOKEN_REFRESH	7cfa0577-7f0e-4a34-91db-730773f49c61	admin	172.19.0.3	\N	SUCCESS	\N	2026-10-14 07:31:10.343163+00
c733743c-0a1f-4e26-9857-2840935795be	TOKEN_REFRESH	7cfa0577-7f0e-4a34-91db-730773f49c61	admin	172.19.0.3	\N	SUCCESS	\N	2026-10-14 08:18:10.331561+00
2ff33e29-297c-4fef-96e8-d074724836b7	TOKEN_REFRESH	7cfa0577-7f0e-4a34-91db-730773f49c61	admin	172.19.0.3	\N	SUCCESS	\N	2026-10-14 12:29:55.775019+00
f2d61f0b-6b2b-449f-b54a-7454684ee2e4	LOGIN_FAILED	7cfa0577-7f0e-4a34-91db-730773f49c61	admin	127.0.0.1	python-requests/2.34.2	FAILED	{"failed_attempts": 1}	2026-10-15 11:43:43.639695+00
\.


--
-- Data for Name: cameras; Type: TABLE DATA; Schema: public; Owner: cctv_user
--

COPY public.cameras (id, name, camera_number, organization_id, site_id, dvr_id, dvr_channel, channel_name, dvr_address, rtsp_url, source_type, location, latitude, longitude, enabled, fire_smoke_enabled, ppe_enabled, person_enabled, zone_enabled, ppe_inference_interval_sec, priority, capture_fps, target_ai_fps, frame_skip, gpu_device_id, fps_limit, connection_timeout, reconnect_interval, created_at, updated_at) FROM stdin;
1	hall	CAM-01	\N	\N	\N	\N	\N	\N	rtsp://admin:sky%402026@192.168.1.9:554/Streaming/Channels/301	rtsp	hall	13.0827	80.2707	f	t	t	t	t	0.05	HIGH	25	15	1	0	25	10	5	2026-10-12 11:08:06.751018+00	2026-10-14 04:51:32.236181+00
\.


--
-- Data for Name: detections; Type: TABLE DATA; Schema: public; Owner: cctv_user
--

COPY public.detections (id, camera_id, module, class_name, confidence, bounding_box, frame_number, fps, "timestamp") FROM stdin;
86f943d1-0110-4338-81f3-3d73ef958a53	1	FIRE_SMOKE	person	0.6470757722854614	{"x_min": 0.4972, "y_min": 0.1702, "x_max": 0.5829, "y_max": 0.3735}	84	12.25	2026-10-12 11:08:25.55953+00
0c247bae-137a-41a4-b432-dcedbec50c72	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.5074, "y_min": 0.1815, "x_max": 0.5719, "y_max": 0.2151}	84	12.25	2026-10-12 11:08:25.55953+00
157c2911-ec87-4261-899d-1b83523e186c	1	FIRE_SMOKE	vest	0.6569452881813049	{"x_min": 0.5038, "y_min": 0.2691, "x_max": 0.586, "y_max": 0.3558}	84	12.25	2026-10-12 11:08:25.55953+00
5209d6b7-fe21-400f-a2b8-3f15b190a0c8	1	FIRE_SMOKE	person	0.48631516098976135	{"x_min": 0.5009, "y_min": 0.1745, "x_max": 0.5587, "y_max": 0.2486}	296	12.46	2026-10-13 07:20:47.952215+00
3a2440e8-2332-431a-81cb-8551ed10e7fb	1	FIRE_SMOKE	vest	0.7132750153541565	{"x_min": 0.4992, "y_min": 0.1851, "x_max": 0.5284, "y_max": 0.208}	296	12.46	2026-10-13 07:20:47.952215+00
129187ef-979f-45ad-9547-a545aab5dce7	1	FIRE_SMOKE	gloves	0.6737514138221741	{"x_min": 0.5225, "y_min": 0.2082, "x_max": 0.5349, "y_max": 0.2158}	296	12.46	2026-10-13 07:20:47.952215+00
9d03b201-9f1c-4fab-a4df-2cba8d26863d	1	FIRE_SMOKE	person	0.5165358185768127	{"x_min": 0.5024, "y_min": 0.2574, "x_max": 0.6038, "y_max": 0.3765}	1592	12.52	2026-10-13 07:22:35.975917+00
5d1546a1-120d-4265-9302-7cfc5ea2891a	1	FIRE_SMOKE	vest	0.8129066228866577	{"x_min": 0.0, "y_min": 0.4829, "x_max": 0.9591, "y_max": 0.9993}	1592	12.52	2026-10-13 07:22:35.975917+00
b0283cb2-c3e3-4b67-9973-2b7ff22b9527	1	FIRE_SMOKE	goggles	0.30609002709388733	{"x_min": 0.5002, "y_min": 0.3176, "x_max": 0.5765, "y_max": 0.3185}	1592	12.52	2026-10-13 07:22:35.975917+00
0266a935-8a26-46e8-982c-343b1d3865f6	1	FIRE_SMOKE	goggles	0.22552135586738586	{"x_min": 0.5626, "y_min": 0.2506, "x_max": 0.5958, "y_max": 0.2741}	1592	12.52	2026-10-13 07:22:35.975917+00
3b6a95e2-eda6-425c-abd4-cd4a87262cd4	1	FIRE_SMOKE	goggles	0.21997937560081482	{"x_min": 0.5385, "y_min": 0.3179, "x_max": 0.6103, "y_max": 0.3185}	1592	12.52	2026-10-13 07:22:35.975917+00
aba5fa15-3324-4cb1-9c99-e3e36d3eeac8	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.5121, "y_min": 0.2686, "x_max": 0.5934, "y_max": 0.2987}	1628	12.48	2026-10-13 07:22:38.977592+00
2b233f8c-6edb-4e37-8e56-b4b11fc7d744	1	FIRE_SMOKE	vest	0.620789110660553	{"x_min": 0.5106, "y_min": 0.3051, "x_max": 0.576, "y_max": 0.3616}	1628	12.48	2026-10-13 07:22:38.977592+00
e0a226a8-4e85-4271-9a45-2363f52c17cd	1	FIRE_SMOKE	person	0.6497211456298828	{"x_min": 0.5037, "y_min": 0.2865, "x_max": 0.5843, "y_max": 0.3678}	2020	11.99	2026-10-13 07:23:11.572809+00
8d3089bc-1194-4e92-8acc-deaa1072a868	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.5114, "y_min": 0.2939, "x_max": 0.5759, "y_max": 0.3143}	2020	11.99	2026-10-13 07:23:11.572809+00
0d2db3c2-789f-49b5-ac3b-99cf7851565d	1	FIRE_SMOKE	vest	0.807258129119873	{"x_min": 0.5054, "y_min": 0.3677, "x_max": 0.5808, "y_max": 0.4323}	2020	11.99	2026-10-13 07:23:11.572809+00
adc853f5-4695-4c8a-9c35-a3115174cc0b	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.5114, "y_min": 0.2939, "x_max": 0.5759, "y_max": 0.3143}	2064	12.98	2026-10-13 07:23:15.271846+00
aa1d31e1-d1c1-4ae7-b292-f0476fdcd244	1	FIRE_SMOKE	vest	0.807258129119873	{"x_min": 0.5054, "y_min": 0.3677, "x_max": 0.5808, "y_max": 0.4323}	2064	12.98	2026-10-13 07:23:15.271846+00
d4b1bf3f-036d-4433-a1be-a679f90bf439	1	FIRE_SMOKE	person	0.5312106013298035	{"x_min": 0.5037, "y_min": 0.2876, "x_max": 0.5837, "y_max": 0.3687}	2120	11.84	2026-10-13 07:23:19.872187+00
0c98ea97-88a1-40f9-92a3-1db67c215947	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.5108, "y_min": 0.2951, "x_max": 0.5759, "y_max": 0.3149}	2120	11.84	2026-10-13 07:23:19.872187+00
48637f42-bce1-4b5b-b2e4-41f75a1cabc2	1	FIRE_SMOKE	vest	0.7461943626403809	{"x_min": 0.5061, "y_min": 0.3721, "x_max": 0.581, "y_max": 0.4328}	2120	11.84	2026-10-13 07:23:19.872187+00
d8e0bcf0-08fd-4018-857c-dd2b7fc74ca4	1	FIRE_SMOKE	gloves	0.2883285582065582	{"x_min": 0.5014, "y_min": 0.3, "x_max": 0.5717, "y_max": 0.3898}	2120	11.84	2026-10-13 07:23:19.872187+00
aee84968-af3e-420b-8121-cc207cfad1ce	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.5108, "y_min": 0.2951, "x_max": 0.5759, "y_max": 0.3149}	2152	12	2026-10-13 07:23:22.572428+00
045fe79e-ac73-495a-9def-762456e87c43	1	FIRE_SMOKE	vest	0.7461943626403809	{"x_min": 0.5061, "y_min": 0.3721, "x_max": 0.581, "y_max": 0.4328}	2152	12	2026-10-13 07:23:22.572428+00
707ff3ac-17d4-4442-86e0-bcef65a3e1b9	1	FIRE_SMOKE	person	0.46327412128448486	{"x_min": 0.4935, "y_min": 0.2492, "x_max": 0.5805, "y_max": 0.3821}	2484	11.98	2026-10-13 07:23:50.410142+00
d4d5606d-e391-4c38-b7ae-9d85ebe283e0	1	FIRE_SMOKE	vest	0.6738008856773376	{"x_min": 0.5014, "y_min": 0.2686, "x_max": 0.5621, "y_max": 0.3066}	2524	11.81	2026-10-13 07:23:53.677018+00
2a80d67c-f299-424c-9794-69834b5abd6f	1	FIRE_SMOKE	gloves	0.20535773038864136	{"x_min": 0.5052, "y_min": 0.2907, "x_max": 0.5761, "y_max": 0.3692}	2524	11.81	2026-10-13 07:23:53.677018+00
1a6cf340-9305-4806-8d9c-76c30eb7e84a	1	FIRE_SMOKE	person	0.8053620457649231	{"x_min": 0.5766, "y_min": 0.2464, "x_max": 0.5932, "y_max": 0.2873}	3220	12.29	2026-10-13 07:24:51.57404+00
1234b90e-08e7-4564-89d5-8a5ee68e8563	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.578, "y_min": 0.2482, "x_max": 0.5907, "y_max": 0.2548}	3220	12.29	2026-10-13 07:24:51.57404+00
126b8de7-ad04-423d-8c58-7b9e063bca5b	1	FIRE_SMOKE	vest	0.7823877334594727	{"x_min": 0.5771, "y_min": 0.2669, "x_max": 0.5933, "y_max": 0.2825}	3220	12.29	2026-10-13 07:24:51.57404+00
5a415f08-cf18-4afd-9662-880237ec397a	1	FIRE_SMOKE	person	0.5061867833137512	{"x_min": 0.5, "y_min": 0.2468, "x_max": 0.5853, "y_max": 0.3816}	3360	12.09	2026-10-13 07:25:03.473445+00
69ca44c6-7e4f-4be9-8a59-cfac2bd96164	1	FIRE_SMOKE	vest	0.6802065372467041	{"x_min": 0.0, "y_min": 0.4882, "x_max": 0.9346, "y_max": 0.9993}	3360	12.09	2026-10-13 07:25:03.473445+00
e50a508e-44a4-43c1-bd4a-1e948cbef1f4	1	FIRE_SMOKE	goggles	0.24576953053474426	{"x_min": 0.5298, "y_min": 0.2389, "x_max": 0.5636, "y_max": 0.2507}	3360	12.09	2026-10-13 07:25:03.473445+00
c386ba00-e087-4a3c-8d0b-5adb76921621	1	FIRE_SMOKE	goggles	0.13857659697532654	{"x_min": 0.5004, "y_min": 0.2908, "x_max": 0.5262, "y_max": 0.3149}	3360	12.09	2026-10-13 07:25:03.473445+00
d3a49e59-7f94-4088-a6c8-0562ac52fa36	1	FIRE_SMOKE	goggles	0.12475171685218811	{"x_min": 0.4961, "y_min": 0.284, "x_max": 0.5239, "y_max": 0.3092}	3360	12.09	2026-10-13 07:25:03.473445+00
d7ace7c0-f5f2-4e3a-9082-3373bcd246ab	1	FIRE_SMOKE	vest	0.6603104472160339	{"x_min": 0.5041, "y_min": 0.2662, "x_max": 0.5594, "y_max": 0.3052}	3416	12.65	2026-10-13 07:25:08.075953+00
9a1a1730-66fb-47b7-8374-8acfedea9850	1	FIRE_SMOKE	goggles	0.12475171685218811	{"x_min": 0.4961, "y_min": 0.284, "x_max": 0.5239, "y_max": 0.3092}	3416	12.65	2026-10-13 07:25:08.075953+00
caa17b35-0589-4bac-a9b9-9d84d40abacf	1	FIRE_SMOKE	person	0.4791928827762604	{"x_min": 0.5733, "y_min": 0.28, "x_max": 0.5838, "y_max": 0.2878}	1732	12	2026-10-13 07:29:16.735761+00
bdaf7bd8-b173-4605-ac80-c6d23f593f39	1	FIRE_SMOKE	person	0.4781363010406494	{"x_min": 0.5695, "y_min": 0.346, "x_max": 0.5874, "y_max": 0.3659}	2572	12.94	2026-10-13 07:30:26.793037+00
d08c1e37-bcd6-4dce-9967-5a51e9e8374f	1	FIRE_SMOKE	person	0.6017610430717468	{"x_min": 0.4928, "y_min": 0.2493, "x_max": 0.5923, "y_max": 0.3853}	8504	11.98	2026-10-13 07:38:41.136927+00
fdb5068a-8030-4f56-ad6a-2ec6040cb567	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.5027, "y_min": 0.262, "x_max": 0.582, "y_max": 0.2963}	8504	11.98	2026-10-13 07:38:41.136927+00
e38f5078-00eb-430a-9ec8-5fd5bde006d9	1	FIRE_SMOKE	vest	0.9369524121284485	{"x_min": 0.4907, "y_min": 0.3314, "x_max": 0.5544, "y_max": 0.3737}	8504	11.98	2026-10-13 07:38:41.136927+00
fb693874-71e9-4ae0-8a7d-154d337e4067	1	FIRE_SMOKE	vest	0.8770113587379456	{"x_min": 0.5042, "y_min": 0.2701, "x_max": 0.5616, "y_max": 0.3413}	8504	11.98	2026-10-13 07:38:41.136927+00
e01c1474-c721-4d06-840d-f6822cf53887	1	FIRE_SMOKE	person	0.50928795337677	{"x_min": 0.4908, "y_min": 0.235, "x_max": 0.5806, "y_max": 0.3276}	10628	11.99	2026-10-13 07:41:38.14006+00
9687080c-3ea7-459a-87d7-b7a4b954afcf	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4993, "y_min": 0.244, "x_max": 0.5712, "y_max": 0.2668}	10628	11.99	2026-10-13 07:41:38.14006+00
1d9257f0-9366-4802-a5c8-b9252a49539f	1	FIRE_SMOKE	vest	0.7896239757537842	{"x_min": 0.4885, "y_min": 0.3363, "x_max": 0.5659, "y_max": 0.3996}	10628	11.99	2026-10-13 07:41:38.14006+00
bd51f0de-3df6-4bba-9d68-6430955e899b	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.5027, "y_min": 0.262, "x_max": 0.582, "y_max": 0.2963}	8536	11.95	2026-10-13 07:38:43.777769+00
f32c60b6-d828-40fb-8efd-2d19efcf65c7	1	FIRE_SMOKE	vest	0.6820392608642578	{"x_min": 0.0, "y_min": 0.4902, "x_max": 0.9174, "y_max": 0.9992}	8536	11.95	2026-10-13 07:38:43.777769+00
6592187c-5280-423b-bfeb-dd8cea882402	1	FIRE_SMOKE	vest	0.7896239757537842	{"x_min": 0.4885, "y_min": 0.3363, "x_max": 0.5659, "y_max": 0.3996}	10668	11.99	2026-10-13 07:41:41.536305+00
b492f23a-13f8-4b68-a354-113303bf5571	1	FIRE_SMOKE	person	0.7945079803466797	{"x_min": 0.486, "y_min": 0.2273, "x_max": 0.5895, "y_max": 0.3887}	668	11.83	2026-10-13 08:22:36.398933+00
0fb0c26f-ba9c-4228-99dd-e016cfbe0c9d	1	FIRE_SMOKE	vest	0.9900000095367432	{"x_min": 0.4935, "y_min": 0.3011, "x_max": 0.5752, "y_max": 0.3596}	668	11.83	2026-10-13 08:22:36.398933+00
629d2fe5-1a65-4695-b723-6de9cfed7e83	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.496, "y_min": 0.2428, "x_max": 0.5793, "y_max": 0.2831}	668	11.83	2026-10-13 08:22:36.398933+00
c5765081-7a14-4385-8c30-f5f7dc91d80f	1	FIRE_SMOKE	person	0.529005229473114	{"x_min": 0.4883, "y_min": 0.2269, "x_max": 0.5949, "y_max": 0.3884}	700	11.98	2026-10-13 08:22:38.997645+00
d61e4e5f-2b23-4450-80e4-aa3e5e211f89	1	FIRE_SMOKE	vest	0.9900000095367432	{"x_min": 0.4961, "y_min": 0.3007, "x_max": 0.5801, "y_max": 0.3592}	700	11.98	2026-10-13 08:22:38.997645+00
f9b51a5f-9ead-489e-97e9-2bf6c2817104	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.498, "y_min": 0.2422, "x_max": 0.5847, "y_max": 0.2825}	700	11.98	2026-10-13 08:22:38.997645+00
b6130d82-3778-438e-90ac-ab669dc2b79d	1	FIRE_SMOKE	vest	0.9900000095367432	{"x_min": 0.4953, "y_min": 0.3008, "x_max": 0.5786, "y_max": 0.3593}	740	12.41	2026-10-13 08:22:42.400315+00
de1ac56f-48ea-440f-9a55-3b594bf5ad98	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4973, "y_min": 0.2422, "x_max": 0.5827, "y_max": 0.2825}	740	12.41	2026-10-13 08:22:42.400315+00
a9f4cb5f-01de-442d-9a5e-1098804598c8	1	FIRE_SMOKE	person	0.5276191234588623	{"x_min": 0.4886, "y_min": 0.2273, "x_max": 0.5861, "y_max": 0.3512}	764	10.79	2026-10-13 08:22:44.499599+00
a010a0a4-f78f-4df0-8d3d-1dadeb00571e	1	FIRE_SMOKE	vest	0.9900000095367432	{"x_min": 0.5004, "y_min": 0.2896, "x_max": 0.5823, "y_max": 0.3405}	764	10.79	2026-10-13 08:22:44.499599+00
5a49c446-77d2-4218-bbd5-9684ffade35d	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.498, "y_min": 0.2392, "x_max": 0.5766, "y_max": 0.2698}	764	10.79	2026-10-13 08:22:44.499599+00
e7477b70-548f-4e21-9ba9-b7bbc3246281	1	FIRE_SMOKE	vest	0.9900000095367432	{"x_min": 0.5004, "y_min": 0.2896, "x_max": 0.5823, "y_max": 0.3405}	804	12.06	2026-10-13 08:22:47.800646+00
8f1f72b7-e3b4-46c8-a16d-3c8fcf6517d8	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.498, "y_min": 0.2392, "x_max": 0.5766, "y_max": 0.2698}	804	12.06	2026-10-13 08:22:47.800646+00
14673d91-d155-4e15-b19e-a972a088fc26	1	FIRE_SMOKE	person	0.5087860226631165	{"x_min": 0.4867, "y_min": 0.2273, "x_max": 0.6053, "y_max": 0.3884}	860	12.26	2026-10-13 08:22:52.501322+00
f77917da-e1fe-4791-b866-97f6eafc52a9	1	FIRE_SMOKE	vest	0.9900000095367432	{"x_min": 0.4929, "y_min": 0.3145, "x_max": 0.5945, "y_max": 0.3742}	860	12.26	2026-10-13 08:22:52.501322+00
3ea158af-8508-4b12-812b-5952596c88a5	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.498, "y_min": 0.2428, "x_max": 0.5934, "y_max": 0.2831}	860	12.26	2026-10-13 08:22:52.501322+00
2a493a3e-cd68-4fe4-a1c3-4088763acc66	1	FIRE_SMOKE	vest	0.8319503664970398	{"x_min": 0.4952, "y_min": 0.2673, "x_max": 0.5631, "y_max": 0.342}	860	12.26	2026-10-13 08:22:52.501322+00
4360346c-97d8-4036-80e0-a12c2720c759	1	FIRE_SMOKE	person	0.712651252746582	{"x_min": 0.498, "y_min": 0.3002, "x_max": 0.5833, "y_max": 0.3824}	892	11.85	2026-10-13 08:22:55.099967+00
a5e7dfcc-5e2c-46a1-bc2f-5c7f8ffd353c	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.5047, "y_min": 0.3113, "x_max": 0.5759, "y_max": 0.3395}	892	11.85	2026-10-13 08:22:55.099967+00
5c4574e0-add5-4a30-82d5-ccadfcafb5e1	1	FIRE_SMOKE	vest	0.8319503664970398	{"x_min": 0.5041, "y_min": 0.3206, "x_max": 0.5529, "y_max": 0.3587}	892	11.85	2026-10-13 08:22:55.099967+00
ead78f59-3c7d-4019-9b32-67ba18d6606c	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.504, "y_min": 0.2885, "x_max": 0.58, "y_max": 0.3149}	932	12.28	2026-10-13 08:22:58.511211+00
b610adc8-7348-44b2-95f1-3030d3d38dd7	1	FIRE_SMOKE	vest	0.8319503664970398	{"x_min": 0.5014, "y_min": 0.3046, "x_max": 0.556, "y_max": 0.3537}	932	12.28	2026-10-13 08:22:58.511211+00
131578ad-8a12-4c30-885b-d08a7b84a3ae	1	FIRE_SMOKE	person	0.5321346521377563	{"x_min": 0.4979, "y_min": 0.261, "x_max": 0.5954, "y_max": 0.3478}	2184	13.12	2026-10-13 08:24:42.80179+00
3a932324-26b6-4622-9ac5-88758bc2187a	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.5054, "y_min": 0.2728, "x_max": 0.5867, "y_max": 0.3023}	2184	13.12	2026-10-13 08:24:42.80179+00
00c359ff-c85a-4c8a-bfae-e5e3c3523912	1	FIRE_SMOKE	vest	0.8120116591453552	{"x_min": 0.4954, "y_min": 0.3513, "x_max": 0.5844, "y_max": 0.4161}	2184	13.12	2026-10-13 08:24:42.80179+00
f6bb64d2-fb05-48f0-87cc-ff5e2ac3fd5a	1	FIRE_SMOKE	gloves	0.23236355185508728	{"x_min": 0.4973, "y_min": 0.2828, "x_max": 0.5801, "y_max": 0.4026}	2184	13.12	2026-10-13 08:24:42.80179+00
0b2d5a66-574b-4d1f-99af-2f72c7587c71	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.5054, "y_min": 0.2728, "x_max": 0.5867, "y_max": 0.3023}	2224	12	2026-10-13 08:24:46.109366+00
47cb883e-42c8-4e8f-80a3-b38b81b90aac	1	FIRE_SMOKE	vest	0.8120116591453552	{"x_min": 0.4954, "y_min": 0.3513, "x_max": 0.5844, "y_max": 0.4161}	2224	12	2026-10-13 08:24:46.109366+00
9719eb3b-2212-448f-ba16-2ba9314285aa	1	FIRE_SMOKE	person	0.585318922996521	{"x_min": 0.4966, "y_min": 0.2983, "x_max": 0.6025, "y_max": 0.3904}	3116	12	2026-10-13 08:26:00.522651+00
a74072b7-e41d-48ed-ad07-11c287ac7f97	1	FIRE_SMOKE	vest	0.6403520107269287	{"x_min": 0.4966, "y_min": 0.3912, "x_max": 0.5901, "y_max": 0.4627}	3116	12	2026-10-13 08:26:00.522651+00
776676be-2ebb-46d3-b9f1-9869e0f11624	1	FIRE_SMOKE	vest	0.7318041920661926	{"x_min": 0.0, "y_min": 0.4823, "x_max": 0.9616, "y_max": 0.9994}	3152	11.89	2026-10-13 08:26:03.524252+00
2f43ecb3-cff0-49c0-a4c4-1bdd9bc7d925	1	FIRE_SMOKE	goggles	0.2412705272436142	{"x_min": 0.533, "y_min": 0.36, "x_max": 0.6062, "y_max": 0.3606}	3152	11.89	2026-10-13 08:26:03.524252+00
20e818bc-74e9-4a1f-af0f-da6f597a96fb	1	FIRE_SMOKE	goggles	0.1591016948223114	{"x_min": 0.5147, "y_min": 0.3282, "x_max": 0.5575, "y_max": 0.3445}	3152	11.89	2026-10-13 08:26:03.524252+00
f7a45511-97e7-4a19-9fb9-e25f36d3475d	1	FIRE_SMOKE	person	0.47505298256874084	{"x_min": 0.6057, "y_min": 0.3777, "x_max": 0.6197, "y_max": 0.3831}	3596	11.99	2026-10-13 08:26:40.521141+00
9241b891-6c6c-4a81-b9c6-e3aa049d873f	1	FIRE_SMOKE	person	0.8637750744819641	{"x_min": 0.575, "y_min": 0.2427, "x_max": 0.5923, "y_max": 0.2944}	3672	12.98	2026-10-13 08:26:46.821737+00
21562bf5-9add-4caa-b6b4-02b25d9a98bf	1	FIRE_SMOKE	person	0.54591304063797	{"x_min": 0.5766, "y_min": 0.2424, "x_max": 0.5926, "y_max": 0.2921}	3840	12.64	2026-10-13 08:27:00.771858+00
4845a0ef-8dc6-47ed-8d38-8608f52510c7	1	FIRE_SMOKE	person	0.8424046635627747	{"x_min": 0.4683, "y_min": 0.2437, "x_max": 0.5622, "y_max": 0.3784}	4848	11.84	2026-10-13 08:28:24.784713+00
71e1939d-0635-4b98-8f28-9a5e242c1675	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4772, "y_min": 0.256, "x_max": 0.5524, "y_max": 0.2903}	4900	11.97	2026-10-13 08:28:29.044206+00
aee51c7a-86ee-4dcb-aaa9-3679a991db77	1	FIRE_SMOKE	vest	0.6696792244911194	{"x_min": 0.0, "y_min": 0.4878, "x_max": 0.9963, "y_max": 0.9994}	4900	11.97	2026-10-13 08:28:29.044206+00
1dd38bb3-5660-43a9-b4ee-fa6300f3da4f	1	FIRE_SMOKE	person	0.4817050099372864	{"x_min": 0.4955, "y_min": 0.378, "x_max": 0.5148, "y_max": 0.4033}	6276	11.99	2026-10-13 08:30:23.80347+00
6e1ccdcb-6dcd-41f5-babf-fe873649e30d	1	FIRE_SMOKE	vest	0.744670569896698	{"x_min": 0.4946, "y_min": 0.3879, "x_max": 0.5137, "y_max": 0.4006}	6276	11.99	2026-10-13 08:30:23.80347+00
e959a7e8-8790-4da2-8ba3-b1c9e88ee631	1	FIRE_SMOKE	person	0.7722755074501038	{"x_min": 0.5267, "y_min": 0.1885, "x_max": 0.5586, "y_max": 0.2095}	15412	13.58	2026-10-13 08:43:05.184098+00
7e6e5f5b-f14c-4981-9b47-987999b3f3b0	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.5282, "y_min": 0.1905, "x_max": 0.5565, "y_max": 0.1977}	15412	13.58	2026-10-13 08:43:05.184098+00
848a592c-8b00-402d-85ef-5b08527a64ab	1	FIRE_SMOKE	vest	0.9597287178039551	{"x_min": 0.5255, "y_min": 0.2195, "x_max": 0.5582, "y_max": 0.2259}	15412	13.58	2026-10-13 08:43:05.184098+00
5c595187-ab2f-48b3-a38b-d5590220f39f	1	FIRE_SMOKE	gloves	0.2293240875005722	{"x_min": 0.5255, "y_min": 0.1911, "x_max": 0.5416, "y_max": 0.2131}	15412	13.58	2026-10-13 08:43:05.184098+00
f0b80de5-7c34-4b96-a091-d15db7bfc32f	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4772, "y_min": 0.1695, "x_max": 0.5067, "y_max": 0.1941}	16136	12.58	2026-10-13 08:44:05.488+00
0a3aff98-965c-42d0-82e3-27f0c3959dce	1	FIRE_SMOKE	person	0.6659433245658875	{"x_min": 0.5565, "y_min": 0.2296, "x_max": 0.6016, "y_max": 0.2748}	17672	12.97	2026-10-13 08:46:13.510264+00
4dfebb51-a023-44d7-9f37-d0d0e3a03880	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.5605, "y_min": 0.2338, "x_max": 0.5974, "y_max": 0.2446}	17672	12.97	2026-10-13 08:46:13.510264+00
48c7b9f3-f90c-4a28-ba4b-6b5e994da310	1	FIRE_SMOKE	person	0.9900000095367432	{"x_min": 0.3219, "y_min": 0.1374, "x_max": 0.4878, "y_max": 0.7293}	7292	11.96	2026-10-13 08:31:48.54701+00
1cdf8e3a-8360-4b6e-803b-eec289e4e374	1	FIRE_SMOKE	goggles	0.1286948025226593	{"x_min": 0.4617, "y_min": 0.1016, "x_max": 0.5034, "y_max": 0.143}	7292	11.96	2026-10-13 08:31:48.54701+00
11668b34-fad0-41da-badd-396cf09c8b16	1	FIRE_SMOKE	person	0.5208989381790161	{"x_min": 0.5313, "y_min": 0.1936, "x_max": 0.559, "y_max": 0.2095}	15300	12.98	2026-10-13 08:42:55.847387+00
f73b0087-bdee-4c0b-8757-89dffe2aee14	1	FIRE_SMOKE	person	0.5998311638832092	{"x_min": 0.5239, "y_min": 0.1797, "x_max": 0.5565, "y_max": 0.2095}	15740	12.18	2026-10-13 08:43:32.591573+00
5527053d-85e9-498e-a7e0-7ecf5b5b8055	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.5255, "y_min": 0.1833, "x_max": 0.5544, "y_max": 0.1935}	15740	12.18	2026-10-13 08:43:32.591573+00
ec1151e0-bdb1-4e9e-9b72-4773340aae27	1	FIRE_SMOKE	vest	0.8750935792922974	{"x_min": 0.5261, "y_min": 0.2092, "x_max": 0.5568, "y_max": 0.2325}	15740	12.18	2026-10-13 08:43:32.591573+00
fb3be848-3227-4b1d-bb14-13f8b299b0d7	1	FIRE_SMOKE	person	0.4872068762779236	{"x_min": 0.5575, "y_min": 0.2296, "x_max": 0.5979, "y_max": 0.2761}	17184	11.44	2026-10-13 08:45:32.796376+00
611c06c5-0337-487b-b2bd-3d033be60857	1	FIRE_SMOKE	vest	0.7319410443305969	{"x_min": 0.559, "y_min": 0.25, "x_max": 0.5929, "y_max": 0.2713}	17184	11.44	2026-10-13 08:45:32.796376+00
01c1ea23-d18c-488e-84d3-0ceef6924e88	1	FIRE_SMOKE	gloves	0.2280597686767578	{"x_min": 0.5765, "y_min": 0.2479, "x_max": 0.5987, "y_max": 0.2708}	17184	11.44	2026-10-13 08:45:32.796376+00
17445b99-7c7c-4ba2-a2d4-f75148ad8428	1	FIRE_SMOKE	person	0.8462628722190857	{"x_min": 0.2467, "y_min": 0.1175, "x_max": 0.4043, "y_max": 0.6345}	7328	12.95	2026-10-13 08:31:51.546661+00
fd945aaf-fcb4-4984-a59f-08a518d8a945	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.2661, "y_min": 0.1478, "x_max": 0.3844, "y_max": 0.2332}	7328	12.95	2026-10-13 08:31:51.546661+00
0851bb08-1c3d-49aa-af79-7167c9916150	1	FIRE_SMOKE	gloves	0.3562825322151184	{"x_min": 0.2406, "y_min": 0.1947, "x_max": 0.3837, "y_max": 0.4688}	7328	12.95	2026-10-13 08:31:51.546661+00
fd388d64-40da-455a-9db4-6c1fbeebb124	1	FIRE_SMOKE	person	0.8550522923469543	{"x_min": 0.5299, "y_min": 0.1908, "x_max": 0.559, "y_max": 0.2095}	15360	11.95	2026-10-13 08:43:00.856434+00
ec4b6ad9-9808-4153-b509-9d485a6327d9	1	FIRE_SMOKE	person	0.8465312123298645	{"x_min": 0.4725, "y_min": 0.1619, "x_max": 0.5119, "y_max": 0.31}	16104	11.98	2026-10-13 08:44:02.846655+00
f24d7981-38b5-4b78-8d6e-0e8e4d92c805	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4772, "y_min": 0.1695, "x_max": 0.5067, "y_max": 0.1941}	16104	11.98	2026-10-13 08:44:02.846655+00
eef393be-d9d1-4129-9485-5206a7b1cacb	1	FIRE_SMOKE	vest	0.6795106530189514	{"x_min": 0.0, "y_min": 0.4956, "x_max": 0.9267, "y_max": 0.9993}	16104	11.98	2026-10-13 08:44:02.846655+00
5fc64a6b-dbbc-4789-9a75-43dbe34cbc65	1	FIRE_SMOKE	person	0.4552857577800751	{"x_min": 0.4938, "y_min": 0.2298, "x_max": 0.5748, "y_max": 0.3433}	17388	12.96	2026-10-13 08:45:49.812591+00
162732d8-7aa3-4390-ba72-a26925c40ffa	1	FIRE_SMOKE	goggles	0.1652020961046219	{"x_min": 0.5185, "y_min": 0.223, "x_max": 0.5548, "y_max": 0.237}	17388	12.96	2026-10-13 08:45:49.812591+00
7079540e-9345-4f40-a850-5cce31bad3ee	1	FIRE_SMOKE	goggles	0.12199082970619202	{"x_min": 0.5442, "y_min": 0.2632, "x_max": 0.5671, "y_max": 0.2885}	17388	12.96	2026-10-13 08:45:49.812591+00
fd37041e-6814-467c-8c71-8a70dfe974b6	1	FIRE_SMOKE	person	0.9900000095367432	{"x_min": 0.2855, "y_min": 0.0934, "x_max": 0.4038, "y_max": 0.6063}	7372	15.87	2026-10-13 08:31:55.144515+00
968d8908-31fe-4141-8eca-2e0e080e70ce	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.2997, "y_min": 0.1238, "x_max": 0.3884, "y_max": 0.2079}	7372	15.87	2026-10-13 08:31:55.144515+00
6bc637ae-1a35-4e9e-acff-7fb122cc6c05	1	FIRE_SMOKE	person	0.9551354646682739	{"x_min": 0.5314, "y_min": 0.1925, "x_max": 0.559, "y_max": 0.2095}	15564	12.5	2026-10-13 08:43:17.875655+00
04a3f6e0-d5c1-4e57-8345-80c1ec3be60d	1	FIRE_SMOKE	person	0.5133154392242432	{"x_min": 0.5534, "y_min": 0.235, "x_max": 0.5994, "y_max": 0.2763}	19596	11.98	2026-10-13 08:48:53.868936+00
ad29e17d-b6d7-4cab-b480-37324b45e348	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.5565, "y_min": 0.2404, "x_max": 0.5954, "y_max": 0.2542}	19596	11.98	2026-10-13 08:48:53.868936+00
140e0c17-c18d-4b2d-aee4-3fe46dc58cc8	1	FIRE_SMOKE	gloves	0.25688573718070984	{"x_min": 0.557, "y_min": 0.2467, "x_max": 0.5984, "y_max": 0.2974}	19596	11.98	2026-10-13 08:48:53.868936+00
d9993b6b-dd7a-4756-b4c5-649e257e50fd	1	FIRE_SMOKE	person	0.7225590944290161	{"x_min": 0.5306, "y_min": 0.1975, "x_max": 0.559, "y_max": 0.2095}	15236	12.59	2026-10-13 08:42:50.498547+00
4d356783-1da3-4943-8f48-df5a1526bd5e	1	FIRE_SMOKE	person	0.6438353061676025	{"x_min": 0.5145, "y_min": 0.1712, "x_max": 0.547, "y_max": 0.2095}	15608	12.41	2026-10-13 08:43:21.591308+00
70574824-2b18-4903-92de-379c93a27cd9	1	FIRE_SMOKE	vest	0.9900000095367432	{"x_min": 0.5139, "y_min": 0.1904, "x_max": 0.5465, "y_max": 0.2054}	15608	12.41	2026-10-13 08:43:21.591308+00
e4c5e648-62a6-4e83-a5dd-84d4295b0c50	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.5168, "y_min": 0.1737, "x_max": 0.5437, "y_max": 0.1833}	15608	12.41	2026-10-13 08:43:21.591308+00
2c3b8545-d0cf-476d-b60e-9eb9ebe2f3b9	1	FIRE_SMOKE	person	0.7692054510116577	{"x_min": 0.5274, "y_min": 0.1919, "x_max": 0.5572, "y_max": 0.2095}	15464	11.93	2026-10-13 08:43:09.588322+00
c90470b5-782f-4a33-9ce9-01380f9df086	1	FIRE_SMOKE	vest	0.9597287178039551	{"x_min": 0.5263, "y_min": 0.2179, "x_max": 0.5568, "y_max": 0.2233}	15464	11.93	2026-10-13 08:43:09.588322+00
2f868e8c-2694-4490-b7e5-c32ecf951800	1	FIRE_SMOKE	goggles	0.12199082970619202	{"x_min": 0.5442, "y_min": 0.2632, "x_max": 0.5671, "y_max": 0.2885}	17436	11.99	2026-10-13 08:45:53.813564+00
79745ae2-4f7d-4562-968d-1f1b89e6da73	1	FIRE_SMOKE	person	0.49476924538612366	{"x_min": 0.5526, "y_min": 0.308, "x_max": 0.5721, "y_max": 0.3448}	23376	12.76	2026-10-13 08:54:08.869978+00
721b5b2a-6045-4ead-af99-dd0744116da6	1	FIRE_SMOKE	person	0.44724586606025696	{"x_min": 0.4748, "y_min": 0.1672, "x_max": 0.5537, "y_max": 0.376}	24460	12.5	2026-10-13 08:55:39.090363+00
7b96c099-2934-47eb-84f2-bc0af7c3994e	1	FIRE_SMOKE	vest	0.7379950284957886	{"x_min": 0.497, "y_min": 0.3011, "x_max": 0.5546, "y_max": 0.3585}	24460	12.5	2026-10-13 08:55:39.090363+00
aefcf0dd-0272-4631-897c-43e646e2d04d	1	FIRE_SMOKE	vest	0.7379950284957886	{"x_min": 0.497, "y_min": 0.3011, "x_max": 0.5546, "y_max": 0.3585}	24504	12.53	2026-10-13 08:55:42.852405+00
9b88392a-d85a-4770-b22a-ddcd25665f80	1	FIRE_SMOKE	goggles	0.12963183224201202	{"x_min": 0.501, "y_min": 0.1888, "x_max": 0.5316, "y_max": 0.215}	24504	12.53	2026-10-13 08:55:42.852405+00
739f04dd-6b36-4da0-9dff-230cecce9b0b	1	FIRE_SMOKE	goggles	0.12735548615455627	{"x_min": 0.4815, "y_min": 0.2097, "x_max": 0.5066, "y_max": 0.2302}	24504	12.53	2026-10-13 08:55:42.852405+00
d23f3bb6-9efa-4925-8d75-7cb6ea01bf04	1	FIRE_SMOKE	person	0.4941769242286682	{"x_min": 0.6052, "y_min": 0.3788, "x_max": 0.6208, "y_max": 0.3886}	25576	11.61	2026-10-13 08:57:12.09381+00
6ae03ba2-83fa-43ae-8689-1ebda66cf55f	1	FIRE_SMOKE	vest	0.9459316730499268	{"x_min": 0.6099, "y_min": 0.3818, "x_max": 0.6195, "y_max": 0.3915}	25576	11.61	2026-10-13 08:57:12.09381+00
188b4a64-d329-4ad3-b3a7-aba437ca8787	1	FIRE_SMOKE	gloves	0.2199135720729828	{"x_min": 0.6048, "y_min": 0.3798, "x_max": 0.6118, "y_max": 0.3897}	25576	11.61	2026-10-13 08:57:12.09381+00
8bfb176a-de42-46aa-8e93-37655e03bbd8	1	FIRE_SMOKE	person	0.5206875205039978	{"x_min": 0.4852, "y_min": 0.2151, "x_max": 0.6072, "y_max": 0.4206}	32620	11.97	2026-10-13 09:06:58.977344+00
04269761-cb13-4198-9dc6-c717ebcdbe9b	1	FIRE_SMOKE	goggles	0.3031596541404724	{"x_min": 0.4811, "y_min": 0.291, "x_max": 0.573, "y_max": 0.2923}	32620	11.97	2026-10-13 09:06:58.977344+00
5b4d8973-29e8-4285-9c3e-10412e3cb74a	1	FIRE_SMOKE	goggles	0.180749773979187	{"x_min": 0.568, "y_min": 0.2031, "x_max": 0.6186, "y_max": 0.2251}	32620	11.97	2026-10-13 09:06:58.977344+00
c16c5a68-a79b-46ca-b345-b821a4375a3b	1	FIRE_SMOKE	goggles	0.14337226748466492	{"x_min": 0.5343, "y_min": 0.2031, "x_max": 0.573, "y_max": 0.2389}	32620	11.97	2026-10-13 09:06:58.977344+00
307dd63a-afc1-4cc0-93b0-6b21a43d36b1	1	FIRE_SMOKE	goggles	0.12989386916160583	{"x_min": 0.507, "y_min": 0.2031, "x_max": 0.5494, "y_max": 0.2446}	32620	11.97	2026-10-13 09:06:58.977344+00
2e6464ed-5276-4266-92f1-0f134a81aaa5	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4966, "y_min": 0.235, "x_max": 0.5948, "y_max": 0.2867}	32664	12.51	2026-10-13 09:07:02.674653+00
fdba9970-7bd2-4147-aa7d-e5bd22bea40c	1	FIRE_SMOKE	vest	0.7712926864624023	{"x_min": 0.0, "y_min": 0.491, "x_max": 0.9717, "y_max": 0.9993}	32664	12.51	2026-10-13 09:07:02.674653+00
5dd4aa84-7b3d-4698-8935-314df93e7ed8	1	FIRE_SMOKE	smoke	0.7537	{"x_min": 0.4132, "y_min": 0.4117, "x_max": 0.9892, "y_max": 0.9989}	33124	11.34	2026-10-13 09:07:40.973554+00
502c6850-9712-4300-9447-0b56bf838c49	1	FIRE_SMOKE	person	0.5733481049537659	{"x_min": 0.5939, "y_min": 0.2061, "x_max": 0.6363, "y_max": 0.257}	39208	12.33	2026-10-13 09:16:07.819321+00
4be3d7f0-b8ee-4183-a5cb-bfd160f9b07c	1	FIRE_SMOKE	vest	0.9900000095367432	{"x_min": 0.5967, "y_min": 0.2259, "x_max": 0.6298, "y_max": 0.2513}	39208	12.33	2026-10-13 09:16:07.819321+00
161315fe-5661-44ac-acbe-bc4a5d43ca2c	1	FIRE_SMOKE	person	0.8383554816246033	{"x_min": 0.5572, "y_min": 0.2407, "x_max": 0.593, "y_max": 0.257}	39688	12.31	2026-10-13 09:16:47.808095+00
577469d6-b0ae-4240-895e-49fb4ee4fa4a	1	FIRE_SMOKE	person	0.5555151700973511	{"x_min": 0.5219, "y_min": 0.2604, "x_max": 0.6069, "y_max": 0.3427}	48728	9.8	2026-10-13 09:29:17.586687+00
1c978d0b-cf38-435e-b82d-ff2777773637	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.5282, "y_min": 0.2716, "x_max": 0.6001, "y_max": 0.2999}	48728	9.8	2026-10-13 09:29:17.586687+00
503a59ae-090d-41ea-9f14-b5a14ea02d65	1	FIRE_SMOKE	vest	0.7114138603210449	{"x_min": 0.5219, "y_min": 0.307, "x_max": 0.5939, "y_max": 0.3856}	48728	9.8	2026-10-13 09:29:17.586687+00
1a4ea6c1-64b9-4a1a-b7a7-5515bec2654d	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.5282, "y_min": 0.2716, "x_max": 0.6001, "y_max": 0.2999}	48780	10.8	2026-10-13 09:29:20.949921+00
86780e04-28b0-4ddb-a080-572fa30ef5de	1	FIRE_SMOKE	vest	0.7114138603210449	{"x_min": 0.5219, "y_min": 0.307, "x_max": 0.5939, "y_max": 0.3856}	48780	10.8	2026-10-13 09:29:20.949921+00
1617c48e-c733-4b7a-bbef-ee81271d195e	1	FIRE_SMOKE	person	0.9900000095367432	{"x_min": 0.2699, "y_min": 0.0975, "x_max": 0.4009, "y_max": 0.592}	49392	9.98	2026-10-13 09:30:12.231885+00
f502834b-0ca6-407d-bbc6-1caf34d145c5	1	FIRE_SMOKE	goggles	0.14119166135787964	{"x_min": 0.3952, "y_min": 0.1659, "x_max": 0.4133, "y_max": 0.259}	49392	9.98	2026-10-13 09:30:12.231885+00
4c3e677e-c720-4c1d-ac2c-6f740642b209	1	FIRE_SMOKE	goggles	0.14119166135787964	{"x_min": 0.3952, "y_min": 0.1659, "x_max": 0.4133, "y_max": 0.259}	49436	8.99	2026-10-13 09:30:15.551176+00
86bdfbdc-0446-4ecf-84b3-f75ffdac389e	1	FIRE_SMOKE	person	0.7479617595672607	{"x_min": 0.3419, "y_min": 0.0771, "x_max": 0.4612, "y_max": 0.5898}	49460	12.95	2026-10-13 09:30:17.991872+00
bcaf7614-00bc-4ad5-9033-cc20de5c6dd0	1	FIRE_SMOKE	smoke	0.7653	{"x_min": 0.4154, "y_min": 0.4517, "x_max": 1.0, "y_max": 1.0}	51200	9.17	2026-10-13 09:32:42.383619+00
34a28b09-6fa4-475c-a626-f564259939fb	1	FIRE_SMOKE	smoke	0.7974	{"x_min": 0.4156, "y_min": 0.4488, "x_max": 0.9993, "y_max": 1.0}	51740	9.75	2026-10-13 09:33:27.064263+00
2632cb8d-8026-4b7c-a02a-89fca382ccab	1	FIRE_SMOKE	person	0.48159417510032654	{"x_min": 0.4832, "y_min": 0.2488, "x_max": 0.5944, "y_max": 0.3827}	51788	13.41	2026-10-13 09:33:30.931915+00
da984e6b-c595-44e2-bce4-81d183fefb7f	1	FIRE_SMOKE	goggles	0.30709075927734375	{"x_min": 0.4768, "y_min": 0.3169, "x_max": 0.5577, "y_max": 0.3179}	51788	13.41	2026-10-13 09:33:30.931915+00
3fcadff5-2252-4979-b2c4-b284d789d5ae	1	FIRE_SMOKE	goggles	0.14964017271995544	{"x_min": 0.5163, "y_min": 0.3172, "x_max": 0.5992, "y_max": 0.3179}	51788	13.41	2026-10-13 09:33:30.931915+00
2a108a85-adf3-4250-b4a1-d92d16bb0627	1	FIRE_SMOKE	goggles	0.13240644335746765	{"x_min": 0.5057, "y_min": 0.241, "x_max": 0.5409, "y_max": 0.255}	51788	13.41	2026-10-13 09:33:30.931915+00
5a374466-4205-4d3f-be77-f062afff63e3	1	FIRE_SMOKE	vest	0.8489943742752075	{"x_min": 0.4959, "y_min": 0.2696, "x_max": 0.5633, "y_max": 0.3588}	51824	14.6	2026-10-13 09:33:33.972051+00
c24ab90b-b4ca-4fe7-9508-3466f249a9bb	1	FIRE_SMOKE	vest	0.7489949464797974	{"x_min": 0.4927, "y_min": 0.3102, "x_max": 0.5868, "y_max": 0.3686}	51824	14.6	2026-10-13 09:33:33.972051+00
f8055592-9841-4ffe-8269-e4253a237758	1	FIRE_SMOKE	person	0.47897103428840637	{"x_min": 0.4934, "y_min": 0.2296, "x_max": 0.5862, "y_max": 0.3585}	68	21.76	2026-10-13 09:36:47.233635+00
9cebf8f0-da43-4c20-9bc8-e541d4ea56ad	1	FIRE_SMOKE	gloves	0.8003025054931641	{"x_min": 0.5564, "y_min": 0.326, "x_max": 0.5749, "y_max": 0.3434}	68	21.76	2026-10-13 09:36:47.233635+00
9714192c-ba87-44af-9958-548cec5d7049	1	FIRE_SMOKE	person	0.637208878993988	{"x_min": 0.487, "y_min": 0.1586, "x_max": 0.5462, "y_max": 0.2799}	1820	10.23	2026-10-13 09:39:12.259219+00
34c206e4-8cf9-48c0-84b4-c2c3c14c5e37	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.494, "y_min": 0.1653, "x_max": 0.5383, "y_max": 0.1851}	1820	10.23	2026-10-13 09:39:12.259219+00
86bdc8d0-c320-4a54-8095-27af1c569e5f	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.494, "y_min": 0.1653, "x_max": 0.5383, "y_max": 0.1851}	1856	11.67	2026-10-13 09:39:14.987204+00
8a9c6b74-1451-4427-8099-0f42ab8d6b51	1	FIRE_SMOKE	person	0.8552103042602539	{"x_min": 0.4881, "y_min": 0.1615, "x_max": 0.546, "y_max": 0.2799}	1928	13.16	2026-10-13 09:39:21.129346+00
1b4773b3-9861-48a4-a8c1-c2a4c245e810	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4946, "y_min": 0.1677, "x_max": 0.539, "y_max": 0.1875}	1928	13.16	2026-10-13 09:39:21.129346+00
85f4d515-62c3-4d9b-a7f7-f61905286bc3	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4946, "y_min": 0.1677, "x_max": 0.539, "y_max": 0.1875}	1976	14.82	2026-10-13 09:39:24.990719+00
e85f2696-a6ba-4fbb-ae7e-856de83ffba1	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4946, "y_min": 0.1767, "x_max": 0.539, "y_max": 0.1941}	2052	10.37	2026-10-13 09:39:31.346108+00
7fd6222f-01c0-479e-8172-b546766bc51e	1	FIRE_SMOKE	gloves	0.2200300693511963	{"x_min": 0.487, "y_min": 0.2181, "x_max": 0.5474, "y_max": 0.2701}	2052	10.37	2026-10-13 09:39:31.346108+00
2fcd6265-5749-45f1-b6ae-f99072e1a4c6	1	FIRE_SMOKE	person	0.8495033979415894	{"x_min": 0.4869, "y_min": 0.1631, "x_max": 0.5462, "y_max": 0.2799}	2092	15.46	2026-10-13 09:39:34.373313+00
06cc836f-3e62-4752-b4e9-d906b18c41c2	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.494, "y_min": 0.1689, "x_max": 0.5383, "y_max": 0.1887}	2092	15.46	2026-10-13 09:39:34.373313+00
c702c854-9414-4adf-8b79-980e08fed59e	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.494, "y_min": 0.1689, "x_max": 0.5383, "y_max": 0.1887}	2144	17.75	2026-10-13 09:39:38.694418+00
8e6f5a50-d2f8-448a-bccf-4f982d7539cd	1	FIRE_SMOKE	person	0.9900000095367432	{"x_min": 0.4883, "y_min": 0.1678, "x_max": 0.5462, "y_max": 0.2799}	2208	17.75	2026-10-13 09:39:44.457224+00
4d1fff61-f038-4ea2-a6dd-9facc0ab0671	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4946, "y_min": 0.1737, "x_max": 0.539, "y_max": 0.1923}	2208	17.75	2026-10-13 09:39:44.457224+00
e3e13864-97f5-45e5-b7ed-9790e12fdbdb	1	FIRE_SMOKE	person	0.5200594663619995	{"x_min": 0.4897, "y_min": 0.1486, "x_max": 0.5462, "y_max": 0.2799}	2416	13.8	2026-10-13 09:40:01.687987+00
711c7dd2-0dd8-4fac-ba60-367637daca5b	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.496, "y_min": 0.1556, "x_max": 0.539, "y_max": 0.1773}	2416	13.8	2026-10-13 09:40:01.687987+00
71866e99-3ed5-40d7-a695-8ce12afef904	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.496, "y_min": 0.1556, "x_max": 0.539, "y_max": 0.1773}	2448	10.14	2026-10-13 09:40:04.466039+00
b85d6c47-ee4e-4b38-a93b-0e18756aed95	1	FIRE_SMOKE	smoke	0.7497	{"x_min": 0.4165, "y_min": 0.4592, "x_max": 0.9992, "y_max": 1.0}	2580	9.49	2026-10-13 09:40:15.304192+00
21da398a-a681-41ce-a14e-53b0407d905e	1	FIRE_SMOKE	person	0.9900000095367432	{"x_min": 0.3431, "y_min": 0.1035, "x_max": 0.4766, "y_max": 0.5606}	4748	11.58	2026-10-13 09:43:15.329189+00
b0c8d382-c82b-41a0-9c43-ebb110584ef4	1	FIRE_SMOKE	goggles	0.13382546603679657	{"x_min": 0.3703, "y_min": 0.0763, "x_max": 0.4778, "y_max": 0.1599}	4792	12.28	2026-10-13 09:43:19.065623+00
6a602446-ec53-4176-a8ff-c5c5b3e4ecd7	1	FIRE_SMOKE	person	0.9900000095367432	{"x_min": 0.4322, "y_min": 0.1623, "x_max": 0.5419, "y_max": 0.475}	4932	12.33	2026-10-13 09:43:30.716448+00
e42f959c-dc3f-4ba0-b06f-2de41c4013b7	1	FIRE_SMOKE	person	0.8555272817611694	{"x_min": 0.4528, "y_min": 0.1032, "x_max": 0.5396, "y_max": 0.4863}	4968	12.25	2026-10-13 09:43:33.718927+00
d77777d0-2e9e-4f65-8bb0-8894640d4a08	1	FIRE_SMOKE	person	0.9900000095367432	{"x_min": 0.4883, "y_min": 0.1709, "x_max": 0.5462, "y_max": 0.2797}	2004	8.38	2026-10-13 09:39:27.765061+00
795eafa6-08a3-4ba3-80d7-701c83bd9515	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4946, "y_min": 0.1767, "x_max": 0.539, "y_max": 0.1941}	2004	8.38	2026-10-13 09:39:27.765061+00
7101e750-0ab7-441a-a0c4-47903ab58419	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4946, "y_min": 0.1737, "x_max": 0.539, "y_max": 0.1923}	2244	19.38	2026-10-13 09:39:47.075158+00
3c0b8362-bfbc-4a5d-bb3d-7f5f94502350	1	FIRE_SMOKE	gloves	0.31368744373321533	{"x_min": 0.4859, "y_min": 0.1839, "x_max": 0.5266, "y_max": 0.2274}	2244	19.38	2026-10-13 09:39:47.075158+00
0d26c84e-0136-4459-b1d6-835c98026e99	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4583, "y_min": 0.1424, "x_max": 0.5276, "y_max": 0.2013}	5008	12.26	2026-10-13 09:43:37.057977+00
87a49e71-408d-4157-b60d-f9791eb49ac8	1	FIRE_SMOKE	person	0.6680999398231506	{"x_min": 0.4193, "y_min": 0.0465, "x_max": 0.5217, "y_max": 0.4883}	5048	11.82	2026-10-13 09:43:40.317504+00
1905bb49-f4ee-4f90-a801-085c12596ead	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4315, "y_min": 0.0721, "x_max": 0.5087, "y_max": 0.1448}	5048	11.82	2026-10-13 09:43:40.317504+00
c169fb32-e329-4a56-9579-c5106c22eacf	1	FIRE_SMOKE	safety_shoes	0.3872314393520355	{"x_min": 0.4833, "y_min": 0.2094, "x_max": 0.6466, "y_max": 0.5056}	5048	11.82	2026-10-13 09:43:40.317504+00
28102249-d38c-414e-bc84-a42559e8fe63	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4315, "y_min": 0.0721, "x_max": 0.5087, "y_max": 0.1448}	5080	12.99	2026-10-13 09:43:43.059798+00
e358f104-9d92-4827-a052-2256cfce1072	1	FIRE_SMOKE	person	0.9900000095367432	{"x_min": 0.4639, "y_min": 0.1274, "x_max": 0.5942, "y_max": 0.7572}	5292	11.87	2026-10-13 09:44:00.725586+00
0c69e398-420e-4fcd-9cd1-cdad5ea30f97	1	FIRE_SMOKE	goggles	0.6582470536231995	{"x_min": 0.4491, "y_min": 0.195, "x_max": 0.6041, "y_max": 0.5638}	5292	11.87	2026-10-13 09:44:00.725586+00
56cd3a4a-1707-47ac-bab3-fed461a2ad4c	1	FIRE_SMOKE	person	0.9900000095367432	{"x_min": 0.4206, "y_min": 0.1208, "x_max": 0.5745, "y_max": 0.7402}	5320	12.84	2026-10-13 09:44:03.06606+00
4c8ce3ba-3696-4643-a568-232ac7aa6d39	1	FIRE_SMOKE	smoke	0.7742	{"x_min": 0.4123, "y_min": 0.4921, "x_max": 0.9998, "y_max": 1.0}	5320	12.84	2026-10-13 09:44:03.06606+00
3894af1a-27b9-47da-88e7-354ec4acfa8d	1	FIRE_SMOKE	person	0.9900000095367432	{"x_min": 0.3967, "y_min": 0.0846, "x_max": 0.5733, "y_max": 0.7363}	5360	12.18	2026-10-13 09:44:06.324348+00
82676548-6258-4adf-80df-a56066cac59e	1	FIRE_SMOKE	goggles	0.45061033964157104	{"x_min": 0.416, "y_min": 0.2512, "x_max": 0.5538, "y_max": 0.3311}	5360	12.18	2026-10-13 09:44:06.324348+00
26eb91e2-e8fd-4326-8857-9a6207cea766	1	FIRE_SMOKE	goggles	0.37531012296676636	{"x_min": 0.4106, "y_min": 0.0469, "x_max": 0.5511, "y_max": 0.1653}	5360	12.18	2026-10-13 09:44:06.324348+00
6b49cf4c-a40b-4d18-b358-8b4b4501b5e8	1	FIRE_SMOKE	goggles	0.2946033179759979	{"x_min": 0.379, "y_min": 0.1839, "x_max": 0.4281, "y_max": 0.3317}	5360	12.18	2026-10-13 09:44:06.324348+00
1a5f3bff-d2f5-4955-8afe-8f2c589e1842	1	FIRE_SMOKE	goggles	0.642064094543457	{"x_min": 0.4875, "y_min": 0.1152, "x_max": 0.6727, "y_max": 0.5014}	5408	15.94	2026-10-13 09:44:10.472576+00
d2681e4b-a21d-4fba-9d55-0243adf2a81f	1	FIRE_SMOKE	person	0.9900000095367432	{"x_min": 0.4671, "y_min": 0.149, "x_max": 0.6358, "y_max": 0.6196}	5460	11.86	2026-10-13 09:44:14.726504+00
c4136a22-f837-4fd7-99bb-2167c9ab84bb	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4886, "y_min": 0.1767, "x_max": 0.6142, "y_max": 0.2542}	5460	11.86	2026-10-13 09:44:14.726504+00
9af2e17a-5137-482a-ad99-7c0cffe90552	1	FIRE_SMOKE	gloves	0.3902505040168762	{"x_min": 0.5544, "y_min": 0.4964, "x_max": 0.6055, "y_max": 0.5535}	5460	11.86	2026-10-13 09:44:14.726504+00
2a69d8f3-5c6e-497a-ad5e-8599e064b995	1	FIRE_SMOKE	gloves	0.30671101808547974	{"x_min": 0.4637, "y_min": 0.2212, "x_max": 0.6169, "y_max": 0.4441}	5460	11.86	2026-10-13 09:44:14.726504+00
df287b1a-89c7-4a50-b647-847795f391be	1	FIRE_SMOKE	gloves	0.4968532919883728	{"x_min": 0.5558, "y_min": 0.4982, "x_max": 0.6048, "y_max": 0.5523}	5500	12.1	2026-10-13 09:44:18.068368+00
602a15c0-6905-4968-9920-2931f1236e1c	1	FIRE_SMOKE	fire	0.5933	{"x_min": 0.6383, "y_min": 0.4997, "x_max": 0.7072, "y_max": 0.5998}	5568	11.58	2026-10-13 09:44:23.75286+00
76e27b99-93e7-49fd-bf11-f7e7e5dbd974	1	FIRE_SMOKE	smoke	0.7578	{"x_min": 0.4116, "y_min": 0.4125, "x_max": 0.9876, "y_max": 0.9994}	5644	11.72	2026-10-13 09:44:30.067851+00
1082b7d7-5c47-49fc-b2b1-6ff5caa4ac44	1	FIRE_SMOKE	person	0.5616345405578613	{"x_min": 0.492, "y_min": 0.1346, "x_max": 0.634, "y_max": 0.6365}	5688	12.07	2026-10-13 09:44:33.727253+00
94afcf17-4a77-4745-a49a-2aa4dfc68779	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.5094, "y_min": 0.1635, "x_max": 0.6163, "y_max": 0.2464}	5688	12.07	2026-10-13 09:44:33.727253+00
74c6dc4d-0a55-497e-8d34-e9cff4a46daa	1	FIRE_SMOKE	gloves	0.38023513555526733	{"x_min": 0.5558, "y_min": 0.4952, "x_max": 0.6048, "y_max": 0.5505}	5688	12.07	2026-10-13 09:44:33.727253+00
ede75751-f879-4bff-9beb-1b0b6b1d4b15	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.5094, "y_min": 0.1635, "x_max": 0.6163, "y_max": 0.2464}	5752	12	2026-10-13 09:44:39.064577+00
606d2a90-81b7-4b8e-bb5b-b817b78daf2e	1	FIRE_SMOKE	gloves	0.48948076367378235	{"x_min": 0.5517, "y_min": 0.4952, "x_max": 0.6048, "y_max": 0.5511}	5752	12	2026-10-13 09:44:39.064577+00
1ca7d5d6-d16f-43d9-8d38-63d591d4f794	1	FIRE_SMOKE	smoke	0.7521	{"x_min": 0.4119, "y_min": 0.4124, "x_max": 0.9856, "y_max": 0.9997}	6032	11.91	2026-10-13 09:45:02.747039+00
52dfbb60-88b7-4af6-a9a6-d040f73cf804	1	FIRE_SMOKE	smoke	0.7765	{"x_min": 0.416, "y_min": 0.4608, "x_max": 1.0, "y_max": 1.0}	6220	11.87	2026-10-13 09:45:18.327225+00
e5faa39b-2d8f-46ef-83e2-99be89f4aa1b	1	FIRE_SMOKE	person	0.5510998964309692	{"x_min": 0.4835, "y_min": 0.1108, "x_max": 0.6404, "y_max": 0.6225}	6308	12.56	2026-10-13 09:45:25.726743+00
ded91192-815e-453d-b2ca-abdbe85185f8	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.5027, "y_min": 0.1406, "x_max": 0.6203, "y_max": 0.2248}	6308	12.56	2026-10-13 09:45:25.726743+00
e16b08db-2840-4ae6-b9d7-eee3a52f37b4	1	FIRE_SMOKE	gloves	0.7309070825576782	{"x_min": 0.5538, "y_min": 0.4946, "x_max": 0.6048, "y_max": 0.5517}	6308	12.56	2026-10-13 09:45:25.726743+00
e9d77b3f-7c97-4596-86ae-cd1cebacedce	1	FIRE_SMOKE	person	0.9900000095367432	{"x_min": 0.4613, "y_min": 0.1085, "x_max": 0.6582, "y_max": 0.6975}	6348	11.83	2026-10-13 09:45:29.067039+00
20f33e54-965b-4183-bfbd-e2dddf43fa90	1	FIRE_SMOKE	goggles	0.4303250312805176	{"x_min": 0.4393, "y_min": 0.0706, "x_max": 0.6049, "y_max": 0.5264}	6348	11.83	2026-10-13 09:45:29.067039+00
83f646d6-f6f3-4361-9e28-c2680bf730f0	1	FIRE_SMOKE	gloves	0.26395660638809204	{"x_min": 0.4536, "y_min": 0.1971, "x_max": 0.5948, "y_max": 0.5}	6348	11.83	2026-10-13 09:45:29.067039+00
70d528f7-6e00-44a6-a897-884d9e3bda98	1	FIRE_SMOKE	gloves	0.25003764033317566	{"x_min": 0.4684, "y_min": 0.4838, "x_max": 0.504, "y_max": 0.5276}	6348	11.83	2026-10-13 09:45:29.067039+00
f470f70c-1f6c-4b15-85bc-21b5f647db5d	1	FIRE_SMOKE	person	0.5985682606697083	{"x_min": 0.4495, "y_min": 0.0695, "x_max": 0.6012, "y_max": 0.6969}	6408	12.73	2026-10-13 09:45:34.06484+00
15ac1d47-c95b-441b-b00c-732169314ce4	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4684, "y_min": 0.1058, "x_max": 0.5813, "y_max": 0.2097}	6408	12.73	2026-10-13 09:45:34.06484+00
98b8402c-c47f-4290-b9ca-279f088f79df	1	FIRE_SMOKE	gloves	0.2042578160762787	{"x_min": 0.4429, "y_min": 0.1911, "x_max": 0.5894, "y_max": 0.5084}	6408	12.73	2026-10-13 09:45:34.06484+00
9a3efa79-730b-470a-b0c9-66089ffc9a25	1	FIRE_SMOKE	person	0.9900000095367432	{"x_min": 0.4044, "y_min": 0.1099, "x_max": 0.5706, "y_max": 0.7584}	6444	11.15	2026-10-13 09:45:37.224409+00
69389618-2bb7-459c-b4bc-edab62a013a9	1	FIRE_SMOKE	gloves	0.22615604102611542	{"x_min": 0.3978, "y_min": 0.2073, "x_max": 0.5645, "y_max": 0.5415}	6444	11.15	2026-10-13 09:45:37.224409+00
2def6609-6e1d-4750-8b56-8ff080e92f26	1	FIRE_SMOKE	smoke	0.7729	{"x_min": 0.4116, "y_min": 0.413, "x_max": 0.9888, "y_max": 0.9999}	6984	11.99	2026-10-13 09:46:22.138725+00
96c8ef71-93cc-486d-bb91-5a1960994f26	1	FIRE_SMOKE	person	0.5195804238319397	{"x_min": 0.7211, "y_min": 0.0346, "x_max": 0.7829, "y_max": 0.2225}	8744	11.83	2026-10-13 09:48:52.089238+00
e8ef8aa3-863e-4e74-8d68-b320e3ea76f2	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.7285, "y_min": 0.0451, "x_max": 0.7749, "y_max": 0.0757}	8744	11.83	2026-10-13 09:48:52.089238+00
572fdd5c-4425-4b37-84a1-3629811a2ae7	1	FIRE_SMOKE	gloves	0.8757691383361816	{"x_min": 0.7309, "y_min": 0.1933, "x_max": 0.7656, "y_max": 0.2066}	8744	11.83	2026-10-13 09:48:52.089238+00
2c568bcb-37d0-45db-946d-9c6b9b9fb2d1	1	FIRE_SMOKE	person	0.4533795416355133	{"x_min": 0.6496, "y_min": 0.1878, "x_max": 0.777, "y_max": 0.5764}	8932	11.83	2026-10-13 09:49:07.750232+00
91d6a6c4-2357-434a-b009-f08d85eab3a3	1	FIRE_SMOKE	goggles	0.6378054022789001	{"x_min": 0.6519, "y_min": 0.2626, "x_max": 0.754, "y_max": 0.3341}	8932	11.83	2026-10-13 09:49:07.750232+00
54a332b9-30d4-4b54-b80e-84caad6833f8	1	FIRE_SMOKE	goggles	0.45569443702697754	{"x_min": 0.6371, "y_min": 0.2175, "x_max": 0.6747, "y_max": 0.3323}	8932	11.83	2026-10-13 09:49:07.750232+00
2964e50b-8247-478a-8e13-5856d76f0e9e	1	FIRE_SMOKE	goggles	0.24726076424121857	{"x_min": 0.6734, "y_min": 0.1647, "x_max": 0.7453, "y_max": 0.2296}	8932	11.83	2026-10-13 09:49:07.750232+00
853e19ae-083b-479f-93b9-1d6233a3bd6f	1	FIRE_SMOKE	goggles	0.14990897476673126	{"x_min": 0.6364, "y_min": 0.1647, "x_max": 0.7184, "y_max": 0.2181}	8932	11.83	2026-10-13 09:49:07.750232+00
046a2ca7-494e-434b-9a94-5abd4045d773	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4832, "y_min": 0.1743, "x_max": 0.5726, "y_max": 0.247}	9152	12.76	2026-10-13 09:49:26.085676+00
c2fad552-4d68-49f3-8e3c-ae827d6b7a77	1	FIRE_SMOKE	smoke	0.7581	{"x_min": 0.4129, "y_min": 0.4156, "x_max": 0.9557, "y_max": 0.9979}	9152	12.76	2026-10-13 09:49:26.085676+00
7c12cb72-3c8f-4bce-8f2e-7331ee802393	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4402, "y_min": 0.1388, "x_max": 0.5632, "y_max": 0.2434}	6500	11.83	2026-10-13 09:45:41.925759+00
bbe0c43c-7c54-4706-8a79-c4202e96ddc9	1	FIRE_SMOKE	goggles	0.15948553383350372	{"x_min": 0.4168, "y_min": 0.0955, "x_max": 0.4632, "y_max": 0.1516}	7136	12.85	2026-10-13 09:46:34.816031+00
3b8b6a41-c709-432b-a6e7-da67d53790ca	1	FIRE_SMOKE	smoke	0.7785	{"x_min": 0.4131, "y_min": 0.4513, "x_max": 1.0, "y_max": 1.0}	7136	12.85	2026-10-13 09:46:34.816031+00
bc1e4f74-1b57-4759-ba31-5004b8759794	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.7413, "y_min": 0.1094, "x_max": 0.8293, "y_max": 0.146}	8668	11.99	2026-10-13 09:48:45.736058+00
43199ce0-882d-44d4-b131-d08797c1d93c	1	FIRE_SMOKE	gloves	0.2767043113708496	{"x_min": 0.7218, "y_min": 0.1918, "x_max": 0.8043, "y_max": 0.3002}	8668	11.99	2026-10-13 09:48:45.736058+00
e805cee7-6cab-4f69-a2da-6986f59f4020	1	FIRE_SMOKE	person	0.7269457578659058	{"x_min": 0.7363, "y_min": 0.0555, "x_max": 0.8038, "y_max": 0.2288}	8852	11.83	2026-10-13 09:49:01.089971+00
a903d192-7f03-49b9-804f-8a0b8bd12db5	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.7446, "y_min": 0.0649, "x_max": 0.7944, "y_max": 0.0938}	8852	11.83	2026-10-13 09:49:01.089971+00
89ee80f8-53c2-47c1-a359-64ab3d01667b	1	FIRE_SMOKE	smoke	0.7754	{"x_min": 0.4131, "y_min": 0.4005, "x_max": 0.9604, "y_max": 1.0}	9096	11.8	2026-10-13 09:49:21.358396+00
56e7750c-665c-4ba5-bf87-08ed9755f97d	1	FIRE_SMOKE	smoke	0.7741	{"x_min": 0.4109, "y_min": 0.4138, "x_max": 0.9652, "y_max": 0.9994}	9296	11.98	2026-10-13 09:49:38.088296+00
f5347c5d-abea-4c31-aa5e-2075645f6b80	1	FIRE_SMOKE	person	0.9095128178596497	{"x_min": 0.4091, "y_min": 0.0763, "x_max": 0.533, "y_max": 0.5297}	7068	12.27	2026-10-13 09:46:29.135591+00
0521916c-fc62-4810-bb78-4297f7a5b1f8	1	FIRE_SMOKE	smoke	0.8068	{"x_min": 0.4115, "y_min": 0.4118, "x_max": 0.9828, "y_max": 0.9998}	7068	12.27	2026-10-13 09:46:29.135591+00
17db2d3b-8d10-4d0e-a975-c7b2bda1d631	1	FIRE_SMOKE	person	0.7392208576202393	{"x_min": 0.4372, "y_min": 0.1389, "x_max": 0.5561, "y_max": 0.5326}	7104	12.8	2026-10-13 09:46:32.13592+00
1f760ed5-1221-47e9-9e65-66ef75b7f4f6	1	FIRE_SMOKE	goggles	0.627994954586029	{"x_min": 0.4338, "y_min": 0.1967, "x_max": 0.5298, "y_max": 0.2871}	7104	12.8	2026-10-13 09:46:32.13592+00
3e626b50-47cc-4d58-8b3a-393da37fb496	1	FIRE_SMOKE	goggles	0.3102090060710907	{"x_min": 0.4628, "y_min": 0.1154, "x_max": 0.5498, "y_max": 0.1834}	7104	12.8	2026-10-13 09:46:32.13592+00
ab9beedc-b3cd-41cf-b151-dcb51147b606	1	FIRE_SMOKE	goggles	0.15948553383350372	{"x_min": 0.4254, "y_min": 0.1154, "x_max": 0.4712, "y_max": 0.169}	7104	12.8	2026-10-13 09:46:32.13592+00
c3a45cf0-a0cd-48c7-b776-1d59831945de	1	FIRE_SMOKE	smoke	0.802	{"x_min": 0.415, "y_min": 0.4123, "x_max": 0.9792, "y_max": 0.9999}	8576	11.99	2026-10-13 09:48:38.096348+00
afc25ae9-4bd8-4205-80eb-e0623565f092	1	FIRE_SMOKE	smoke	0.8112	{"x_min": 0.4146, "y_min": 0.4164, "x_max": 0.9995, "y_max": 1.0}	8780	12.9	2026-10-13 09:48:55.088694+00
9d562c58-6063-460a-8ba8-4e38973e1322	1	FIRE_SMOKE	goggles	0.14990897476673126	{"x_min": 0.6364, "y_min": 0.1647, "x_max": 0.7184, "y_max": 0.2181}	8968	13.82	2026-10-13 09:49:10.752708+00
c4b89b7a-6792-4d60-bfce-ec8d2c9a1bf0	1	FIRE_SMOKE	smoke	0.7511	{"x_min": 0.4117, "y_min": 0.4196, "x_max": 0.9869, "y_max": 0.9977}	8968	13.82	2026-10-13 09:49:10.752708+00
a39bb723-537b-4bc2-a9bd-d9fff79caba0	1	FIRE_SMOKE	person	0.9831376671791077	{"x_min": 0.5594, "y_min": 0.2184, "x_max": 0.6836, "y_max": 0.7127}	9200	12.84	2026-10-13 09:49:30.08817+00
e0aec36c-229e-4714-ba44-23e0e907b8a7	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.5746, "y_min": 0.247, "x_max": 0.668, "y_max": 0.3287}	9200	12.84	2026-10-13 09:49:30.08817+00
d2ce0862-67e3-4046-9c75-e8f7ed7e756a	1	FIRE_SMOKE	smoke	0.7711	{"x_min": 0.4138, "y_min": 0.4191, "x_max": 0.99, "y_max": 0.9987}	8500	11.91	2026-10-13 09:48:31.726548+00
71a9ed0f-bd17-4004-9a23-6d3ac690c045	1	FIRE_SMOKE	smoke	0.7795	{"x_min": 0.415, "y_min": 0.404, "x_max": 0.9656, "y_max": 1.0}	8732	11.96	2026-10-13 09:48:51.089267+00
9f4da3b5-77b6-417c-bb3f-7b856206158f	1	FIRE_SMOKE	gloves	0.2591478228569031	{"x_min": 0.7332, "y_min": 0.1021, "x_max": 0.8051, "y_max": 0.2092}	8884	12.97	2026-10-13 09:49:03.736424+00
984c6ec4-bd66-4262-92c8-35f0a5f31952	1	FIRE_SMOKE	smoke	0.7822	{"x_min": 0.4152, "y_min": 0.4029, "x_max": 0.9689, "y_max": 1.0}	8884	12.97	2026-10-13 09:49:03.736424+00
6e475e47-caea-464b-a75b-037b3b722a0f	1	FIRE_SMOKE	person	0.8365387320518494	{"x_min": 0.4686, "y_min": 0.1489, "x_max": 0.5876, "y_max": 0.5903}	9124	12.75	2026-10-13 09:49:23.750568+00
966490a7-1116-4bd1-beb4-2136ac3e6407	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4832, "y_min": 0.1743, "x_max": 0.5726, "y_max": 0.247}	9124	12.75	2026-10-13 09:49:23.750568+00
4e1d9754-1da6-41d6-8c0e-1ec2b5d18185	1	FIRE_SMOKE	gloves	0.24574439227581024	{"x_min": 0.5541, "y_min": 0.4952, "x_max": 0.5921, "y_max": 0.5547}	9124	12.75	2026-10-13 09:49:23.750568+00
6ce625e9-4ce2-4cbe-b749-ac2a37262237	1	FIRE_SMOKE	smoke	0.7828	{"x_min": 0.4113, "y_min": 0.4002, "x_max": 0.9448, "y_max": 1.0}	9328	11.86	2026-10-13 09:49:40.748175+00
b69b4973-bbad-4786-94ae-97cddb7adc0f	1	FIRE_SMOKE	person	0.742478609085083	{"x_min": 0.7267, "y_min": 0.0973, "x_max": 0.8443, "y_max": 0.3196}	8632	11.82	2026-10-13 09:48:42.728753+00
8014d9af-dc98-4632-9ecb-e9a92d0ead58	1	FIRE_SMOKE	smoke	0.7794	{"x_min": 0.4142, "y_min": 0.4017, "x_max": 0.9744, "y_max": 1.0}	8840	11.86	2026-10-13 09:49:00.094316+00
ae685798-98c3-4c90-bbd1-dadbbf5c827e	1	FIRE_SMOKE	smoke	0.7903	{"x_min": 0.4131, "y_min": 0.4175, "x_max": 0.9804, "y_max": 0.9989}	9036	11.81	2026-10-13 09:49:16.664934+00
175195d3-ffe2-4d2d-a374-c1409f9d12a2	1	FIRE_SMOKE	gloves	0.3606571853160858	{"x_min": 0.555, "y_min": 0.4948, "x_max": 0.6061, "y_max": 0.5514}	9232	12.75	2026-10-13 09:49:32.748724+00
bbf7aa68-5f98-45fd-94e6-14594b03fe22	1	FIRE_SMOKE	smoke	0.8193	{"x_min": 0.4126, "y_min": 0.418, "x_max": 0.9925, "y_max": 0.9983}	9232	12.75	2026-10-13 09:49:32.748724+00
a7f4bd7f-8c3d-4127-afd0-75aa1ccbfeda	1	FIRE_SMOKE	smoke	0.7483	{"x_min": 0.4117, "y_min": 0.4153, "x_max": 0.9553, "y_max": 0.9998}	9344	11.83	2026-10-13 09:49:42.086425+00
21fd591f-890c-4e64-bca8-96a33764833d	1	FIRE_SMOKE	smoke	0.7844	{"x_min": 0.4139, "y_min": 0.4149, "x_max": 0.9621, "y_max": 0.9983}	9444	11.99	2026-10-13 09:49:50.34757+00
abbd3978-d392-44cf-bad3-6115bdd119e1	1	FIRE_SMOKE	smoke	0.7592	{"x_min": 0.4127, "y_min": 0.414, "x_max": 0.9678, "y_max": 0.9992}	9476	12.72	2026-10-13 09:49:53.090717+00
ff23dc4a-b9a4-46a8-9709-e899264e2270	1	FIRE_SMOKE	smoke	0.7698	{"x_min": 0.4138, "y_min": 0.4166, "x_max": 0.9978, "y_max": 1.0}	9520	11.98	2026-10-13 09:49:56.74928+00
7a3ca607-5c3a-4f8c-a4e4-7beaa576db17	1	FIRE_SMOKE	smoke	0.7789	{"x_min": 0.4124, "y_min": 0.4158, "x_max": 0.9768, "y_max": 0.9981}	9568	11.91	2026-10-13 09:50:00.735058+00
facfcb5c-530f-4a4d-9232-1987c794243d	1	FIRE_SMOKE	smoke	0.7766	{"x_min": 0.4127, "y_min": 0.4002, "x_max": 0.9841, "y_max": 1.0}	9676	11.82	2026-10-13 09:50:09.748022+00
e9bc8edf-c574-45a1-bd42-c466a87d0155	1	FIRE_SMOKE	person	0.5882774591445923	{"x_min": 0.833, "y_min": 0.0357, "x_max": 0.8763, "y_max": 0.1403}	9748	12.74	2026-10-13 09:50:15.736646+00
8748b13a-b3a7-4f2e-9950-ef3905e78319	1	FIRE_SMOKE	smoke	0.7979	{"x_min": 0.4145, "y_min": 0.416, "x_max": 0.9842, "y_max": 0.9998}	9888	11.94	2026-10-13 09:50:27.347766+00
99527a4b-9564-4baa-a18b-4d3e92dc225f	1	FIRE_SMOKE	smoke	0.8065	{"x_min": 0.4127, "y_min": 0.4159, "x_max": 0.9764, "y_max": 1.0}	9960	11.94	2026-10-13 09:50:33.336686+00
bb25116d-eadb-4c7e-ba3c-71d0b5830cd1	1	FIRE_SMOKE	smoke	0.7767	{"x_min": 0.4134, "y_min": 0.4132, "x_max": 0.9836, "y_max": 0.9986}	10016	12.55	2026-10-13 09:50:38.088057+00
ab6c52b5-3855-48a2-8cc5-2a3bb641979f	1	FIRE_SMOKE	smoke	0.7856	{"x_min": 0.411, "y_min": 0.4132, "x_max": 0.9726, "y_max": 0.9994}	10100	11.99	2026-10-13 09:50:45.092401+00
ee7cf3ca-5916-44f9-80b8-9e23c1cd6bbd	1	FIRE_SMOKE	smoke	0.7513	{"x_min": 0.4161, "y_min": 0.4008, "x_max": 0.9855, "y_max": 1.0}	10116	12.57	2026-10-13 09:50:46.337732+00
d0ca2759-3e0c-4456-bf9c-0c0bb3b57e4b	1	FIRE_SMOKE	smoke	0.7802	{"x_min": 0.4145, "y_min": 0.4135, "x_max": 0.9773, "y_max": 0.9984}	10188	11.82	2026-10-13 09:50:52.337195+00
ea91b2b9-72d9-42ab-a16b-645f3247a233	1	FIRE_SMOKE	smoke	0.7866	{"x_min": 0.4104, "y_min": 0.415, "x_max": 0.9836, "y_max": 0.9992}	10244	11.98	2026-10-13 09:50:57.090166+00
aba3216f-9243-4176-a7ff-5db4c01c6681	1	FIRE_SMOKE	smoke	0.7691	{"x_min": 0.4139, "y_min": 0.4018, "x_max": 0.9815, "y_max": 1.0}	10316	12.5	2026-10-13 09:51:03.088978+00
9f718d02-d597-41b7-8667-23f06e7f052e	1	FIRE_SMOKE	smoke	0.8133	{"x_min": 0.4151, "y_min": 0.4149, "x_max": 0.9488, "y_max": 0.9996}	10332	12.29	2026-10-13 09:51:04.34877+00
1cf264dc-9732-4b53-9c63-62f9cc5c2f48	1	FIRE_SMOKE	person	0.5252363681793213	{"x_min": 0.7966, "y_min": 0.2238, "x_max": 0.9212, "y_max": 0.6491}	10420	11.81	2026-10-13 09:51:11.737155+00
b4cf2f7a-a72d-456c-bb9b-4f9b82223525	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.8118, "y_min": 0.2488, "x_max": 0.9052, "y_max": 0.3191}	10420	11.81	2026-10-13 09:51:11.737155+00
de66ed2f-da3d-4de0-94ad-c9b0067e8ae4	1	FIRE_SMOKE	smoke	0.7914	{"x_min": 0.4092, "y_min": 0.4094, "x_max": 0.9963, "y_max": 1.0}	10492	11.93	2026-10-13 09:51:17.749311+00
c29e556c-929c-4f53-b378-1918a9ada2b1	1	FIRE_SMOKE	smoke	0.7701	{"x_min": 0.4126, "y_min": 0.4228, "x_max": 0.9831, "y_max": 1.0}	10532	15.92	2026-10-13 09:51:21.109335+00
4f584c45-6df4-4c55-a339-f1497c62ffa3	1	FIRE_SMOKE	smoke	0.7906	{"x_min": 0.4123, "y_min": 0.4193, "x_max": 0.9881, "y_max": 1.0}	10548	11.86	2026-10-13 09:51:22.337981+00
7d150e9b-4d23-432a-90e2-73839e328fd5	1	FIRE_SMOKE	smoke	0.7711	{"x_min": 0.4152, "y_min": 0.4465, "x_max": 1.0, "y_max": 1.0}	10580	12.76	2026-10-13 09:51:25.099134+00
35daf28c-a7b2-4985-bd76-197a208b3d85	1	FIRE_SMOKE	smoke	0.7858	{"x_min": 0.4115, "y_min": 0.4193, "x_max": 0.9893, "y_max": 1.0}	10664	11.73	2026-10-13 09:51:32.094917+00
552727cf-3449-4389-b720-303b312978c0	1	FIRE_SMOKE	smoke	0.7917	{"x_min": 0.4141, "y_min": 0.417, "x_max": 0.988, "y_max": 1.0}	10708	12.74	2026-10-13 09:51:35.747427+00
32aee110-2d57-450f-8908-84fcdd5870e6	1	FIRE_SMOKE	smoke	0.7662	{"x_min": 0.4135, "y_min": 0.4212, "x_max": 0.992, "y_max": 1.0}	10924	12	2026-10-13 09:51:53.750135+00
7bdec972-3dec-46b5-a09b-24690d530d8f	1	FIRE_SMOKE	smoke	0.7674	{"x_min": 0.4137, "y_min": 0.4124, "x_max": 0.988, "y_max": 1.0}	10952	11.99	2026-10-13 09:51:56.109541+00
c62e1f80-ef4f-410d-93b4-d7ad8ea8c264	1	FIRE_SMOKE	smoke	0.764	{"x_min": 0.412, "y_min": 0.4172, "x_max": 0.9671, "y_max": 1.0}	10968	12.31	2026-10-13 09:51:57.350464+00
be9e503e-cc46-470d-9c24-b478c0396811	1	FIRE_SMOKE	smoke	0.7688	{"x_min": 0.4101, "y_min": 0.413, "x_max": 0.9884, "y_max": 0.998}	11036	11.98	2026-10-13 09:52:03.106981+00
d1996539-c7ab-4ec5-aa23-65ead7b175be	1	FIRE_SMOKE	smoke	0.8074	{"x_min": 0.4109, "y_min": 0.4117, "x_max": 0.9925, "y_max": 1.0}	11092	11.24	2026-10-13 09:52:07.750553+00
e60b34cb-6b12-41df-b0be-f003fe12ab12	1	FIRE_SMOKE	smoke	0.7537	{"x_min": 0.4122, "y_min": 0.4128, "x_max": 0.9922, "y_max": 0.9988}	11108	12.6	2026-10-13 09:52:09.108275+00
7ff777b6-2208-40f7-80c7-7a68c1feaf19	1	FIRE_SMOKE	smoke	0.7622	{"x_min": 0.4131, "y_min": 0.4146, "x_max": 0.9939, "y_max": 1.0}	11164	11.83	2026-10-13 09:52:13.737986+00
89abedfc-b50d-4476-bc93-36589f99a4c9	1	FIRE_SMOKE	smoke	0.7793	{"x_min": 0.4139, "y_min": 0.4125, "x_max": 0.9854, "y_max": 0.999}	11212	11.97	2026-10-13 09:52:17.749886+00
9bd86490-64d0-4202-9c0e-61fdb0b53ced	1	FIRE_SMOKE	smoke	0.7849	{"x_min": 0.4091, "y_min": 0.4137, "x_max": 0.9858, "y_max": 1.0}	11348	13.64	2026-10-13 09:52:29.099463+00
b841778d-f374-48ca-a941-56b7a6dfd3c6	1	FIRE_SMOKE	smoke	0.749	{"x_min": 0.4155, "y_min": 0.4135, "x_max": 0.9886, "y_max": 1.0}	11432	11.99	2026-10-13 09:52:36.107164+00
8870c428-e0de-4489-a09b-3f35b5b07bf6	1	FIRE_SMOKE	smoke	0.7522	{"x_min": 0.413, "y_min": 0.4125, "x_max": 0.9825, "y_max": 1.0}	11580	12.43	2026-10-13 09:52:48.348386+00
8b754abd-4334-4535-bbf7-238984a9f716	1	FIRE_SMOKE	smoke	0.7865	{"x_min": 0.4126, "y_min": 0.4159, "x_max": 0.9956, "y_max": 0.9993}	11680	11.91	2026-10-13 09:52:56.748978+00
1d421305-d1fd-4f1a-bc6e-2b1826aa08d8	1	FIRE_SMOKE	smoke	0.7598	{"x_min": 0.4117, "y_min": 0.4164, "x_max": 0.9942, "y_max": 1.0}	11780	11.96	2026-10-13 09:53:05.108278+00
3a503847-3bf6-41be-9d21-6d79aa1f26ad	1	FIRE_SMOKE	smoke	0.756	{"x_min": 0.4099, "y_min": 0.4134, "x_max": 0.9902, "y_max": 1.0}	11972	12.86	2026-10-13 09:53:21.048042+00
8d575aca-438f-485c-ab26-27f589a94240	1	FIRE_SMOKE	smoke	0.7807	{"x_min": 0.4101, "y_min": 0.4142, "x_max": 0.9834, "y_max": 0.9998}	12200	11.83	2026-10-13 09:53:40.049001+00
885c0ac1-7e68-4893-9bac-f89f6a32e073	1	FIRE_SMOKE	smoke	0.7942	{"x_min": 0.4127, "y_min": 0.4201, "x_max": 0.9951, "y_max": 1.0}	12536	12.51	2026-10-13 09:54:08.089679+00
a86b4e2b-39c9-4e8d-85e0-092acdbb4714	1	FIRE_SMOKE	smoke	0.8124	{"x_min": 0.4131, "y_min": 0.4125, "x_max": 0.985, "y_max": 1.0}	12004	13.46	2026-10-13 09:53:23.649665+00
5cfd3025-0ee5-48cb-8503-c298d5dee039	1	FIRE_SMOKE	smoke	0.7542	{"x_min": 0.4098, "y_min": 0.4127, "x_max": 0.9945, "y_max": 0.9992}	12232	12.98	2026-10-13 09:53:42.649134+00
82ecc272-13c4-47c3-9d7e-19224d4210b1	1	FIRE_SMOKE	smoke	0.7656	{"x_min": 0.4115, "y_min": 0.4128, "x_max": 0.993, "y_max": 1.0}	12708	8.46	2026-10-13 09:54:22.308454+00
7018b1a4-8cb1-474f-a26a-b11bf9fbccd1	1	FIRE_SMOKE	smoke	0.756	{"x_min": 0.4127, "y_min": 0.4138, "x_max": 0.9892, "y_max": 1.0}	12036	11.99	2026-10-13 09:53:26.310446+00
ec84a6f0-f5c9-4fdc-b3df-b5d2f9da9abe	1	FIRE_SMOKE	smoke	0.7593	{"x_min": 0.4104, "y_min": 0.4081, "x_max": 0.9939, "y_max": 1.0}	12408	11.63	2026-10-13 09:53:57.309169+00
62ff13e1-35e8-49a5-af6c-79a3ba77ab09	1	FIRE_SMOKE	smoke	0.8095	{"x_min": 0.4121, "y_min": 0.4156, "x_max": 0.9945, "y_max": 0.9995}	12804	11.99	2026-10-13 09:54:30.31157+00
96860e42-4022-4e57-bc07-c2d1e823ecef	1	FIRE_SMOKE	smoke	0.7681	{"x_min": 0.4125, "y_min": 0.4299, "x_max": 0.9923, "y_max": 1.0}	12068	13.52	2026-10-13 09:53:29.052137+00
18a02fc5-39f2-41d7-974a-57926b2cdf40	1	FIRE_SMOKE	smoke	0.775	{"x_min": 0.4135, "y_min": 0.4172, "x_max": 0.9931, "y_max": 0.9991}	12464	11.97	2026-10-13 09:54:02.049471+00
e26c0298-f658-455f-8296-8aec752a6a73	1	FIRE_SMOKE	smoke	0.8128	{"x_min": 0.4132, "y_min": 0.4151, "x_max": 0.9992, "y_max": 0.9998}	12832	11.55	2026-10-13 09:54:32.672606+00
36f3272f-2ebb-4b18-903a-a87535d7faea	1	FIRE_SMOKE	smoke	0.7753	{"x_min": 0.4103, "y_min": 0.4071, "x_max": 0.9945, "y_max": 1.0}	12168	11.72	2026-10-13 09:53:37.307296+00
eb94185b-ddaa-48e9-8742-38024bd50a32	1	FIRE_SMOKE	smoke	0.7499	{"x_min": 0.4115, "y_min": 0.4155, "x_max": 0.9702, "y_max": 1.0}	12480	12.28	2026-10-13 09:54:03.306984+00
9b10d13d-8562-4583-bda7-724898121686	1	FIRE_SMOKE	person	0.7247527837753296	{"x_min": 0.5696, "y_min": 0.2909, "x_max": 0.5756, "y_max": 0.2984}	1356	12.99	2026-10-14 04:11:45.798339+00
e87cbd44-87c4-43d9-8093-c508b630e7f2	1	FIRE_SMOKE	person	0.6628431081771851	{"x_min": 0.473, "y_min": 0.1575, "x_max": 0.5778, "y_max": 0.4636}	2088	12.25	2026-10-14 04:12:46.754731+00
0f323f65-11ba-4b15-a929-0a0b757442fc	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4852, "y_min": 0.1755, "x_max": 0.5645, "y_max": 0.226}	2088	12.25	2026-10-14 04:12:46.754731+00
c2c4f800-aac5-461c-afbf-db60b0225801	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4852, "y_min": 0.1755, "x_max": 0.5645, "y_max": 0.226}	2112	11.96	2026-10-14 04:12:48.754675+00
303c2a5e-30e6-43e7-a1d3-0218a7f4c784	1	FIRE_SMOKE	person	0.9900000095367432	{"x_min": 0.3209, "y_min": 0.0974, "x_max": 0.4255, "y_max": 0.5409}	2152	12.76	2026-10-14 04:12:52.060771+00
0fdd951f-2c1f-4385-a342-d1250db9ba7d	1	FIRE_SMOKE	person	0.9900000095367432	{"x_min": 0.3711, "y_min": 0.0894, "x_max": 0.5026, "y_max": 0.5467}	2180	12.25	2026-10-14 04:12:54.457736+00
6db1ed84-9a0f-4cfc-b081-29b234b0de7b	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.371, "y_min": 0.1184, "x_max": 0.4637, "y_max": 0.1929}	2216	11.86	2026-10-14 04:12:57.456679+00
ac4d5185-6e11-41e8-8bc5-37f1b6a0aeca	1	FIRE_SMOKE	person	0.7654833197593689	{"x_min": 0.4791, "y_min": 0.1985, "x_max": 0.527, "y_max": 0.282}	2432	12.14	2026-10-14 04:13:15.457346+00
f8e52b13-af4f-4d7e-bc23-46fe037281ce	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4825, "y_min": 0.2061, "x_max": 0.5228, "y_max": 0.2272}	2432	12.14	2026-10-14 04:13:15.457346+00
d61967aa-ba42-4e61-a860-488980c1f8cb	1	FIRE_SMOKE	person	0.5213529467582703	{"x_min": 0.4805, "y_min": 0.1985, "x_max": 0.5272, "y_max": 0.2819}	2472	12.18	2026-10-14 04:13:18.820212+00
cb0204a3-5514-43c8-b713-e33fa066d14d	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4839, "y_min": 0.2061, "x_max": 0.5228, "y_max": 0.2272}	2472	12.18	2026-10-14 04:13:18.820212+00
31de2742-ff08-4b4e-853a-35a0979d8841	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4839, "y_min": 0.2061, "x_max": 0.5228, "y_max": 0.2272}	2508	12.2	2026-10-14 04:13:21.817153+00
1661ed91-ee6a-48c6-b6a2-c531dc7107bd	1	FIRE_SMOKE	person	0.7440841794013977	{"x_min": 0.4787, "y_min": 0.1983, "x_max": 0.5272, "y_max": 0.282}	2548	13.12	2026-10-14 04:13:25.04619+00
2b9faf17-51ef-43d9-b102-2895691a32cf	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4825, "y_min": 0.2061, "x_max": 0.5228, "y_max": 0.2272}	2548	13.12	2026-10-14 04:13:25.04619+00
c07078d9-77c8-4962-8b3a-705d9b963aa9	1	FIRE_SMOKE	person	0.6897130012512207	{"x_min": 0.4826, "y_min": 0.1987, "x_max": 0.5264, "y_max": 0.282}	2580	15.49	2026-10-14 04:13:27.817753+00
38ca7cd8-ae2f-45d8-8bba-2a687621fda0	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4879, "y_min": 0.2025, "x_max": 0.5208, "y_max": 0.2163}	2580	15.49	2026-10-14 04:13:27.817753+00
b5b31067-a1cb-4666-b8b8-f8c66683b9a5	1	FIRE_SMOKE	person	0.5766081213951111	{"x_min": 0.4834, "y_min": 0.1985, "x_max": 0.5272, "y_max": 0.282}	2620	11.9	2026-10-14 04:13:31.046623+00
fd2935d6-4f66-4a69-85e8-8681b4c75a06	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4886, "y_min": 0.2025, "x_max": 0.5215, "y_max": 0.2163}	2620	11.9	2026-10-14 04:13:31.046623+00
347fd5b6-8098-446e-82b4-c9ec4cdaf576	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4879, "y_min": 0.2025, "x_max": 0.5215, "y_max": 0.2163}	2648	12.63	2026-10-14 04:13:33.459902+00
7eff6ba3-6b1d-447f-9823-d3a35e79a202	1	FIRE_SMOKE	person	0.4468494653701782	{"x_min": 0.4773, "y_min": 0.1985, "x_max": 0.5272, "y_max": 0.2822}	2844	11.99	2026-10-14 04:13:49.816671+00
3fa8be9a-a7cf-4b29-933e-b609182d0660	1	FIRE_SMOKE	gloves	0.3916742503643036	{"x_min": 0.4775, "y_min": 0.2472, "x_max": 0.4901, "y_max": 0.2583}	2880	13.92	2026-10-14 04:13:52.816747+00
0ceaa89c-731d-4c27-9fbf-9e28405171bf	1	FIRE_SMOKE	person	0.6317811608314514	{"x_min": 0.4857, "y_min": 0.1985, "x_max": 0.5272, "y_max": 0.282}	3400	12.23	2026-10-14 04:14:36.079945+00
87ed13c0-58d0-4034-808b-1dd369787189	1	FIRE_SMOKE	person	0.5292191505432129	{"x_min": 0.4754, "y_min": 0.1988, "x_max": 0.5268, "y_max": 0.282}	3532	11.99	2026-10-14 04:14:47.089833+00
86ba15d8-3af8-42b6-9991-7cee57dff571	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4798, "y_min": 0.2061, "x_max": 0.5215, "y_max": 0.2272}	3532	11.99	2026-10-14 04:14:47.089833+00
9ec536c7-c12b-49d8-9ea6-d32f0f9e8ee5	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4798, "y_min": 0.2061, "x_max": 0.5215, "y_max": 0.2272}	3576	12.54	2026-10-14 04:14:50.816545+00
0a71900d-7714-48e3-bcde-1bfd0fc480b7	1	FIRE_SMOKE	person	0.44874849915504456	{"x_min": 0.4766, "y_min": 0.1988, "x_max": 0.5272, "y_max": 0.282}	3804	12.32	2026-10-14 04:15:09.877154+00
c084578f-a3b3-4daa-a646-650ccc385463	1	FIRE_SMOKE	smoke	0.749	{"x_min": 0.4136, "y_min": 0.4113, "x_max": 0.9702, "y_max": 1.0}	4584	12.98	2026-10-14 04:16:14.876982+00
47b9f083-98ea-427c-8d19-be0e8e2f1206	1	FIRE_SMOKE	person	0.44641411304473877	{"x_min": 0.4878, "y_min": 0.2754, "x_max": 0.578, "y_max": 0.3571}	6316	12.29	2026-10-14 04:18:39.077257+00
ac83a360-c5ac-4ab7-900b-8ce604c1ad96	1	FIRE_SMOKE	person	0.5715615749359131	{"x_min": 0.4892, "y_min": 0.2746, "x_max": 0.5776, "y_max": 0.3573}	6352	12.87	2026-10-14 04:18:42.066875+00
78ba333a-1433-4dc1-aacd-e29f622f0761	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4953, "y_min": 0.2855, "x_max": 0.5706, "y_max": 0.3143}	6352	12.87	2026-10-14 04:18:42.066875+00
70646e0f-269c-4cbd-b0b3-a6e73c8cccfa	1	FIRE_SMOKE	gloves	0.20404987037181854	{"x_min": 0.4874, "y_min": 0.2861, "x_max": 0.5577, "y_max": 0.3947}	6352	12.87	2026-10-14 04:18:42.066875+00
edf04256-ed15-453e-abd4-6b152e890305	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4953, "y_min": 0.2861, "x_max": 0.5706, "y_max": 0.3143}	6384	12.62	2026-10-14 04:18:44.836784+00
2d31a613-ce9a-4b07-ac69-8b4e27616342	1	FIRE_SMOKE	gloves	0.2037813812494278	{"x_min": 0.4874, "y_min": 0.2867, "x_max": 0.562, "y_max": 0.4092}	6384	12.62	2026-10-14 04:18:44.836784+00
7884afaf-3f4b-4f95-88d8-08600ed0b067	1	FIRE_SMOKE	person	0.49269023537635803	{"x_min": 0.4858, "y_min": 0.2746, "x_max": 0.5548, "y_max": 0.3573}	6484	11.99	2026-10-14 04:18:53.077189+00
72317b59-b6c5-4163-b9aa-5f7c5820edba	1	FIRE_SMOKE	gloves	0.2682287395000458	{"x_min": 0.4987, "y_min": 0.3089, "x_max": 0.556, "y_max": 0.3492}	6484	11.99	2026-10-14 04:18:53.077189+00
e76af5ea-d6b3-401f-ada0-7b7b0476d271	1	FIRE_SMOKE	person	0.7449339628219604	{"x_min": 0.4825, "y_min": 0.2747, "x_max": 0.5766, "y_max": 0.3573}	6524	11.96	2026-10-14 04:18:56.479514+00
5ac348ef-1174-4346-a419-fea3606709a7	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4892, "y_min": 0.2861, "x_max": 0.5685, "y_max": 0.3143}	6524	11.96	2026-10-14 04:18:56.479514+00
0fe417bf-4830-4337-9b70-d273f08539e0	1	FIRE_SMOKE	gloves	0.2229345142841339	{"x_min": 0.4867, "y_min": 0.2867, "x_max": 0.5656, "y_max": 0.3903}	6524	11.96	2026-10-14 04:18:56.479514+00
fdcd5776-919a-4bcf-b40b-827ee7eab49d	1	FIRE_SMOKE	person	0.6742486953735352	{"x_min": 0.4845, "y_min": 0.2744, "x_max": 0.5762, "y_max": 0.3571}	6552	11.87	2026-10-14 04:18:58.837463+00
23c227e6-6274-4292-9d89-17c1333b9d7f	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4913, "y_min": 0.2855, "x_max": 0.5685, "y_max": 0.3143}	6552	11.87	2026-10-14 04:18:58.837463+00
11260a62-f976-4e60-93b2-570ae48aa046	1	FIRE_SMOKE	gloves	0.2624603807926178	{"x_min": 0.4872, "y_min": 0.2881, "x_max": 0.5591, "y_max": 0.4041}	6552	11.87	2026-10-14 04:18:58.837463+00
4a96f38c-cc4c-40f6-b2e3-9a2b6bebd288	1	FIRE_SMOKE	person	0.7942720651626587	{"x_min": 0.489, "y_min": 0.2746, "x_max": 0.5764, "y_max": 0.3573}	6624	12.74	2026-10-14 04:19:04.841834+00
f6298a5b-6cd8-4a1f-b0b6-e90ac8158219	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4953, "y_min": 0.2855, "x_max": 0.5692, "y_max": 0.3143}	6624	12.74	2026-10-14 04:19:04.841834+00
8857bce8-cfe3-4d77-8bdb-8f8517367c6d	1	FIRE_SMOKE	gloves	0.3189447522163391	{"x_min": 0.4912, "y_min": 0.2861, "x_max": 0.5699, "y_max": 0.3801}	6624	12.74	2026-10-14 04:19:04.841834+00
f666ec5a-9d46-496e-9ca9-c4180bab8746	1	FIRE_SMOKE	person	0.7068674564361572	{"x_min": 0.4837, "y_min": 0.2744, "x_max": 0.5736, "y_max": 0.3573}	6880	12.49	2026-10-14 04:19:26.079279+00
36c2074b-4320-456d-aa3e-e687a9ee4f53	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4906, "y_min": 0.2855, "x_max": 0.5659, "y_max": 0.3143}	6880	12.49	2026-10-14 04:19:26.079279+00
31bb4a85-9d31-4908-98bb-60837cdf4495	1	FIRE_SMOKE	person	0.7216222286224365	{"x_min": 0.4837, "y_min": 0.2742, "x_max": 0.5685, "y_max": 0.3569}	7012	11.67	2026-10-14 04:19:37.078622+00
92edef87-6e40-4f4f-a5c6-3bb509d7bfa5	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4899, "y_min": 0.2855, "x_max": 0.5618, "y_max": 0.3137}	7012	11.67	2026-10-14 04:19:37.078622+00
94e565df-5a45-4aae-b4a9-0106ae3d2970	1	FIRE_SMOKE	person	0.6102344989776611	{"x_min": 0.4856, "y_min": 0.2746, "x_max": 0.5764, "y_max": 0.3569}	7096	12.2	2026-10-14 04:19:44.078359+00
58621c61-7c66-4d26-bd37-1f43abf94642	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4926, "y_min": 0.2855, "x_max": 0.5685, "y_max": 0.3137}	7096	12.2	2026-10-14 04:19:44.078359+00
32c1f2de-30e9-48cf-bf04-5848d4bef542	1	FIRE_SMOKE	gloves	0.2177884876728058	{"x_min": 0.4858, "y_min": 0.2861, "x_max": 0.5589, "y_max": 0.4021}	7096	12.2	2026-10-14 04:19:44.078359+00
fa45d0d4-88ca-4420-b75b-af42c8153889	1	FIRE_SMOKE	person	0.4699401259422302	{"x_min": 0.4886, "y_min": 0.2747, "x_max": 0.5611, "y_max": 0.3573}	7152	11.79	2026-10-14 04:19:48.83786+00
76ff18cf-626a-45f6-b633-5743dd5ab680	1	FIRE_SMOKE	person	0.4664563238620758	{"x_min": 0.4931, "y_min": 0.2754, "x_max": 0.577, "y_max": 0.3569}	7308	12	2026-10-14 04:20:01.862848+00
9251281c-4e32-46c8-b13f-5b81f79d78a6	1	FIRE_SMOKE	gloves	0.24470092356204987	{"x_min": 0.4901, "y_min": 0.2876, "x_max": 0.5631, "y_max": 0.4005}	7308	12	2026-10-14 04:20:01.862848+00
ba2a0a00-2d09-4847-b03e-dc0805277cc4	1	FIRE_SMOKE	person	0.5369065999984741	{"x_min": 0.4907, "y_min": 0.2746, "x_max": 0.575, "y_max": 0.3571}	7416	12.51	2026-10-14 04:20:10.857261+00
333cecad-808c-4797-9785-525c8147c011	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4973, "y_min": 0.2855, "x_max": 0.5679, "y_max": 0.3143}	7416	12.51	2026-10-14 04:20:10.857261+00
12276f29-eb83-4359-bade-d657abd1ce59	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.494, "y_min": 0.2819, "x_max": 0.5565, "y_max": 0.3023}	7488	12.45	2026-10-14 04:20:16.858604+00
f78457a6-ed83-4b75-9b69-05a33bbac231	1	FIRE_SMOKE	person	0.6048843860626221	{"x_min": 0.4868, "y_min": 0.2744, "x_max": 0.5774, "y_max": 0.3573}	7520	12.49	2026-10-14 04:20:19.500106+00
6c4fabb5-948b-4420-be29-8dcf147af258	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.494, "y_min": 0.2855, "x_max": 0.5699, "y_max": 0.3143}	7520	12.49	2026-10-14 04:20:19.500106+00
37c2eac2-84c9-482e-a65e-004ef19fa984	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4933, "y_min": 0.2855, "x_max": 0.5685, "y_max": 0.3143}	7632	12.84	2026-10-14 04:20:28.860419+00
426864dc-bc01-404e-a9b4-ff5255a84198	1	FIRE_SMOKE	gloves	0.2756127119064331	{"x_min": 0.5326, "y_min": 0.2861, "x_max": 0.5773, "y_max": 0.3132}	7632	12.84	2026-10-14 04:20:28.860419+00
67246f70-96ba-434b-89e5-6cbb7f6fabd1	1	FIRE_SMOKE	person	0.6808933019638062	{"x_min": 0.4876, "y_min": 0.2746, "x_max": 0.5625, "y_max": 0.3573}	7800	11.83	2026-10-14 04:20:42.878058+00
50c9fcc3-e0af-475e-822f-3b04d819c16c	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4946, "y_min": 0.2819, "x_max": 0.5544, "y_max": 0.3023}	7800	11.83	2026-10-14 04:20:42.878058+00
6c1bddbb-46ca-4aaa-86c6-2f18eefdf36c	1	FIRE_SMOKE	gloves	0.20132866501808167	{"x_min": 0.4865, "y_min": 0.2861, "x_max": 0.5292, "y_max": 0.3373}	7800	11.83	2026-10-14 04:20:42.878058+00
16c9aadc-ddd1-4939-afc9-5015b9d6c078	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4926, "y_min": 0.2861, "x_max": 0.5659, "y_max": 0.3143}	7932	12	2026-10-14 04:20:53.901112+00
9362b724-c6e0-43b2-9d85-cc3af74fce9f	1	FIRE_SMOKE	person	0.61565101146698	{"x_min": 0.4892, "y_min": 0.2744, "x_max": 0.5774, "y_max": 0.3575}	8032	11.9	2026-10-14 04:21:02.202014+00
82ebebe3-a5ac-4b77-87b5-99373eecf717	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4953, "y_min": 0.2855, "x_max": 0.5706, "y_max": 0.3143}	8032	11.9	2026-10-14 04:21:02.202014+00
ee12427f-8eda-4252-a472-f51523e3e85d	1	FIRE_SMOKE	gloves	0.22665686905384064	{"x_min": 0.4874, "y_min": 0.2872, "x_max": 0.5577, "y_max": 0.3985}	8032	11.9	2026-10-14 04:21:02.202014+00
efb149df-3a0b-4ab8-9e5f-0c326ba32567	1	FIRE_SMOKE	person	0.5208706855773926	{"x_min": 0.485, "y_min": 0.2746, "x_max": 0.5568, "y_max": 0.3573}	8112	11.89	2026-10-14 04:21:08.997621+00
f053b84e-aa94-4b63-8c0c-e5b61a756695	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4913, "y_min": 0.2819, "x_max": 0.5497, "y_max": 0.3023}	8112	11.89	2026-10-14 04:21:08.997621+00
f6ec019c-3943-4189-b88d-c59768582521	1	FIRE_SMOKE	gloves	0.3321438729763031	{"x_min": 0.5502, "y_min": 0.3159, "x_max": 0.5592, "y_max": 0.3231}	8112	11.89	2026-10-14 04:21:08.997621+00
58f23899-dc0c-401f-8d6f-8fde6c05bb14	1	FIRE_SMOKE	person	0.604672908782959	{"x_min": 0.4874, "y_min": 0.2746, "x_max": 0.5754, "y_max": 0.3573}	8204	12.47	2026-10-14 04:21:16.6974+00
350d47bd-a698-4733-b415-9e395bf91132	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.494, "y_min": 0.2855, "x_max": 0.5685, "y_max": 0.3143}	8204	12.47	2026-10-14 04:21:16.6974+00
3d46fca9-54a9-4dc5-8c44-f26b3a67e949	1	FIRE_SMOKE	gloves	0.30507317185401917	{"x_min": 0.5506, "y_min": 0.335, "x_max": 0.5713, "y_max": 0.3573}	8204	12.47	2026-10-14 04:21:16.6974+00
53af35dc-f7e9-4aae-aeff-f2acc5080081	1	FIRE_SMOKE	person	0.6490065455436707	{"x_min": 0.4843, "y_min": 0.2747, "x_max": 0.5772, "y_max": 0.3573}	8288	11.87	2026-10-14 04:21:23.697944+00
89a5550e-1ea0-46d3-a995-90b7257f9ac5	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4913, "y_min": 0.2861, "x_max": 0.5692, "y_max": 0.3143}	8288	11.87	2026-10-14 04:21:23.697944+00
d23e402f-cd19-4063-a97a-a7d5390eceeb	1	FIRE_SMOKE	person	0.6193122863769531	{"x_min": 0.4894, "y_min": 0.2747, "x_max": 0.5776, "y_max": 0.3575}	6592	11.9	2026-10-14 04:19:02.07866+00
6e5f0dec-eec4-49f4-9eda-0dbe03d33b98	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.496, "y_min": 0.2861, "x_max": 0.5706, "y_max": 0.3143}	6592	11.9	2026-10-14 04:19:02.07866+00
0a46aa69-3628-4e9a-85ca-a216d5aab316	1	FIRE_SMOKE	gloves	0.3297276496887207	{"x_min": 0.4872, "y_min": 0.287, "x_max": 0.557, "y_max": 0.3957}	6592	11.9	2026-10-14 04:19:02.07866+00
fd57a5a2-6230-4d4d-9972-c99a88b19dd7	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4953, "y_min": 0.2855, "x_max": 0.5692, "y_max": 0.3143}	6672	11.74	2026-10-14 04:19:08.837942+00
d6bb180f-b592-4853-ab6b-82a3a4c4e912	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4906, "y_min": 0.2855, "x_max": 0.5659, "y_max": 0.3143}	6908	12.81	2026-10-14 04:19:28.47925+00
729489f8-2e8e-4b18-bdf3-3b554a5d8694	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4899, "y_min": 0.2855, "x_max": 0.5618, "y_max": 0.3137}	7056	12.01	2026-10-14 04:19:40.83758+00
3d6b0a87-9f37-43ce-8ee8-de2c21444c65	1	FIRE_SMOKE	person	0.6279864311218262	{"x_min": 0.4833, "y_min": 0.2746, "x_max": 0.5627, "y_max": 0.3575}	7128	16.54	2026-10-14 04:19:46.836966+00
b88e6957-f815-463d-aec0-095fe9a11357	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4906, "y_min": 0.2819, "x_max": 0.5551, "y_max": 0.3023}	7128	16.54	2026-10-14 04:19:46.836966+00
106a43d2-886d-4098-a095-10b10409e3ed	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.494, "y_min": 0.2825, "x_max": 0.5551, "y_max": 0.3029}	7200	12.75	2026-10-14 04:19:52.840112+00
eb2bb9b0-ce12-4b6c-a029-f19c6b2ecdc5	1	FIRE_SMOKE	person	0.6002811193466187	{"x_min": 0.4864, "y_min": 0.2746, "x_max": 0.577, "y_max": 0.3571}	7380	12.87	2026-10-14 04:20:07.861477+00
8fc7b092-8ddb-48a3-8019-faa38b2ef8ac	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4933, "y_min": 0.2855, "x_max": 0.5692, "y_max": 0.3143}	7380	12.87	2026-10-14 04:20:07.861477+00
353c15a5-6c97-4060-b3a0-2da2502c5125	1	FIRE_SMOKE	gloves	0.30081361532211304	{"x_min": 0.4887, "y_min": 0.2865, "x_max": 0.5636, "y_max": 0.391}	7380	12.87	2026-10-14 04:20:07.861477+00
688f47ac-660a-46c4-b255-c5dfdb26b0ac	1	FIRE_SMOKE	person	0.5336952805519104	{"x_min": 0.4862, "y_min": 0.2744, "x_max": 0.5589, "y_max": 0.3573}	7448	16.24	2026-10-14 04:20:13.499475+00
61e4fd89-7b43-4bf2-8f1a-6078c14422ac	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4926, "y_min": 0.2819, "x_max": 0.5517, "y_max": 0.3023}	7448	16.24	2026-10-14 04:20:13.499475+00
40d27372-5aa2-471f-a181-0135af1db69c	1	FIRE_SMOKE	gloves	0.2247270792722702	{"x_min": 0.4926, "y_min": 0.3023, "x_max": 0.5518, "y_max": 0.3454}	7448	16.24	2026-10-14 04:20:13.499475+00
5e417f04-7f12-4a33-aecd-e43c9b60c13f	1	FIRE_SMOKE	person	0.5725767612457275	{"x_min": 0.487, "y_min": 0.2744, "x_max": 0.5748, "y_max": 0.3573}	7584	12	2026-10-14 04:20:24.858904+00
8036109b-8638-48f5-a804-63ec52af9488	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4933, "y_min": 0.2855, "x_max": 0.5679, "y_max": 0.3143}	7584	12	2026-10-14 04:20:24.858904+00
74ccae25-fdbe-4bc4-b409-4550fd5dbe02	1	FIRE_SMOKE	person	0.7140729427337646	{"x_min": 0.4866, "y_min": 0.2749, "x_max": 0.5766, "y_max": 0.3569}	7744	11.84	2026-10-14 04:20:38.098671+00
85bccbd1-8291-49b6-b787-fba51d26c83b	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4933, "y_min": 0.2861, "x_max": 0.5692, "y_max": 0.3137}	7744	11.84	2026-10-14 04:20:38.098671+00
f6005c16-7123-49c1-871d-42eebc5ce457	1	FIRE_SMOKE	gloves	0.2129935622215271	{"x_min": 0.4849, "y_min": 0.2867, "x_max": 0.5561, "y_max": 0.3921}	7744	11.84	2026-10-14 04:20:38.098671+00
06842806-b9bb-41cf-9fc2-0c9895ffbbe3	1	FIRE_SMOKE	person	0.5642518401145935	{"x_min": 0.4856, "y_min": 0.2747, "x_max": 0.576, "y_max": 0.3573}	7876	12.79	2026-10-14 04:20:49.101401+00
69e9d9bf-9a09-4cf5-b25e-5284c59069fc	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4926, "y_min": 0.2861, "x_max": 0.5685, "y_max": 0.3143}	7876	12.79	2026-10-14 04:20:49.101401+00
397cd444-3ac0-442a-8f1f-d63382e6778e	1	FIRE_SMOKE	gloves	0.2448301613330841	{"x_min": 0.4912, "y_min": 0.2886, "x_max": 0.5709, "y_max": 0.4087}	7876	12.79	2026-10-14 04:20:49.101401+00
a3093477-27da-4854-b231-a1e7607351c1	1	FIRE_SMOKE	person	0.5579845309257507	{"x_min": 0.4825, "y_min": 0.2744, "x_max": 0.5752, "y_max": 0.3571}	8000	12.35	2026-10-14 04:20:59.604157+00
3e27e29b-b742-4d4f-9cca-4ee2255be6cb	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4892, "y_min": 0.2855, "x_max": 0.5672, "y_max": 0.3143}	8000	12.35	2026-10-14 04:20:59.604157+00
70a732ab-8b8b-45c3-ae3e-d3558aa40e0a	1	FIRE_SMOKE	gloves	0.2049281895160675	{"x_min": 0.4844, "y_min": 0.2861, "x_max": 0.5567, "y_max": 0.4073}	8000	12.35	2026-10-14 04:20:59.604157+00
a8487270-e7ee-4f60-a773-c88897cd4617	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.494, "y_min": 0.2855, "x_max": 0.5692, "y_max": 0.3143}	8072	12.45	2026-10-14 04:21:05.605086+00
2427420e-0cdb-406a-941f-55b899ce751e	1	FIRE_SMOKE	gloves	0.21454890072345734	{"x_min": 0.4872, "y_min": 0.2865, "x_max": 0.5628, "y_max": 0.3982}	8072	12.45	2026-10-14 04:21:05.605086+00
4db714ad-2ed3-407a-8dc2-52c0585329de	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4913, "y_min": 0.2819, "x_max": 0.5497, "y_max": 0.3023}	8176	11.87	2026-10-14 04:21:14.297559+00
f4eb1647-1c84-4c33-9451-5127b7211d6a	1	FIRE_SMOKE	gloves	0.2611764967441559	{"x_min": 0.5528, "y_min": 0.3367, "x_max": 0.5592, "y_max": 0.3495}	8176	11.87	2026-10-14 04:21:14.297559+00
8e1fe33a-86d2-4677-9965-561215342baa	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.494, "y_min": 0.2855, "x_max": 0.5685, "y_max": 0.3143}	8248	12.16	2026-10-14 04:21:20.298997+00
b819dda8-02c5-49cc-94b4-0d410fa5b634	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4913, "y_min": 0.2861, "x_max": 0.5692, "y_max": 0.3143}	8336	11.99	2026-10-14 04:21:27.700917+00
f030688f-0d33-439d-b87e-afe8b357a985	1	FIRE_SMOKE	person	0.687434196472168	{"x_min": 0.4888, "y_min": 0.2746, "x_max": 0.5772, "y_max": 0.3573}	8512	11.98	2026-10-14 04:21:42.298021+00
9134d27c-d34d-4de8-adc1-9b6b5ccd694b	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4953, "y_min": 0.2855, "x_max": 0.5699, "y_max": 0.3143}	8512	11.98	2026-10-14 04:21:42.298021+00
e8ea42f1-ac68-4631-80a8-aa972d55ebd2	1	FIRE_SMOKE	gloves	0.20321674644947052	{"x_min": 0.4878, "y_min": 0.2864, "x_max": 0.5593, "y_max": 0.4097}	8512	11.98	2026-10-14 04:21:42.298021+00
ed4b25f4-54e1-4999-826f-90c1f40d9d5c	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4953, "y_min": 0.2855, "x_max": 0.5699, "y_max": 0.3143}	8564	11.82	2026-10-14 04:21:46.698527+00
2feaa035-1640-48c6-bdbb-0b56b7bc76aa	1	FIRE_SMOKE	person	0.5691518187522888	{"x_min": 0.4827, "y_min": 0.2746, "x_max": 0.5672, "y_max": 0.3571}	8668	14.95	2026-10-14 04:21:55.304134+00
271bdcd5-536c-46e8-bcae-be1bb005d7a2	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4892, "y_min": 0.2855, "x_max": 0.5598, "y_max": 0.3143}	8668	14.95	2026-10-14 04:21:55.304134+00
3720ebbf-b6db-4ba3-a998-06b05deb41f4	1	FIRE_SMOKE	gloves	0.454659104347229	{"x_min": 0.532, "y_min": 0.2861, "x_max": 0.5695, "y_max": 0.3122}	8668	14.95	2026-10-14 04:21:55.304134+00
4528e2dd-a88d-467a-a949-1a18ae085edd	1	FIRE_SMOKE	gloves	0.3103826940059662	{"x_min": 0.5517, "y_min": 0.3355, "x_max": 0.5699, "y_max": 0.358}	8668	14.95	2026-10-14 04:21:55.304134+00
8120585c-22d8-4e9b-8950-a8670cb879ac	1	FIRE_SMOKE	person	0.5297631621360779	{"x_min": 0.4829, "y_min": 0.2744, "x_max": 0.5537, "y_max": 0.3573}	8744	11.95	2026-10-14 04:22:01.700057+00
365d3222-cf4c-4a23-8515-0dc60190e17d	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4892, "y_min": 0.2819, "x_max": 0.5464, "y_max": 0.3023}	8744	11.95	2026-10-14 04:22:01.700057+00
9b31dc36-3279-4e15-9eee-327f3a167974	1	FIRE_SMOKE	gloves	0.21994125843048096	{"x_min": 0.4886, "y_min": 0.2916, "x_max": 0.5388, "y_max": 0.3414}	8744	11.95	2026-10-14 04:22:01.700057+00
667dd829-d62c-4a0c-a15b-f3f0dc317fd3	1	FIRE_SMOKE	person	0.7594766020774841	{"x_min": 0.4862, "y_min": 0.2747, "x_max": 0.5764, "y_max": 0.3573}	8944	12.01	2026-10-14 04:22:18.399046+00
26b03ce9-454f-4324-a6c2-9de9a36a1c61	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4933, "y_min": 0.2861, "x_max": 0.5685, "y_max": 0.3143}	8944	12.01	2026-10-14 04:22:18.399046+00
dfd5582a-d4d6-4957-99e3-9707b1cec2bc	1	FIRE_SMOKE	gloves	0.2061065286397934	{"x_min": 0.4944, "y_min": 0.307, "x_max": 0.5611, "y_max": 0.4187}	10240	12.12	2026-10-14 04:24:06.301797+00
50a86c30-d042-4e90-848e-27bd06502d5c	1	FIRE_SMOKE	gloves	0.20512905716896057	{"x_min": 0.4937, "y_min": 0.331, "x_max": 0.5006, "y_max": 0.337}	10328	11.85	2026-10-14 04:24:13.72658+00
abfe0804-75ce-44af-bc99-d6a25954da9d	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.498, "y_min": 0.3059, "x_max": 0.5726, "y_max": 0.3335}	10552	15.45	2026-10-14 04:24:32.30511+00
e1247de1-6538-411d-88af-1e7b2824454f	1	FIRE_SMOKE	gloves	0.2539020776748657	{"x_min": 0.4913, "y_min": 0.3065, "x_max": 0.5516, "y_max": 0.3824}	10552	15.45	2026-10-14 04:24:32.30511+00
784cdefa-62c4-40b2-9568-09e0cec53b98	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4926, "y_min": 0.1917, "x_max": 0.5793, "y_max": 0.2416}	11492	13.82	2026-10-14 04:25:50.723134+00
a53266a2-df74-44db-bf09-ec06a5cd1586	1	FIRE_SMOKE	smoke	0.78	{"x_min": 0.4099, "y_min": 0.4126, "x_max": 0.9696, "y_max": 1.0}	11492	13.82	2026-10-14 04:25:50.723134+00
beb33b28-8869-4c37-956a-2b306fa392a3	1	FIRE_SMOKE	smoke	0.7814	{"x_min": 0.4151, "y_min": 0.4126, "x_max": 0.9749, "y_max": 0.9995}	12516	11.86	2026-10-14 04:27:16.021855+00
2920459a-4c9f-49fe-af80-25ad9c6b44a4	1	FIRE_SMOKE	smoke	0.7659	{"x_min": 0.4139, "y_min": 0.4123, "x_max": 0.9731, "y_max": 1.0}	12760	11.89	2026-10-14 04:27:36.32221+00
9c035b2c-28a0-40e1-81b8-cd95899cc26e	1	FIRE_SMOKE	smoke	0.7519	{"x_min": 0.4157, "y_min": 0.4121, "x_max": 0.9599, "y_max": 1.0}	12924	11.89	2026-10-14 04:27:50.033848+00
0741802d-6c7e-47e3-a590-cb23e58b5561	1	FIRE_SMOKE	person	0.49129465222358704	{"x_min": 0.573, "y_min": 0.2572, "x_max": 0.5968, "y_max": 0.2997}	13336	11.81	2026-10-14 04:28:24.321606+00
b0d92e6c-4081-4963-9393-e81e3d8fa069	1	FIRE_SMOKE	person	0.4435114562511444	{"x_min": 0.497, "y_min": 0.232, "x_max": 0.6029, "y_max": 0.3174}	13804	11.83	2026-10-14 04:29:03.313843+00
2b5c4b23-c188-403e-bac8-e6648edb9d27	1	FIRE_SMOKE	person	0.5441039204597473	{"x_min": 0.497, "y_min": 0.232, "x_max": 0.5963, "y_max": 0.3575}	13960	12.35	2026-10-14 04:29:16.320775+00
cc977bf6-63a6-4e97-9813-fcfabe8ae891	1	FIRE_SMOKE	person	0.6695467829704285	{"x_min": 0.4961, "y_min": 0.2322, "x_max": 0.6127, "y_max": 0.357}	14044	11.82	2026-10-14 04:29:23.323257+00
7c2d28df-b946-4a80-94cd-b168119093ba	1	FIRE_SMOKE	person	0.44800645112991333	{"x_min": 0.491, "y_min": 0.232, "x_max": 0.6043, "y_max": 0.3575}	14272	11.88	2026-10-14 04:29:42.218617+00
f15ea6e1-f98a-4817-8e5b-dd8bf93a1ef2	1	FIRE_SMOKE	person	0.6036772727966309	{"x_min": 0.4956, "y_min": 0.232, "x_max": 0.5952, "y_max": 0.3326}	14380	11.98	2026-10-14 04:29:51.219106+00
e977c135-8228-4e75-8fd2-a68a34fa33a3	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4933, "y_min": 0.2915, "x_max": 0.5672, "y_max": 0.3149}	16196	12.88	2026-10-14 04:32:22.844129+00
a5661207-6cee-49d1-9db6-a1bedfe9f5f6	1	FIRE_SMOKE	gloves	0.27793437242507935	{"x_min": 0.4888, "y_min": 0.2971, "x_max": 0.5744, "y_max": 0.4259}	16196	12.88	2026-10-14 04:32:22.844129+00
9c9f4fb7-f405-412c-a81a-83089b7df300	1	FIRE_SMOKE	person	0.7133926153182983	{"x_min": 0.4822, "y_min": 0.283, "x_max": 0.5895, "y_max": 0.376}	16280	12.49	2026-10-14 04:32:29.842357+00
e5465e01-221e-43b3-827b-8d2ad2fdc966	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4906, "y_min": 0.2951, "x_max": 0.5806, "y_max": 0.3269}	16280	12.49	2026-10-14 04:32:29.842357+00
979ffeab-ec26-44f8-993c-20e09910fcb2	1	FIRE_SMOKE	gloves	0.24877791106700897	{"x_min": 0.4873, "y_min": 0.2963, "x_max": 0.5661, "y_max": 0.4156}	16280	12.49	2026-10-14 04:32:29.842357+00
54eee392-403b-42f5-a349-947cebce2225	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4913, "y_min": 0.2951, "x_max": 0.5853, "y_max": 0.3269}	16352	11.99	2026-10-14 04:32:35.844017+00
1365cff1-93ef-47f4-9330-c158854103b2	1	FIRE_SMOKE	gloves	0.3170745074748993	{"x_min": 0.4894, "y_min": 0.2963, "x_max": 0.5693, "y_max": 0.4251}	16352	11.99	2026-10-14 04:32:35.844017+00
39814085-8d4b-4728-8db9-81ee638b9e3d	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4892, "y_min": 0.2951, "x_max": 0.5692, "y_max": 0.3263}	16420	12.81	2026-10-14 04:32:41.440671+00
d83686ae-a515-4be8-a927-e9d5801bb3eb	1	FIRE_SMOKE	person	0.9256737232208252	{"x_min": 0.4844, "y_min": 0.283, "x_max": 0.5741, "y_max": 0.3671}	16544	12.95	2026-10-14 04:32:51.840828+00
6f46ea2c-7e95-4213-86fb-00563ff6ff99	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4913, "y_min": 0.2939, "x_max": 0.5665, "y_max": 0.3227}	16544	12.95	2026-10-14 04:32:51.840828+00
5cf13de2-7110-4754-b278-7a7dc4b97901	1	FIRE_SMOKE	gloves	0.25396206974983215	{"x_min": 0.4919, "y_min": 0.2955, "x_max": 0.5733, "y_max": 0.4119}	16544	12.95	2026-10-14 04:32:51.840828+00
cdd96200-d011-4eba-ae9b-089a6f506349	1	FIRE_SMOKE	person	0.8923229575157166	{"x_min": 0.4835, "y_min": 0.283, "x_max": 0.5765, "y_max": 0.376}	16664	11.84	2026-10-14 04:33:01.919287+00
55686f22-e8ef-4d41-a722-4112db5b596c	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4919, "y_min": 0.2915, "x_max": 0.5672, "y_max": 0.3149}	16664	11.84	2026-10-14 04:33:01.919287+00
3db2c991-56c8-4827-acb6-04c789cf9945	1	FIRE_SMOKE	gloves	0.2825320065021515	{"x_min": 0.4898, "y_min": 0.2967, "x_max": 0.5761, "y_max": 0.4337}	16664	11.84	2026-10-14 04:33:01.919287+00
ca22f824-fa2a-4da8-88a8-a50034057fa1	1	FIRE_SMOKE	person	0.473609060049057	{"x_min": 0.4815, "y_min": 0.2829, "x_max": 0.5754, "y_max": 0.3762}	16784	12.94	2026-10-14 04:33:12.001891+00
e1e269e0-d106-4762-bcb1-db2268b3ff48	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4906, "y_min": 0.2951, "x_max": 0.5726, "y_max": 0.3275}	16896	11.96	2026-10-14 04:33:21.236858+00
e72324b5-4c24-4106-b94f-36c41d8df07b	1	FIRE_SMOKE	person	0.5445955991744995	{"x_min": 0.4968, "y_min": 0.2942, "x_max": 0.586, "y_max": 0.3768}	17188	11.96	2026-10-14 04:33:46.241738+00
7ca0c537-b62c-4f75-a5ac-f01ec550b89c	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.5034, "y_min": 0.3053, "x_max": 0.5793, "y_max": 0.3335}	17188	11.96	2026-10-14 04:33:46.241738+00
6d32d787-b911-4259-9aca-b9eb028825c4	1	FIRE_SMOKE	gloves	0.2568511962890625	{"x_min": 0.4933, "y_min": 0.3059, "x_max": 0.5662, "y_max": 0.3977}	17188	11.96	2026-10-14 04:33:46.241738+00
da292372-7912-474e-8558-f5a7fcabfefc	1	FIRE_SMOKE	person	0.4682951271533966	{"x_min": 0.4966, "y_min": 0.2947, "x_max": 0.5845, "y_max": 0.3766}	17408	12.26	2026-10-14 04:34:04.86152+00
affca0d3-0a8b-4bc4-890c-f9ce76df83f5	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4899, "y_min": 0.2819, "x_max": 0.5497, "y_max": 0.3023}	8788	11.84	2026-10-14 04:22:05.400019+00
1e8ee8bd-81b0-4f0e-b74d-e97f2a084df3	1	FIRE_SMOKE	gloves	0.27005597949028015	{"x_min": 0.5524, "y_min": 0.3364, "x_max": 0.5598, "y_max": 0.3495}	8788	11.84	2026-10-14 04:22:05.400019+00
cce01e98-96fd-42ca-96ac-899b668b2221	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4933, "y_min": 0.2861, "x_max": 0.5685, "y_max": 0.3143}	9000	11.86	2026-10-14 04:22:23.050021+00
7b012e73-ae4a-43cb-89e0-645e325f6535	1	FIRE_SMOKE	person	0.44722500443458557	{"x_min": 0.4916, "y_min": 0.2944, "x_max": 0.5796, "y_max": 0.377}	10196	11.6	2026-10-14 04:24:02.724058+00
9345a2c1-140b-47a2-8b04-256c7fdd30e6	1	FIRE_SMOKE	person	0.5467188358306885	{"x_min": 0.4918, "y_min": 0.2944, "x_max": 0.5249, "y_max": 0.377}	10292	12.16	2026-10-14 04:24:10.710931+00
0e8910ba-1f8e-4182-ab0a-318eaa4d9a36	1	FIRE_SMOKE	person	0.5337965488433838	{"x_min": 0.4916, "y_min": 0.2947, "x_max": 0.5798, "y_max": 0.3768}	10516	11.8	2026-10-14 04:24:29.303005+00
c4bc1bb2-f169-4e14-b30f-8dcd8183a143	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.498, "y_min": 0.3059, "x_max": 0.5726, "y_max": 0.3335}	10516	11.8	2026-10-14 04:24:29.303005+00
1c7a08b4-5456-45a1-baee-4b9bec1e5c95	1	FIRE_SMOKE	person	0.6559664011001587	{"x_min": 0.4785, "y_min": 0.1737, "x_max": 0.5934, "y_max": 0.4772}	11456	11.84	2026-10-14 04:25:47.721783+00
557a534a-906a-4a58-8d0d-7b262cf7246a	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4926, "y_min": 0.1917, "x_max": 0.5793, "y_max": 0.2416}	11456	11.84	2026-10-14 04:25:47.721783+00
723950bf-aa6b-4136-be69-bf1a72e10b4a	1	FIRE_SMOKE	person	0.9900000095367432	{"x_min": 0.3503, "y_min": 0.094, "x_max": 0.4784, "y_max": 0.6487}	11532	11.85	2026-10-14 04:25:54.001016+00
30c049cc-6347-4862-a8bb-8c2ae6e41898	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.3663, "y_min": 0.1262, "x_max": 0.4617, "y_max": 0.2181}	11532	11.85	2026-10-14 04:25:54.001016+00
aede4db0-dea4-4a6d-9466-cdecb8700ee1	1	FIRE_SMOKE	smoke	0.7665	{"x_min": 0.4136, "y_min": 0.4134, "x_max": 0.9803, "y_max": 1.0}	12864	12.3	2026-10-14 04:27:45.022397+00
0e6772ea-af33-4a25-8980-974f36034f3e	1	FIRE_SMOKE	person	0.4931396245956421	{"x_min": 0.5004, "y_min": 0.274, "x_max": 0.5603, "y_max": 0.3525}	13088	11.92	2026-10-14 04:28:03.726661+00
fe89dcd2-bdad-401f-ae6e-a7eb8019b7d1	1	FIRE_SMOKE	smoke	0.7591	{"x_min": 0.411, "y_min": 0.4134, "x_max": 0.9858, "y_max": 1.0}	13760	11.86	2026-10-14 04:28:59.742871+00
61872b37-c1cf-4a74-b6c3-97640cb6f8dc	1	FIRE_SMOKE	person	0.6393910050392151	{"x_min": 0.4961, "y_min": 0.232, "x_max": 0.6124, "y_max": 0.3575}	13920	11.95	2026-10-14 04:29:13.026035+00
1de98c67-d822-45fa-afdc-73662e05e662	1	FIRE_SMOKE	person	0.5011404752731323	{"x_min": 0.4961, "y_min": 0.232, "x_max": 0.5954, "y_max": 0.3559}	14008	12.82	2026-10-14 04:29:20.32215+00
07fd35a3-980e-4da4-8fd4-e9b414c5736d	1	FIRE_SMOKE	person	0.6855645775794983	{"x_min": 0.4904, "y_min": 0.232, "x_max": 0.6081, "y_max": 0.3554}	14092	11.86	2026-10-14 04:29:27.322157+00
feec7b8e-95b9-4e98-beb4-c70042ba70a4	1	FIRE_SMOKE	goggles	0.8463670611381531	{"x_min": 0.5228, "y_min": 0.2916, "x_max": 0.5814, "y_max": 0.3151}	14092	11.86	2026-10-14 04:29:27.322157+00
5d59b081-15ba-4099-9bfc-1a27dc5111e1	1	FIRE_SMOKE	person	0.7691163420677185	{"x_min": 0.4941, "y_min": 0.232, "x_max": 0.6, "y_max": 0.3572}	14128	8.98	2026-10-14 04:29:30.625264+00
a5fddbf6-46d0-43cb-bfa2-f0dd2692cd51	1	FIRE_SMOKE	goggles	0.8463670611381531	{"x_min": 0.5233, "y_min": 0.2924, "x_max": 0.576, "y_max": 0.3163}	14128	8.98	2026-10-14 04:29:30.625264+00
262d008d-4f02-45b2-8778-a392fa79cfd0	1	FIRE_SMOKE	person	0.48228901624679565	{"x_min": 0.4964, "y_min": 0.232, "x_max": 0.5997, "y_max": 0.3339}	14344	11.83	2026-10-14 04:29:48.218827+00
114ec54f-28ca-4018-953f-7eaf8bad13f3	1	FIRE_SMOKE	person	0.549920380115509	{"x_min": 0.4933, "y_min": 0.232, "x_max": 0.6098, "y_max": 0.3536}	14500	12.79	2026-10-14 04:30:01.220685+00
d6e70f88-128f-4747-92c7-e28cfa89ce6a	1	FIRE_SMOKE	person	0.636132001876831	{"x_min": 0.4846, "y_min": 0.2829, "x_max": 0.5763, "y_max": 0.3762}	16168	12.89	2026-10-14 04:32:20.444104+00
50fe7788-3af3-4a9b-b066-064466f1e240	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4933, "y_min": 0.2915, "x_max": 0.5672, "y_max": 0.3149}	16168	12.89	2026-10-14 04:32:20.444104+00
5dc246f8-021d-4ee0-adb6-20db0c8d3103	1	FIRE_SMOKE	person	0.5687521696090698	{"x_min": 0.5, "y_min": 0.283, "x_max": 0.5748, "y_max": 0.3579}	16240	12.35	2026-10-14 04:32:26.442992+00
8da72036-157f-42a4-96a8-4162d26ea44e	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.5067, "y_min": 0.2897, "x_max": 0.5672, "y_max": 0.3083}	16240	12.35	2026-10-14 04:32:26.442992+00
f3bf63e2-5466-49cd-a6c7-b9eac0e845ab	1	FIRE_SMOKE	person	0.47854679822921753	{"x_min": 0.4835, "y_min": 0.2829, "x_max": 0.597, "y_max": 0.3762}	16312	9.08	2026-10-14 04:32:32.443588+00
7e1a9710-13ee-4ec2-9c10-768091b15195	1	FIRE_SMOKE	person	0.5604132413864136	{"x_min": 0.4813, "y_min": 0.2829, "x_max": 0.5777, "y_max": 0.3748}	16384	11.73	2026-10-14 04:32:38.440572+00
99c66ab3-9033-475a-9482-7a9b97e36d59	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4892, "y_min": 0.2951, "x_max": 0.5692, "y_max": 0.3263}	16384	11.73	2026-10-14 04:32:38.440572+00
e88dca49-1052-48a9-86c0-6f2940dbce73	1	FIRE_SMOKE	gloves	0.21824829280376434	{"x_min": 0.49, "y_min": 0.2961, "x_max": 0.5746, "y_max": 0.4089}	16384	11.73	2026-10-14 04:32:38.440572+00
a1d2828e-580a-40a8-b0c1-024ce12f028b	1	FIRE_SMOKE	person	0.6105735301971436	{"x_min": 0.4833, "y_min": 0.2829, "x_max": 0.5752, "y_max": 0.3762}	16448	12.93	2026-10-14 04:32:43.841291+00
fa0e83a8-32f1-40f3-904f-71091deda3ea	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4919, "y_min": 0.2915, "x_max": 0.5659, "y_max": 0.3149}	16448	12.93	2026-10-14 04:32:43.841291+00
42a09542-3f8c-4dcc-9bf1-1acde41f32e2	1	FIRE_SMOKE	gloves	0.22578312456607819	{"x_min": 0.491, "y_min": 0.2967, "x_max": 0.5753, "y_max": 0.4347}	16448	12.93	2026-10-14 04:32:43.841291+00
dcee806e-741f-4853-892f-cb71dea3ff33	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4919, "y_min": 0.2915, "x_max": 0.5659, "y_max": 0.3149}	16496	12.81	2026-10-14 04:32:47.841012+00
903a2ded-6f42-446e-ab21-d72226c17bb5	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4913, "y_min": 0.2939, "x_max": 0.5665, "y_max": 0.3227}	16612	12	2026-10-14 04:32:57.531158+00
5a772618-1c01-48ee-b226-279444e230ba	1	FIRE_SMOKE	gloves	0.23474286496639252	{"x_min": 0.4933, "y_min": 0.2966, "x_max": 0.5724, "y_max": 0.4123}	16612	12	2026-10-14 04:32:57.531158+00
e127e5cd-af57-4740-9295-692ef7aa7eae	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4919, "y_min": 0.2915, "x_max": 0.5672, "y_max": 0.3149}	16732	11.16	2026-10-14 04:33:07.543646+00
7828a476-8b74-4198-b594-dd0ef2cd7a4b	1	FIRE_SMOKE	gloves	0.20329119265079498	{"x_min": 0.4939, "y_min": 0.2967, "x_max": 0.5757, "y_max": 0.4309}	16732	11.16	2026-10-14 04:33:07.543646+00
3f4ed7d7-22c6-4a1e-a5aa-ff651eb89a25	1	FIRE_SMOKE	person	0.6816809177398682	{"x_min": 0.4835, "y_min": 0.283, "x_max": 0.5832, "y_max": 0.3764}	16848	12.44	2026-10-14 04:33:17.237594+00
7f21b679-3c0f-4043-a95d-30b0d84d76a2	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4913, "y_min": 0.2951, "x_max": 0.5746, "y_max": 0.3275}	16848	12.44	2026-10-14 04:33:17.237594+00
ce7df92d-dae9-4485-b796-4b5a8c1d5184	1	FIRE_SMOKE	gloves	0.25837981700897217	{"x_min": 0.4934, "y_min": 0.2967, "x_max": 0.5797, "y_max": 0.4145}	16848	12.44	2026-10-14 04:33:17.237594+00
b1bc7017-c719-4b6a-b434-dabab784238e	1	FIRE_SMOKE	person	0.5538798570632935	{"x_min": 0.4846, "y_min": 0.283, "x_max": 0.5752, "y_max": 0.3575}	17000	11.88	2026-10-14 04:33:30.058375+00
22019105-5113-4c5f-8650-b046c9659516	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4919, "y_min": 0.2927, "x_max": 0.5672, "y_max": 0.3179}	17000	11.88	2026-10-14 04:33:30.058375+00
2be097ac-00d9-47f0-987b-47d1531e6e24	1	FIRE_SMOKE	gloves	0.2327449768781662	{"x_min": 0.4931, "y_min": 0.2944, "x_max": 0.5643, "y_max": 0.4101}	17000	11.88	2026-10-14 04:33:30.058375+00
74dffb8f-3e46-4545-8034-ec385e0800ed	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.5034, "y_min": 0.3053, "x_max": 0.5793, "y_max": 0.3335}	17248	11.84	2026-10-14 04:33:51.231796+00
be03a615-57bd-4083-922e-9b968845beb4	1	FIRE_SMOKE	person	0.6410289406776428	{"x_min": 0.4857, "y_min": 0.2553, "x_max": 0.5977, "y_max": 0.3878}	17772	12.99	2026-10-14 04:34:35.124132+00
3dbbd5d9-75c5-4c56-97e4-7dca8541465d	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4966, "y_min": 0.2674, "x_max": 0.586, "y_max": 0.3005}	17772	12.99	2026-10-14 04:34:35.124132+00
9341d7ae-6c9a-4db6-a359-53270199c38c	1	FIRE_SMOKE	gloves	0.25350716710090637	{"x_min": 0.4885, "y_min": 0.2895, "x_max": 0.57, "y_max": 0.3749}	17772	12.99	2026-10-14 04:34:35.124132+00
a28bcbd7-ff5b-46d7-b7db-e92658e5bb65	1	FIRE_SMOKE	person	0.5564142465591431	{"x_min": 0.4878, "y_min": 0.2553, "x_max": 0.5738, "y_max": 0.3875}	17816	12.26	2026-10-14 04:34:38.849936+00
663e5fd7-39aa-4b81-8306-136349c563fd	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4953, "y_min": 0.2674, "x_max": 0.5652, "y_max": 0.3005}	17816	12.26	2026-10-14 04:34:38.849936+00
7a94e843-2265-4d68-8445-c21a87f82038	1	FIRE_SMOKE	gloves	0.4248571991920471	{"x_min": 0.4961, "y_min": 0.292, "x_max": 0.5749, "y_max": 0.3734}	17816	12.26	2026-10-14 04:34:38.849936+00
f8098ff8-952f-4d9c-83bb-d10badfc0d84	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.496, "y_min": 0.2674, "x_max": 0.5712, "y_max": 0.3005}	17884	10.92	2026-10-14 04:34:44.541616+00
30687200-67f1-47d5-b466-25e5f96eca6e	1	FIRE_SMOKE	person	0.46495482325553894	{"x_min": 0.4886, "y_min": 0.255, "x_max": 0.6067, "y_max": 0.3878}	17944	11.72	2026-10-14 04:34:49.536539+00
b6b91400-0298-4839-bbc0-26622fa9e785	1	FIRE_SMOKE	gloves	0.7844105958938599	{"x_min": 0.5524, "y_min": 0.3355, "x_max": 0.5727, "y_max": 0.3564}	17944	11.72	2026-10-14 04:34:49.536539+00
3cd1397c-1bb6-4747-aec7-0be90c62c6e1	1	FIRE_SMOKE	gloves	0.5563134551048279	{"x_min": 0.5706, "y_min": 0.3545, "x_max": 0.5903, "y_max": 0.3736}	17944	11.72	2026-10-14 04:34:49.536539+00
4a9a9ec7-78dc-4fb3-8538-bd2a469ce34c	1	FIRE_SMOKE	person	0.6584784984588623	{"x_min": 0.4873, "y_min": 0.255, "x_max": 0.5873, "y_max": 0.3885}	18300	12.17	2026-10-14 04:35:19.143251+00
6175ba2a-7a13-442a-be22-625325b14dd5	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4973, "y_min": 0.2674, "x_max": 0.5766, "y_max": 0.3011}	18300	12.17	2026-10-14 04:35:19.143251+00
561bd992-2785-4701-94a3-f55bfc149f3f	1	FIRE_SMOKE	person	0.5611627697944641	{"x_min": 0.4865, "y_min": 0.2553, "x_max": 0.5754, "y_max": 0.3883}	18328	11.82	2026-10-14 04:35:21.534177+00
0a172e15-ff8e-429d-878b-4b697ec6d766	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4946, "y_min": 0.2674, "x_max": 0.5665, "y_max": 0.3011}	18328	11.82	2026-10-14 04:35:21.534177+00
2a420c44-58d4-4a86-8db3-6e6cf72f837c	1	FIRE_SMOKE	gloves	0.33033525943756104	{"x_min": 0.4926, "y_min": 0.2844, "x_max": 0.555, "y_max": 0.37}	18328	11.82	2026-10-14 04:35:21.534177+00
6cc0aa77-18b4-4d03-960b-49ae12dca92f	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4953, "y_min": 0.2674, "x_max": 0.5699, "y_max": 0.3011}	18368	12.61	2026-10-14 04:35:24.92077+00
ad5f2848-bc35-4549-b874-2b998cf04504	1	FIRE_SMOKE	gloves	0.3520887494087219	{"x_min": 0.4976, "y_min": 0.2955, "x_max": 0.564, "y_max": 0.3774}	18368	12.61	2026-10-14 04:35:24.92077+00
c0e8619a-5bc6-4117-b91a-5f4433dff234	1	FIRE_SMOKE	person	0.49152013659477234	{"x_min": 0.4862, "y_min": 0.255, "x_max": 0.5777, "y_max": 0.388}	18396	12.99	2026-10-14 04:35:27.14295+00
15b0d9fb-dd8f-43e8-b78d-a80ea2905e73	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4946, "y_min": 0.2674, "x_max": 0.5685, "y_max": 0.3005}	18436	12.42	2026-10-14 04:35:30.542055+00
16d8b12a-afb8-4d1a-9f46-7a6e3fc90841	1	FIRE_SMOKE	gloves	0.24867704510688782	{"x_min": 0.499, "y_min": 0.2918, "x_max": 0.5677, "y_max": 0.3759}	18436	12.42	2026-10-14 04:35:30.542055+00
535993de-2d31-4d3d-9fcd-ba6bca0d3c78	1	FIRE_SMOKE	person	0.48353326320648193	{"x_min": 0.4838, "y_min": 0.255, "x_max": 0.5719, "y_max": 0.388}	18672	12.06	2026-10-14 04:35:50.142947+00
4e948ef8-aaea-47da-be75-dab30a14ba95	1	FIRE_SMOKE	mask	0.14305417239665985	{"x_min": 0.4819, "y_min": 0.2553, "x_max": 0.5273, "y_max": 0.3202}	18672	12.06	2026-10-14 04:35:50.142947+00
af32c86b-d678-4b6a-a52c-3d96f135bc5e	1	FIRE_SMOKE	gloves	0.2924984097480774	{"x_min": 0.4949, "y_min": 0.2897, "x_max": 0.5587, "y_max": 0.3729}	18700	11.99	2026-10-14 04:35:52.545291+00
6ac1e5e7-ca95-4f62-ab46-853841fef7ad	1	FIRE_SMOKE	person	0.4585644006729126	{"x_min": 0.4857, "y_min": 0.2548, "x_max": 0.5934, "y_max": 0.3878}	18780	12.76	2026-10-14 04:35:59.143112+00
6ae3ca2d-4d34-4dd4-8f29-e226a455dbe1	1	FIRE_SMOKE	person	0.5533507466316223	{"x_min": 0.4865, "y_min": 0.255, "x_max": 0.574, "y_max": 0.3866}	18880	12.08	2026-10-14 04:36:07.54628+00
f00097f2-0a0c-4eea-b813-abf5243060d6	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4946, "y_min": 0.2674, "x_max": 0.5652, "y_max": 0.3005}	18880	12.08	2026-10-14 04:36:07.54628+00
a5699dc2-dfd3-4269-b8bc-25cc5c5711a6	1	FIRE_SMOKE	gloves	0.3064436614513397	{"x_min": 0.4954, "y_min": 0.2906, "x_max": 0.5631, "y_max": 0.3746}	18880	12.08	2026-10-14 04:36:07.54628+00
f421c7c8-366a-44d0-b842-3a163185dfc5	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4946, "y_min": 0.2674, "x_max": 0.5652, "y_max": 0.3005}	18924	11.85	2026-10-14 04:36:11.166075+00
145dbfce-b55a-4c9e-a7c2-474ef7c03689	1	FIRE_SMOKE	person	0.6278210282325745	{"x_min": 0.4881, "y_min": 0.255, "x_max": 0.5698, "y_max": 0.3875}	19044	12.5	2026-10-14 04:36:21.165949+00
970f1838-e3e3-4cb4-92f0-7c9c5be7fb0c	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.496, "y_min": 0.2674, "x_max": 0.5612, "y_max": 0.3005}	19044	12.5	2026-10-14 04:36:21.165949+00
980b7b47-3b25-4fe3-85fb-83ac1066f261	1	FIRE_SMOKE	gloves	0.21067681908607483	{"x_min": 0.4939, "y_min": 0.2898, "x_max": 0.553, "y_max": 0.3715}	19044	12.5	2026-10-14 04:36:21.165949+00
4733920b-192d-4842-8c65-2b5047e6029f	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.496, "y_min": 0.2674, "x_max": 0.5612, "y_max": 0.3005}	19076	12.99	2026-10-14 04:36:23.924729+00
cbf1ec6e-d37a-4b48-8123-19d34eef6170	1	FIRE_SMOKE	gloves	0.39583027362823486	{"x_min": 0.4974, "y_min": 0.2968, "x_max": 0.5593, "y_max": 0.3754}	19076	12.99	2026-10-14 04:36:23.924729+00
5ac7d3e2-f1cf-414e-8e24-6913070f3a86	1	FIRE_SMOKE	person	0.7354339361190796	{"x_min": 0.4838, "y_min": 0.255, "x_max": 0.57, "y_max": 0.388}	19192	12	2026-10-14 04:36:33.564394+00
075185bf-c105-4662-bf90-45cb097c17f0	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4919, "y_min": 0.2674, "x_max": 0.5612, "y_max": 0.3005}	19192	12	2026-10-14 04:36:33.564394+00
1029fd4e-1413-4dd1-be68-54ae6a574921	1	FIRE_SMOKE	gloves	0.24935245513916016	{"x_min": 0.4994, "y_min": 0.2955, "x_max": 0.5682, "y_max": 0.3764}	19192	12	2026-10-14 04:36:33.564394+00
42b87b5c-9df3-4d50-875c-e4431bedd8f3	1	FIRE_SMOKE	person	0.5152591466903687	{"x_min": 0.4889, "y_min": 0.255, "x_max": 0.5902, "y_max": 0.3649}	19224	11.9	2026-10-14 04:36:36.246628+00
205f2de0-1d31-47f6-ad7c-cc65bd62ce0e	1	FIRE_SMOKE	gloves	0.23856070637702942	{"x_min": 0.485, "y_min": 0.2714, "x_max": 0.5349, "y_max": 0.3415}	19224	11.9	2026-10-14 04:36:36.246628+00
0d0b6485-f97b-4515-9873-4a0ca1112f40	1	FIRE_SMOKE	person	0.5733794569969177	{"x_min": 0.4852, "y_min": 0.2548, "x_max": 0.5658, "y_max": 0.3866}	19264	12.39	2026-10-14 04:36:39.664608+00
2517ca53-0b0f-4766-830b-973ebf5802c1	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4926, "y_min": 0.2674, "x_max": 0.5571, "y_max": 0.3005}	19264	12.39	2026-10-14 04:36:39.664608+00
a770c434-15d3-439c-807f-4941a7649c32	1	FIRE_SMOKE	gloves	0.21173352003097534	{"x_min": 0.4948, "y_min": 0.2838, "x_max": 0.5616, "y_max": 0.3747}	19264	12.39	2026-10-14 04:36:39.664608+00
4fb2d85d-f39c-4197-81ca-751c30dba731	1	FIRE_SMOKE	person	0.4871816039085388	{"x_min": 0.4828, "y_min": 0.255, "x_max": 0.5703, "y_max": 0.388}	19336	12.74	2026-10-14 04:36:45.664055+00
5502886f-7293-496f-9240-219433d43d95	1	FIRE_SMOKE	person	0.52691251039505	{"x_min": 0.483, "y_min": 0.255, "x_max": 0.5793, "y_max": 0.3883}	19412	11.86	2026-10-14 04:36:51.956749+00
907668ad-7903-4426-b7ee-46c03a95b144	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4919, "y_min": 0.2674, "x_max": 0.5699, "y_max": 0.3011}	19412	11.86	2026-10-14 04:36:51.956749+00
c09721f6-8366-4c14-ad90-486da24f51b5	1	FIRE_SMOKE	gloves	0.2128511518239975	{"x_min": 0.4952, "y_min": 0.2902, "x_max": 0.5582, "y_max": 0.3735}	19412	11.86	2026-10-14 04:36:51.956749+00
982de1d9-efd1-47e4-8017-94bf50ba7a13	1	FIRE_SMOKE	person	0.6099330186843872	{"x_min": 0.4849, "y_min": 0.255, "x_max": 0.578, "y_max": 0.388}	19488	13.94	2026-10-14 04:36:58.367063+00
66b911b6-4483-435a-9c67-f738fb74afc7	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4933, "y_min": 0.2674, "x_max": 0.5692, "y_max": 0.3005}	19488	13.94	2026-10-14 04:36:58.367063+00
4149bbb2-ef35-471f-b5f9-956063d80c45	1	FIRE_SMOKE	gloves	0.24422688782215118	{"x_min": 0.4962, "y_min": 0.2925, "x_max": 0.5581, "y_max": 0.3748}	19488	13.94	2026-10-14 04:36:58.367063+00
ff33691a-d572-4a61-b590-2826e33a6746	1	FIRE_SMOKE	person	0.4759025275707245	{"x_min": 0.4836, "y_min": 0.255, "x_max": 0.5684, "y_max": 0.3878}	19624	11.87	2026-10-14 04:37:09.763194+00
854227e5-b781-416c-ac1d-30046e24c8d2	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4913, "y_min": 0.2674, "x_max": 0.5598, "y_max": 0.3011}	19940	7.32	2026-10-14 04:37:36.765407+00
b7aa8734-2f11-4caa-a7f0-1c0cf3454ad0	1	FIRE_SMOKE	person	0.6603959202766418	{"x_min": 0.4833, "y_min": 0.255, "x_max": 0.5655, "y_max": 0.388}	20052	11.83	2026-10-14 04:37:46.462724+00
b9f81414-0ed4-4677-9b0d-e40a071aa7ee	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4913, "y_min": 0.2674, "x_max": 0.5571, "y_max": 0.3005}	20052	11.83	2026-10-14 04:37:46.462724+00
0d1130a8-e81c-4977-872a-2a5d60b9034a	1	FIRE_SMOKE	person	0.5075061321258545	{"x_min": 0.4836, "y_min": 0.255, "x_max": 0.5682, "y_max": 0.388}	20168	13.89	2026-10-14 04:37:56.124665+00
12cb93e6-75b1-4791-bf9a-0c041ec6fe4e	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4913, "y_min": 0.2674, "x_max": 0.5598, "y_max": 0.3005}	20168	13.89	2026-10-14 04:37:56.124665+00
dc9c1cd3-0b2b-4932-bb6e-5b4260382f12	1	FIRE_SMOKE	gloves	0.25364571809768677	{"x_min": 0.4969, "y_min": 0.2954, "x_max": 0.5704, "y_max": 0.3753}	20168	13.89	2026-10-14 04:37:56.124665+00
81b78143-154d-4a0a-bd29-04130d0b0791	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4973, "y_min": 0.2674, "x_max": 0.5726, "y_max": 0.3017}	21332	9.34	2026-10-14 04:39:33.166318+00
e7688ba2-62c8-4e24-8402-73bd05c3b663	1	FIRE_SMOKE	gloves	0.4835819602012634	{"x_min": 0.5505, "y_min": 0.3345, "x_max": 0.5725, "y_max": 0.3558}	21332	9.34	2026-10-14 04:39:33.166318+00
0bf9e9c3-a4cd-4023-839a-58f2a10c2543	1	FIRE_SMOKE	person	0.6018044352531433	{"x_min": 0.4825, "y_min": 0.255, "x_max": 0.5746, "y_max": 0.3873}	21584	11.82	2026-10-14 04:39:54.164907+00
67bc102b-6906-405a-9010-e2e05926ecb9	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4906, "y_min": 0.2674, "x_max": 0.5652, "y_max": 0.3005}	21584	11.82	2026-10-14 04:39:54.164907+00
fa2c0b2a-35b1-4dd8-9afc-2e461e870b9c	1	FIRE_SMOKE	person	0.5649695992469788	{"x_min": 0.5121, "y_min": 0.1904, "x_max": 0.5675, "y_max": 0.3231}	21752	11.99	2026-10-14 04:40:08.164546+00
281ad7ee-7335-46d2-901f-241e481273dd	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.5188, "y_min": 0.1971, "x_max": 0.5605, "y_max": 0.2194}	21752	11.99	2026-10-14 04:40:08.164546+00
2375eb11-fee7-4917-bc98-03b3cd4a94e5	1	FIRE_SMOKE	person	0.5508794784545898	{"x_min": 0.5121, "y_min": 0.1901, "x_max": 0.5634, "y_max": 0.3238}	22024	11.98	2026-10-14 04:40:30.925019+00
db3ce8a4-7b13-43f2-9e93-347175f3e519	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.5181, "y_min": 0.1971, "x_max": 0.5571, "y_max": 0.2194}	22024	11.98	2026-10-14 04:40:30.925019+00
cdd150b1-81e2-447e-bb3b-49b4db5b8d65	1	FIRE_SMOKE	person	0.6221421957015991	{"x_min": 0.5121, "y_min": 0.1904, "x_max": 0.5888, "y_max": 0.3221}	22220	11.97	2026-10-14 04:40:47.167068+00
156c298e-324d-4549-931b-d12046034eaf	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.5195, "y_min": 0.2025, "x_max": 0.5813, "y_max": 0.2356}	22220	11.97	2026-10-14 04:40:47.167068+00
7d9e149e-4fc7-49c3-b08b-7e892c0e9d1f	1	FIRE_SMOKE	person	0.6220661401748657	{"x_min": 0.5124, "y_min": 0.1906, "x_max": 0.5888, "y_max": 0.3229}	22292	11.83	2026-10-14 04:40:53.1664+00
819c5dd6-5ef2-410b-ac40-6309a0b6d878	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.5195, "y_min": 0.2031, "x_max": 0.5813, "y_max": 0.2362}	22292	11.83	2026-10-14 04:40:53.1664+00
27ba5502-1a08-4f52-811b-b21c5e482790	1	FIRE_SMOKE	person	0.6198135614395142	{"x_min": 0.5124, "y_min": 0.1901, "x_max": 0.5947, "y_max": 0.3221}	22364	12.58	2026-10-14 04:40:59.167977+00
b44a7990-4901-4d27-b621-50e68fd87e6b	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.5202, "y_min": 0.2025, "x_max": 0.586, "y_max": 0.2356}	22364	12.58	2026-10-14 04:40:59.167977+00
d06fbeb9-42b9-47e4-80b9-3434930a4b3f	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4933, "y_min": 0.2668, "x_max": 0.5632, "y_max": 0.2987}	19296	12.38	2026-10-14 04:36:42.266408+00
fd07a9fa-a158-4dbd-a16a-d265cb733296	1	FIRE_SMOKE	gloves	0.22634942829608917	{"x_min": 0.497, "y_min": 0.2927, "x_max": 0.5548, "y_max": 0.3711}	19296	12.38	2026-10-14 04:36:42.266408+00
ec097bb6-125c-448c-879c-16bd6a134ad6	1	FIRE_SMOKE	person	0.7349917888641357	{"x_min": 0.4844, "y_min": 0.255, "x_max": 0.5706, "y_max": 0.3883}	19368	11.98	2026-10-14 04:36:48.267899+00
3ed66cdd-7367-406b-8399-b482bd06b2dc	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4926, "y_min": 0.2674, "x_max": 0.5618, "y_max": 0.3011}	19368	11.98	2026-10-14 04:36:48.267899+00
04fcdbfd-6bc7-42f8-a6b6-42815788f5a0	1	FIRE_SMOKE	gloves	0.266720175743103	{"x_min": 0.4941, "y_min": 0.2879, "x_max": 0.5676, "y_max": 0.3772}	19368	11.98	2026-10-14 04:36:48.267899+00
ad601482-4c27-45b4-915d-49ce73b5115a	1	FIRE_SMOKE	person	0.7135936617851257	{"x_min": 0.4849, "y_min": 0.255, "x_max": 0.5671, "y_max": 0.388}	19448	11.92	2026-10-14 04:36:55.064841+00
bd83a2e5-1fda-491b-ba2b-5a099a9be666	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4926, "y_min": 0.2674, "x_max": 0.5585, "y_max": 0.3005}	19448	11.92	2026-10-14 04:36:55.064841+00
73b75f94-d926-4347-90f5-c44faf2dc5e4	1	FIRE_SMOKE	person	0.7226173877716064	{"x_min": 0.4849, "y_min": 0.255, "x_max": 0.569, "y_max": 0.3878}	19520	12.06	2026-10-14 04:37:01.067755+00
83401ead-8104-4ca2-8ed8-a934d59098fd	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4926, "y_min": 0.2674, "x_max": 0.5605, "y_max": 0.3005}	19520	12.06	2026-10-14 04:37:01.067755+00
87a162b0-3f51-4bf3-9629-3b4c015dfc71	1	FIRE_SMOKE	gloves	0.30960193276405334	{"x_min": 0.4894, "y_min": 0.2813, "x_max": 0.5455, "y_max": 0.3646}	19520	12.06	2026-10-14 04:37:01.067755+00
0ecbf878-9a53-4eca-9d36-38272795fb2f	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4926, "y_min": 0.2674, "x_max": 0.5625, "y_max": 0.3005}	19568	12.74	2026-10-14 04:37:05.064537+00
15009eaf-27d3-4d59-828e-9026ae4c2a16	1	FIRE_SMOKE	person	0.5294235944747925	{"x_min": 0.4838, "y_min": 0.2553, "x_max": 0.5682, "y_max": 0.3883}	19908	10	2026-10-14 04:37:33.664879+00
864c09e6-9a3c-42f5-86c6-94bc5f10f910	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4913, "y_min": 0.2674, "x_max": 0.5598, "y_max": 0.3011}	19908	10	2026-10-14 04:37:33.664879+00
74d2e258-7441-4016-a574-a64c0218429f	1	FIRE_SMOKE	person	0.5500310659408569	{"x_min": 0.4825, "y_min": 0.255, "x_max": 0.5663, "y_max": 0.388}	19996	11.93	2026-10-14 04:37:41.76258+00
31d18d67-31ab-4fc6-9f22-138503542128	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4899, "y_min": 0.2674, "x_max": 0.5578, "y_max": 0.3005}	19996	11.93	2026-10-14 04:37:41.76258+00
5b5a7722-5919-45d2-8a90-1a42277352a5	1	FIRE_SMOKE	person	0.5917332172393799	{"x_min": 0.4849, "y_min": 0.255, "x_max": 0.5706, "y_max": 0.3883}	20116	11.91	2026-10-14 04:37:51.863214+00
6f4cc9ee-7b1f-4cd2-a3eb-0b0ffa42e27c	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4926, "y_min": 0.2674, "x_max": 0.5625, "y_max": 0.3011}	20116	11.91	2026-10-14 04:37:51.863214+00
59e32b56-7def-4ebf-8c5f-b270767085e8	1	FIRE_SMOKE	gloves	0.23881258070468903	{"x_min": 0.4959, "y_min": 0.2976, "x_max": 0.568, "y_max": 0.3757}	20116	11.91	2026-10-14 04:37:51.863214+00
2361bbd0-1103-4511-9e03-ae716ab2f614	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4913, "y_min": 0.2674, "x_max": 0.5598, "y_max": 0.3005}	20224	11.86	2026-10-14 04:38:00.868522+00
9093042e-743d-4181-a078-20dcb74abea0	1	FIRE_SMOKE	gloves	0.4299723505973816	{"x_min": 0.5509, "y_min": 0.3348, "x_max": 0.5708, "y_max": 0.3567}	20224	11.86	2026-10-14 04:38:00.868522+00
51108fd6-4625-4198-9beb-4b2d243d7689	1	FIRE_SMOKE	person	0.5424108505249023	{"x_min": 0.488, "y_min": 0.2548, "x_max": 0.5821, "y_max": 0.3895}	21296	12.5	2026-10-14 04:39:30.167663+00
b0a1d0f4-bc53-4b37-8ae4-f057ded5c230	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4973, "y_min": 0.2674, "x_max": 0.5726, "y_max": 0.3017}	21296	12.5	2026-10-14 04:39:30.167663+00
a65dd4d9-c510-4b76-a936-5260fc930e22	1	FIRE_SMOKE	gloves	0.9065902233123779	{"x_min": 0.551, "y_min": 0.3353, "x_max": 0.5711, "y_max": 0.3554}	21296	12.5	2026-10-14 04:39:30.167663+00
9a847e3b-2bb0-4e7c-833e-fc4f71f4ec26	1	FIRE_SMOKE	gloves	0.29351794719696045	{"x_min": 0.5702, "y_min": 0.3541, "x_max": 0.5853, "y_max": 0.373}	21296	12.5	2026-10-14 04:39:30.167663+00
d39ca666-bd05-4a5a-8e97-38079ad60ce3	1	FIRE_SMOKE	person	0.6729904413223267	{"x_min": 0.4844, "y_min": 0.255, "x_max": 0.5711, "y_max": 0.3885}	21552	11.78	2026-10-14 04:39:51.566824+00
c9aab8e4-1850-4d64-adce-d7d69245d720	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4926, "y_min": 0.2674, "x_max": 0.5618, "y_max": 0.3011}	21552	11.78	2026-10-14 04:39:51.566824+00
f9392449-36fe-43ab-8908-d0ed3fa95c21	1	FIRE_SMOKE	gloves	0.21884751319885254	{"x_min": 0.4954, "y_min": 0.2879, "x_max": 0.5586, "y_max": 0.3756}	21552	11.78	2026-10-14 04:39:51.566824+00
987bb2b6-81a0-4cd9-85f6-dc1cf5f2bccf	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4913, "y_min": 0.2674, "x_max": 0.5645, "y_max": 0.3005}	21628	12.52	2026-10-14 04:39:57.92553+00
c8f5bdba-bfbd-4538-a6e1-1813ba804444	1	FIRE_SMOKE	person	0.4448208808898926	{"x_min": 0.5124, "y_min": 0.1911, "x_max": 0.5677, "y_max": 0.3212}	21784	11.82	2026-10-14 04:40:10.923947+00
544eb8f0-3a51-40c0-97a8-d6396168114e	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.5181, "y_min": 0.1971, "x_max": 0.5571, "y_max": 0.2194}	22060	14.59	2026-10-14 04:40:33.924516+00
35394424-9806-4073-949c-087e8a17d840	1	FIRE_SMOKE	person	0.607262372970581	{"x_min": 0.5124, "y_min": 0.1904, "x_max": 0.5883, "y_max": 0.3236}	22260	12.01	2026-10-14 04:40:50.565856+00
bdce23c2-7588-41e6-b02d-0394eef5a8fc	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.5195, "y_min": 0.2025, "x_max": 0.5806, "y_max": 0.2362}	22260	12.01	2026-10-14 04:40:50.565856+00
e8d3b067-5e02-49cc-88fd-2100f2ffaa9b	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.5195, "y_min": 0.2031, "x_max": 0.5813, "y_max": 0.2362}	22332	12	2026-10-14 04:40:56.568011+00
801fd493-9396-4f9c-808d-e388fa968707	1	FIRE_SMOKE	person	0.6566974520683289	{"x_min": 0.5124, "y_min": 0.1904, "x_max": 0.5846, "y_max": 0.3231}	22408	11.92	2026-10-14 04:41:02.937772+00
2afdab4b-b328-44d3-be49-46379f4df6e5	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.5208, "y_min": 0.1971, "x_max": 0.5753, "y_max": 0.2194}	22408	11.92	2026-10-14 04:41:02.937772+00
d8259b2b-db35-4e91-93c3-388f9289ffad	1	FIRE_SMOKE	person	0.46683087944984436	{"x_min": 0.4879, "y_min": 0.2656, "x_max": 0.5719, "y_max": 0.3861}	308	11.85	2026-10-14 04:41:46.994084+00
8c22e6c3-c7d9-4aaa-82b7-fe313dca4821	1	FIRE_SMOKE	person	0.5344831943511963	{"x_min": 0.4706, "y_min": 0.1983, "x_max": 0.5809, "y_max": 0.3732}	888	11.9	2026-10-14 04:42:36.087372+00
de65e603-b834-4b3d-8ac9-0c4e249eba72	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4812, "y_min": 0.2151, "x_max": 0.5699, "y_max": 0.2596}	888	11.9	2026-10-14 04:42:36.087372+00
b05596d5-1569-4594-94c8-9718e66eae19	1	FIRE_SMOKE	gloves	0.8208851218223572	{"x_min": 0.5503, "y_min": 0.3367, "x_max": 0.5707, "y_max": 0.3583}	888	11.9	2026-10-14 04:42:36.087372+00
60437000-3537-4d54-b936-a497aba59283	1	FIRE_SMOKE	person	0.9424639940261841	{"x_min": 0.4939, "y_min": 0.1792, "x_max": 0.5945, "y_max": 0.3494}	924	11.88	2026-10-14 04:42:39.087141+00
c125525a-96ef-4be4-944b-e56c9ba254d1	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.5034, "y_min": 0.1959, "x_max": 0.584, "y_max": 0.238}	924	11.88	2026-10-14 04:42:39.087141+00
430477a2-8833-457d-8690-878f7d618d74	1	FIRE_SMOKE	person	0.6802491545677185	{"x_min": 0.4974, "y_min": 0.1815, "x_max": 0.5967, "y_max": 0.349}	968	11.95	2026-10-14 04:42:42.785531+00
30298105-ff18-4c46-b4c9-7692586ed9ff	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.5067, "y_min": 0.1971, "x_max": 0.5867, "y_max": 0.2392}	968	11.95	2026-10-14 04:42:42.785531+00
18e5a429-629e-4ac7-9104-75f1a540d6c3	1	FIRE_SMOKE	person	0.8838122487068176	{"x_min": 0.4974, "y_min": 0.178, "x_max": 0.5975, "y_max": 0.3494}	1004	12.91	2026-10-14 04:42:45.784733+00
bb430834-1a94-4cda-98dc-926677fc0f46	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.5074, "y_min": 0.1947, "x_max": 0.5874, "y_max": 0.2374}	1004	12.91	2026-10-14 04:42:45.784733+00
3d47d7ff-29e3-45aa-b2fd-2a1cab8f0c72	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.506, "y_min": 0.1959, "x_max": 0.586, "y_max": 0.2386}	1044	11.22	2026-10-14 04:42:49.086876+00
2e7f5ec1-214a-4a76-880f-9f1d0fe21774	1	FIRE_SMOKE	person	0.9447118043899536	{"x_min": 0.4982, "y_min": 0.1807, "x_max": 0.5962, "y_max": 0.3487}	1084	11.9	2026-10-14 04:42:52.386509+00
0286cec2-59c7-46dc-9158-dcc0b5955b0c	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.5074, "y_min": 0.1965, "x_max": 0.5867, "y_max": 0.2386}	1084	11.9	2026-10-14 04:42:52.386509+00
53bba331-cb63-4585-bbe0-9b5c94126822	1	FIRE_SMOKE	person	0.9900000095367432	{"x_min": 0.4974, "y_min": 0.1815, "x_max": 0.5945, "y_max": 0.349}	1132	11.97	2026-10-14 04:42:56.389866+00
276643e3-c371-4900-a567-897e87547415	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.5067, "y_min": 0.1971, "x_max": 0.5847, "y_max": 0.2392}	1132	11.97	2026-10-14 04:42:56.389866+00
5f5e4c1a-7c52-4e91-989d-565a8290c373	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.5067, "y_min": 0.1971, "x_max": 0.5853, "y_max": 0.2392}	1164	12.76	2026-10-14 04:42:59.084549+00
be451001-13bf-40f3-8f6a-fb53b64d8c3f	1	FIRE_SMOKE	person	0.48666951060295105	{"x_min": 0.4974, "y_min": 0.1807, "x_max": 0.5949, "y_max": 0.349}	1208	11.97	2026-10-14 04:43:02.776534+00
4e0fa17c-cf6a-4b4a-abfd-58b3b3dae8e5	1	FIRE_SMOKE	person	0.9900000095367432	{"x_min": 0.4978, "y_min": 0.1807, "x_max": 0.5975, "y_max": 0.349}	1244	13.73	2026-10-14 04:43:05.776238+00
8d19ff6e-9440-4741-ae0d-efc2fa92dae5	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.5074, "y_min": 0.1965, "x_max": 0.5874, "y_max": 0.2386}	1244	13.73	2026-10-14 04:43:05.776238+00
c9b9ef47-7c7a-4fca-aad6-1a994ed3b71e	1	FIRE_SMOKE	person	0.4476081430912018	{"x_min": 0.4974, "y_min": 0.1826, "x_max": 0.5855, "y_max": 0.349}	1288	12.69	2026-10-14 04:43:09.39063+00
3ded524c-6ecb-4302-a225-37d3f8d6a48d	1	FIRE_SMOKE	person	0.7875999808311462	{"x_min": 0.4978, "y_min": 0.1822, "x_max": 0.5928, "y_max": 0.3494}	1320	14.63	2026-10-14 04:43:12.086593+00
337658da-8eb4-4d79-9c5e-21bb99826ed8	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.5067, "y_min": 0.1983, "x_max": 0.5833, "y_max": 0.2404}	1320	14.63	2026-10-14 04:43:12.086593+00
660df1aa-b244-4627-bc0e-4970d0a8000f	1	FIRE_SMOKE	person	0.7418933510780334	{"x_min": 0.4978, "y_min": 0.1815, "x_max": 0.5949, "y_max": 0.349}	1364	11.99	2026-10-14 04:43:15.786093+00
da5fa8ca-9852-469d-8194-0bd2de457789	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.5067, "y_min": 0.1971, "x_max": 0.5853, "y_max": 0.2392}	1364	11.99	2026-10-14 04:43:15.786093+00
075444aa-59b2-4852-903f-8aba149142ae	1	FIRE_SMOKE	person	0.5299884080886841	{"x_min": 0.4969, "y_min": 0.1818, "x_max": 0.5997, "y_max": 0.3494}	1400	11.9	2026-10-14 04:43:18.788338+00
00776bbc-b649-462d-baa9-22227555bccf	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.5067, "y_min": 0.1977, "x_max": 0.5894, "y_max": 0.2398}	1400	11.9	2026-10-14 04:43:18.788338+00
56680a12-a8c4-4b5b-8ea1-d1f5d841f06b	1	FIRE_SMOKE	person	0.8869715929031372	{"x_min": 0.4978, "y_min": 0.183, "x_max": 0.5962, "y_max": 0.349}	1448	11.81	2026-10-14 04:43:22.785761+00
2de60bf9-5d39-49c0-831b-f26b4b8cdb28	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.5067, "y_min": 0.1989, "x_max": 0.5867, "y_max": 0.2404}	1448	11.81	2026-10-14 04:43:22.785761+00
53994d36-bcce-40da-bf3f-1901f4cd3300	1	FIRE_SMOKE	person	0.9900000095367432	{"x_min": 0.4969, "y_min": 0.1826, "x_max": 0.5941, "y_max": 0.349}	1496	11.07	2026-10-14 04:43:26.786187+00
4e8f97c0-e2fd-4d51-9b52-729253e74d99	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.506, "y_min": 0.1983, "x_max": 0.584, "y_max": 0.2404}	1496	11.07	2026-10-14 04:43:26.786187+00
cb539d31-f113-44c4-adae-5536c47dbad7	1	FIRE_SMOKE	person	0.5335814356803894	{"x_min": 0.4974, "y_min": 0.1822, "x_max": 0.5915, "y_max": 0.349}	1560	13.83	2026-10-14 04:43:32.085725+00
ca50ef15-17d6-4110-8494-3b54686780b1	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.5067, "y_min": 0.1983, "x_max": 0.582, "y_max": 0.2404}	1560	13.83	2026-10-14 04:43:32.085725+00
b2126eee-a015-4da1-bff2-e00d5758d68b	1	FIRE_SMOKE	person	0.9900000095367432	{"x_min": 0.4978, "y_min": 0.1834, "x_max": 0.5971, "y_max": 0.349}	1612	11.2	2026-10-14 04:43:36.376543+00
fb57253a-d8e1-44f4-9e67-acfe1ab31fdb	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.5074, "y_min": 0.1995, "x_max": 0.5867, "y_max": 0.241}	1612	11.2	2026-10-14 04:43:36.376543+00
414c5a6c-4628-4c98-9805-510188a8a55d	1	FIRE_SMOKE	person	0.6719860434532166	{"x_min": 0.4969, "y_min": 0.1834, "x_max": 0.5876, "y_max": 0.3494}	1680	11.91	2026-10-14 04:43:42.084387+00
271eea53-4ccc-4ef0-81c4-7a2c44d90760	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.5074, "y_min": 0.1929, "x_max": 0.5766, "y_max": 0.22}	1680	11.91	2026-10-14 04:43:42.084387+00
c7dcbec9-f49f-4ba7-a4f5-53eb4053cc19	1	FIRE_SMOKE	person	0.9900000095367432	{"x_min": 0.4974, "y_min": 0.1822, "x_max": 0.5962, "y_max": 0.349}	1736	11.97	2026-10-14 04:43:46.784988+00
4c208a75-f11d-4907-868b-f08344369e83	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.5067, "y_min": 0.1983, "x_max": 0.5867, "y_max": 0.2404}	1736	11.97	2026-10-14 04:43:46.784988+00
ef418404-cb43-4cdd-b18e-2271a5fa54c2	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.506, "y_min": 0.1983, "x_max": 0.5847, "y_max": 0.2404}	1784	12.65	2026-10-14 04:43:50.788739+00
72833de5-3312-4f3d-8063-ca4120627ed7	1	FIRE_SMOKE	person	0.8507398366928101	{"x_min": 0.4974, "y_min": 0.183, "x_max": 0.5945, "y_max": 0.349}	1820	12.81	2026-10-14 04:43:53.788234+00
3b951b8d-7a61-429e-bc51-daf83e2e01df	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.5067, "y_min": 0.1989, "x_max": 0.5847, "y_max": 0.2404}	1820	12.81	2026-10-14 04:43:53.788234+00
6b062ec5-9404-49aa-aaf5-3aeff474c065	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.5067, "y_min": 0.1989, "x_max": 0.5847, "y_max": 0.2404}	1872	11.98	2026-10-14 04:43:58.085593+00
6c152d9f-7f10-4047-ae9f-f8a7320eddcc	1	FIRE_SMOKE	person	0.8190028071403503	{"x_min": 0.4978, "y_min": 0.1826, "x_max": 0.5919, "y_max": 0.3494}	1956	11.73	2026-10-14 04:44:05.088608+00
2a6b7142-ffba-4d05-aa43-a19a1f0fb8c0	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.5067, "y_min": 0.1983, "x_max": 0.582, "y_max": 0.2404}	1956	11.73	2026-10-14 04:44:05.088608+00
e5584541-ab6a-4fbf-9020-9dc7d08624ad	1	FIRE_SMOKE	person	0.9534357190132141	{"x_min": 0.4974, "y_min": 0.1834, "x_max": 0.5984, "y_max": 0.349}	2008	12.96	2026-10-14 04:44:09.386713+00
db55b27f-e28e-40f4-a050-74a30edc74bc	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.5074, "y_min": 0.1995, "x_max": 0.588, "y_max": 0.241}	2008	12.96	2026-10-14 04:44:09.386713+00
8d04e9df-a8c8-4795-9b51-16d4f8d3ccfd	1	FIRE_SMOKE	person	0.47077691555023193	{"x_min": 0.4969, "y_min": 0.183, "x_max": 0.5928, "y_max": 0.349}	2068	12.75	2026-10-14 04:44:14.48488+00
f4209fb1-6deb-4c65-9419-51ee91f77fe2	1	FIRE_SMOKE	person	0.6863467693328857	{"x_min": 0.4969, "y_min": 0.1826, "x_max": 0.5902, "y_max": 0.349}	2120	12.72	2026-10-14 04:44:18.885347+00
eea16caa-ee50-42a2-a9f6-a679c71d9fc1	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.5054, "y_min": 0.1983, "x_max": 0.5813, "y_max": 0.2404}	2120	12.72	2026-10-14 04:44:18.885347+00
4ce39a11-4037-4a1c-9c8f-406da04b28f8	1	FIRE_SMOKE	person	0.5187268257141113	{"x_min": 0.4965, "y_min": 0.183, "x_max": 0.5915, "y_max": 0.349}	2192	12.14	2026-10-14 04:44:24.885615+00
78e07598-794f-4255-8667-3afe77521530	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.5054, "y_min": 0.1989, "x_max": 0.582, "y_max": 0.2404}	2192	12.14	2026-10-14 04:44:24.885615+00
cd91d5ab-1ec1-448b-8c19-92eece55e6d3	1	FIRE_SMOKE	person	0.7307116985321045	{"x_min": 0.4982, "y_min": 0.1842, "x_max": 0.5997, "y_max": 0.349}	2376	12.82	2026-10-14 04:44:40.251013+00
62279107-0213-4163-be79-148dd3889a9a	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.5081, "y_min": 0.1995, "x_max": 0.5894, "y_max": 0.2416}	2376	12.82	2026-10-14 04:44:40.251013+00
5fd41079-55d1-4ea1-b2e1-543a6ffc7c35	1	FIRE_SMOKE	person	0.8384854793548584	{"x_min": 0.4969, "y_min": 0.1845, "x_max": 0.5949, "y_max": 0.349}	2548	12.6	2026-10-14 04:44:54.585595+00
c2283cef-3320-424e-8a4f-5f1574559af5	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.506, "y_min": 0.2001, "x_max": 0.5853, "y_max": 0.2416}	2548	12.6	2026-10-14 04:44:54.585595+00
f2126325-f038-47f9-addb-1b138ccbdafe	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.5081, "y_min": 0.1887, "x_max": 0.5766, "y_max": 0.2169}	2692	13.52	2026-10-14 04:45:06.587678+00
c89cbf14-94ca-4eec-9df8-6e0b12737913	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.5074, "y_min": 0.1965, "x_max": 0.5867, "y_max": 0.2386}	2908	11.84	2026-10-14 04:45:26.287102+00
0ba0457a-5f37-4ca5-a73f-8be1aaf31dd6	1	FIRE_SMOKE	person	0.9900000095367432	{"x_min": 0.4974, "y_min": 0.1768, "x_max": 0.5954, "y_max": 0.3494}	3080	11.98	2026-10-14 04:45:40.684431+00
fd03d257-a347-41fc-b720-903006eea4bc	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.5067, "y_min": 0.1935, "x_max": 0.5853, "y_max": 0.2368}	3080	11.98	2026-10-14 04:45:40.684431+00
6dce2804-b0c9-4b78-803b-ded8ed67dd0e	1	FIRE_SMOKE	person	0.6222542524337769	{"x_min": 0.6492, "y_min": 0.2502, "x_max": 0.8211, "y_max": 0.7245}	3272	11.77	2026-10-14 04:45:56.686827+00
0fbc50e8-f334-4174-8e62-9527cee37074	1	FIRE_SMOKE	goggles	0.9900000095367432	{"x_min": 0.6512, "y_min": 0.3065, "x_max": 0.7917, "y_max": 0.4279}	3272	11.77	2026-10-14 04:45:56.686827+00
5b8e74b9-d966-46ba-84cc-ae48bb6e0d9b	1	FIRE_SMOKE	goggles	0.47418203949928284	{"x_min": 0.6761, "y_min": 0.2218, "x_max": 0.7749, "y_max": 0.3131}	3272	11.77	2026-10-14 04:45:56.686827+00
87cdd5c5-a626-4874-9ccd-d1fb93a3ab16	1	FIRE_SMOKE	goggles	0.38061514496803284	{"x_min": 0.6317, "y_min": 0.2218, "x_max": 0.6976, "y_max": 0.3167}	3272	11.77	2026-10-14 04:45:56.686827+00
8984b5ac-936c-4de2-91d0-874308e1299d	1	FIRE_SMOKE	safety_shoes	0.3523435890674591	{"x_min": 0.7211, "y_min": 0.603, "x_max": 1.0, "y_max": 0.9534}	3272	11.77	2026-10-14 04:45:56.686827+00
4c064a82-73e5-4750-a9e2-8c518e17cf4e	1	FIRE_SMOKE	goggles	0.25498899817466736	{"x_min": 0.7513, "y_min": 0.2218, "x_max": 0.8353, "y_max": 0.2993}	3272	11.77	2026-10-14 04:45:56.686827+00
4cb287e1-c2c8-42f6-b4dc-5525b9a37b55	1	FIRE_SMOKE	goggles	0.1267334520816803	{"x_min": 0.6317, "y_min": 0.3858, "x_max": 0.7177, "y_max": 0.4297}	3272	11.77	2026-10-14 04:45:56.686827+00
9a0661fb-bf79-47a7-a44a-91a2dfe368ef	1	FIRE_SMOKE	smoke	0.7538	{"x_min": 0.416, "y_min": 0.4126, "x_max": 0.986, "y_max": 0.9997}	4096	12.45	2026-10-14 04:47:05.288336+00
3f0c0349-665a-417d-8896-cca56dfeefef	1	FIRE_SMOKE	goggles	0.3442608714103699	{"x_min": 0.5827, "y_min": 0.2043, "x_max": 0.664, "y_max": 0.3077}	4272	12.99	2026-10-14 04:47:20.008758+00
061997d3-e7cc-4ad6-9eef-7fe9dd0ba7f2	1	FIRE_SMOKE	person	0.7144163846969604	{"x_min": 0.3141, "y_min": 0.1138, "x_max": 0.4401, "y_max": 0.5283}	4332	13.63	2026-10-14 04:47:25.009202+00
576805e0-ba6d-4f82-8cf7-cef8e6b26875	1	FIRE_SMOKE	goggles	0.7391354441642761	{"x_min": 0.3044, "y_min": 0.1731, "x_max": 0.4153, "y_max": 0.2656}	4332	13.63	2026-10-14 04:47:25.009202+00
de05b886-eafa-49da-9916-a619519167f2	1	FIRE_SMOKE	goggles	0.42791715264320374	{"x_min": 0.3017, "y_min": 0.1142, "x_max": 0.3629, "y_max": 0.2692}	4332	13.63	2026-10-14 04:47:25.009202+00
88316933-02e2-4119-93b4-c84b03622f6e	1	FIRE_SMOKE	goggles	0.2730349004268646	{"x_min": 0.3595, "y_min": 0.0889, "x_max": 0.4516, "y_max": 0.1671}	4332	13.63	2026-10-14 04:47:25.009202+00
9cf6da8c-9f57-4a1d-a71f-c7e13f6e39dc	1	FIRE_SMOKE	goggles	0.19923512637615204	{"x_min": 0.3737, "y_min": 0.1562, "x_max": 0.4469, "y_max": 0.2656}	4332	13.63	2026-10-14 04:47:25.009202+00
1a85c954-1aab-48da-8251-8e126c4f590e	1	FIRE_SMOKE	person	0.8226375579833984	{"x_min": 0.3024, "y_min": 0.1038, "x_max": 0.4453, "y_max": 0.5537}	4404	12.41	2026-10-14 04:47:31.009139+00
01067380-5c87-4c1b-83d7-2b99c7642159	1	FIRE_SMOKE	goggles	0.9592264890670776	{"x_min": 0.295, "y_min": 0.1665, "x_max": 0.3978, "y_max": 0.2734}	4404	12.41	2026-10-14 04:47:31.009139+00
61669265-4f69-47af-b5eb-79128d4dd9bc	1	FIRE_SMOKE	goggles	0.18739277124404907	{"x_min": 0.2883, "y_min": 0.0769, "x_max": 0.3737, "y_max": 0.1617}	4404	12.41	2026-10-14 04:47:31.009139+00
c9379173-7c14-4ff7-8589-b32165adbffe	1	FIRE_SMOKE	smoke	0.7495	{"x_min": 0.4119, "y_min": 0.4113, "x_max": 0.9845, "y_max": 0.9988}	4528	12.66	2026-10-14 04:47:41.206936+00
170cde02-a328-49f6-bd50-c5e47bd25a84	1	FIRE_SMOKE	person	0.6486495733261108	{"x_min": 0.3477, "y_min": 0.1146, "x_max": 0.4768, "y_max": 0.5784}	4580	11.63	2026-10-14 04:47:45.605071+00
1e5d2bc0-bdea-4bec-aee7-9a11b4e5dd83	1	FIRE_SMOKE	goggles	0.17336922883987427	{"x_min": 0.3528, "y_min": 0.0889, "x_max": 0.4194, "y_max": 0.2025}	4580	11.63	2026-10-14 04:47:45.605071+00
b0102baf-44cc-4d16-bdb9-f7950f0715a8	1	FIRE_SMOKE	goggles	0.15317395329475403	{"x_min": 0.3656, "y_min": 0.0865, "x_max": 0.4664, "y_max": 0.1677}	4580	11.63	2026-10-14 04:47:45.605071+00
5f23b3dc-f2e1-4d07-bee2-3a71ef985f2b	1	FIRE_SMOKE	person	0.6200188398361206	{"x_min": 0.4144, "y_min": 0.0841, "x_max": 0.5137, "y_max": 0.4937}	4644	10.9	2026-10-14 04:47:50.969266+00
a2e5ac2c-ad66-4456-b95b-1d2b16eac572	1	FIRE_SMOKE	person	0.8240303993225098	{"x_min": 0.4899, "y_min": 0.2466, "x_max": 0.5778, "y_max": 0.3687}	5024	11.98	2026-10-14 04:48:22.606749+00
c3323bac-20c9-46ef-8e7f-f321d376d06f	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.498, "y_min": 0.2584, "x_max": 0.5685, "y_max": 0.2891}	5024	11.98	2026-10-14 04:48:22.606749+00
a95d237d-e6e1-4636-973f-6cbe0941f265	1	FIRE_SMOKE	gloves	0.3322054147720337	{"x_min": 0.4915, "y_min": 0.3068, "x_max": 0.5798, "y_max": 0.3576}	5024	11.98	2026-10-14 04:48:22.606749+00
db7bbd31-c1c2-4bba-8b91-ed9727f3de69	1	FIRE_SMOKE	person	0.5212283134460449	{"x_min": 0.4928, "y_min": 0.2464, "x_max": 0.5869, "y_max": 0.3605}	5100	12.61	2026-10-14 04:48:28.969971+00
2c6006b5-f210-4b3f-a47b-87619a58b351	1	FIRE_SMOKE	person	0.6035298705101013	{"x_min": 0.493, "y_min": 0.2466, "x_max": 0.5862, "y_max": 0.356}	5172	12.85	2026-10-14 04:48:35.121535+00
4d5acb57-d617-4982-9bf8-b15bb5e55560	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.5013, "y_min": 0.2572, "x_max": 0.5773, "y_max": 0.2843}	5172	12.85	2026-10-14 04:48:35.121535+00
e051fe26-6064-47fc-8cb2-18a2288ffa57	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.5013, "y_min": 0.2584, "x_max": 0.578, "y_max": 0.2891}	5300	12.13	2026-10-14 04:48:45.610771+00
0535dfba-4968-4e12-af1a-339b05cba8e6	1	FIRE_SMOKE	person	0.4913966953754425	{"x_min": 0.5131, "y_min": 0.2464, "x_max": 0.5842, "y_max": 0.3374}	5852	11.77	2026-10-14 04:49:31.618134+00
23357241-6b93-494b-b079-f894757cf4a1	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.5208, "y_min": 0.2554, "x_max": 0.5867, "y_max": 0.2776}	5924	15.99	2026-10-14 04:49:37.609647+00
777f3086-3b91-474d-bdd9-02c7d79ad83f	1	FIRE_SMOKE	person	0.9026402831077576	{"x_min": 0.4969, "y_min": 0.1834, "x_max": 0.5919, "y_max": 0.349}	2244	11.65	2026-10-14 04:44:29.173714+00
76354e5d-677e-4245-b6eb-629d6570d740	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.506, "y_min": 0.1995, "x_max": 0.582, "y_max": 0.241}	2244	11.65	2026-10-14 04:44:29.173714+00
14f4ab1e-f1f2-4a1b-b983-80b8a547d0d5	1	FIRE_SMOKE	person	0.8268747925758362	{"x_min": 0.4969, "y_min": 0.183, "x_max": 0.5975, "y_max": 0.349}	2308	12.67	2026-10-14 04:44:34.595333+00
be3300d3-0555-4dd5-b979-30e7f3afbb3b	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.5067, "y_min": 0.1989, "x_max": 0.5874, "y_max": 0.2404}	2308	12.67	2026-10-14 04:44:34.595333+00
6a90513a-930e-425a-bcf0-87ee86089344	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.5074, "y_min": 0.1995, "x_max": 0.588, "y_max": 0.241}	2476	11.99	2026-10-14 04:44:48.589015+00
3f7dd51e-ca92-450a-8b52-abe63e418ffe	1	FIRE_SMOKE	person	0.8695249557495117	{"x_min": 0.4978, "y_min": 0.1772, "x_max": 0.5846, "y_max": 0.349}	2640	12.6	2026-10-14 04:45:02.188511+00
223618d6-94bd-4362-9655-46a0034e44a4	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.5081, "y_min": 0.1863, "x_max": 0.5733, "y_max": 0.2151}	2640	12.6	2026-10-14 04:45:02.188511+00
869e6818-269d-432f-b58d-5b7277089e4f	1	FIRE_SMOKE	person	0.9486642479896545	{"x_min": 0.4978, "y_min": 0.1795, "x_max": 0.5911, "y_max": 0.349}	2784	12	2026-10-14 04:45:14.285276+00
593085b2-f664-486e-ab7b-91aaa5c1b0f8	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.5094, "y_min": 0.1887, "x_max": 0.5786, "y_max": 0.2169}	2784	12	2026-10-14 04:45:14.285276+00
66826f4c-bcba-4a28-bc71-fc5d2e7e2753	1	FIRE_SMOKE	person	0.9900000095367432	{"x_min": 0.4978, "y_min": 0.1815, "x_max": 0.5992, "y_max": 0.349}	2836	12.58	2026-10-14 04:45:18.886142+00
7950fe1b-2d7e-4689-a6fd-ce63ae1d8df7	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.5074, "y_min": 0.1971, "x_max": 0.5887, "y_max": 0.2392}	2836	12.58	2026-10-14 04:45:18.886142+00
6886636e-ac9e-4bb0-9ea1-bda463cd7cae	1	FIRE_SMOKE	person	0.9900000095367432	{"x_min": 0.4978, "y_min": 0.1795, "x_max": 0.5881, "y_max": 0.3487}	3012	12	2026-10-14 04:45:35.106771+00
89621884-1073-44ee-ba8d-d9a97a7242f2	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.5081, "y_min": 0.1887, "x_max": 0.5773, "y_max": 0.2169}	3012	12	2026-10-14 04:45:35.106771+00
4d963df0-d4a2-47b0-9ec7-1f7c5e9df04a	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.5094, "y_min": 0.1869, "x_max": 0.5806, "y_max": 0.2157}	3156	12.83	2026-10-14 04:45:46.985153+00
b01d558c-7578-4c18-95c0-3345866b3827	1	FIRE_SMOKE	person	0.6616394519805908	{"x_min": 0.5957, "y_min": 0.2355, "x_max": 0.7428, "y_max": 0.7563}	4236	12.52	2026-10-14 04:47:17.008942+00
a497b42b-25c3-4e2d-8daf-1a8c403a52bc	1	FIRE_SMOKE	goggles	0.394456148147583	{"x_min": 0.5813, "y_min": 0.2566, "x_max": 0.6478, "y_max": 0.39}	4236	12.52	2026-10-14 04:47:17.008942+00
31c01eba-e53c-4c70-b751-65e42d4e56d9	1	FIRE_SMOKE	goggles	0.3791672885417938	{"x_min": 0.6324, "y_min": 0.2037, "x_max": 0.7406, "y_max": 0.2788}	4236	12.52	2026-10-14 04:47:17.008942+00
f23b84e2-0156-414b-b298-806151d0fd6d	1	FIRE_SMOKE	goggles	0.3442608714103699	{"x_min": 0.5827, "y_min": 0.2043, "x_max": 0.664, "y_max": 0.3077}	4236	12.52	2026-10-14 04:47:17.008942+00
366b51f2-b578-4efc-9b8d-6f1e0a2cd661	1	FIRE_SMOKE	smoke	0.778	{"x_min": 0.4167, "y_min": 0.4016, "x_max": 0.9781, "y_max": 1.0}	4320	11.11	2026-10-14 04:47:24.011893+00
c18d78cc-77cf-40e6-b595-a6c17e34e7ac	1	FIRE_SMOKE	person	0.9900000095367432	{"x_min": 0.3129, "y_min": 0.0983, "x_max": 0.4449, "y_max": 0.5292}	4364	12.44	2026-10-14 04:47:27.688644+00
042e793c-5064-48ae-85ea-41c1b0425a0c	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.3293, "y_min": 0.1232, "x_max": 0.4281, "y_max": 0.1941}	4364	12.44	2026-10-14 04:47:27.688644+00
bdfe1996-6356-4c0e-a8c3-2c470d384488	1	FIRE_SMOKE	gloves	0.24764704704284668	{"x_min": 0.3078, "y_min": 0.1623, "x_max": 0.4419, "y_max": 0.3767}	4364	12.44	2026-10-14 04:47:27.688644+00
5abdecb3-7b0a-49e4-8b57-3043c5013b80	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.3226, "y_min": 0.1292, "x_max": 0.4267, "y_max": 0.2019}	4436	11.92	2026-10-14 04:47:33.689165+00
95d6f145-8989-49f8-8752-3594516c722f	1	FIRE_SMOKE	smoke	0.7926	{"x_min": 0.411, "y_min": 0.413, "x_max": 0.9818, "y_max": 1.0}	4540	11.96	2026-10-14 04:47:42.206984+00
c43e04a1-f00d-4467-af9e-883379f91151	1	FIRE_SMOKE	person	0.9338268637657166	{"x_min": 0.3159, "y_min": 0.1112, "x_max": 0.4609, "y_max": 0.5801}	4620	12	2026-10-14 04:47:48.969061+00
4fdf6254-c507-45f6-8a69-5bdb18ac640d	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.334, "y_min": 0.1388, "x_max": 0.4422, "y_max": 0.2157}	4620	12	2026-10-14 04:47:48.969061+00
43cb4576-d994-4d0d-8af9-0f77ff3731ef	1	FIRE_SMOKE	gloves	0.4049411416053772	{"x_min": 0.3105, "y_min": 0.1821, "x_max": 0.4563, "y_max": 0.4237}	4620	12	2026-10-14 04:47:48.969061+00
53ee2a65-aaaf-4ca7-a2e4-1711aebbd76b	1	FIRE_SMOKE	person	0.44239264726638794	{"x_min": 0.4933, "y_min": 0.2464, "x_max": 0.5905, "y_max": 0.3539}	4956	12.14	2026-10-14 04:48:16.968061+00
a0f7910d-cf6c-4004-adc6-ab65ecea9a0f	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.498, "y_min": 0.2584, "x_max": 0.5685, "y_max": 0.2891}	5064	12.12	2026-10-14 04:48:25.972679+00
89f81b60-553e-4f57-99dc-027ea48eae1c	1	FIRE_SMOKE	person	0.5126574635505676	{"x_min": 0.4928, "y_min": 0.2466, "x_max": 0.5879, "y_max": 0.3745}	5140	12.58	2026-10-14 04:48:32.207317+00
c4d50c69-c3b1-44e1-b323-00072bf54f6e	1	FIRE_SMOKE	person	0.5359483361244202	{"x_min": 0.492, "y_min": 0.2466, "x_max": 0.5877, "y_max": 0.3694}	5268	11.86	2026-10-14 04:48:42.976466+00
69c1904f-a5f6-45e6-8f53-9c6ce437e69e	1	FIRE_SMOKE	smoke	0.7578	{"x_min": 0.4123, "y_min": 0.412, "x_max": 0.9884, "y_max": 1.0}	5436	11.97	2026-10-14 04:48:56.970283+00
9b261a8c-25ad-49b6-8f6d-8e774444c454	1	FIRE_SMOKE	person	0.5085754990577698	{"x_min": 0.5127, "y_min": 0.2464, "x_max": 0.5997, "y_max": 0.3374}	5880	11.85	2026-10-14 04:49:33.969956+00
f843a222-d6b5-4943-a025-17bb623f480f	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.5208, "y_min": 0.2554, "x_max": 0.5907, "y_max": 0.2776}	5880	11.85	2026-10-14 04:49:33.969956+00
ffbebcd7-ad82-426f-b261-82457ea40da3	1	FIRE_SMOKE	person	0.5755242109298706	{"x_min": 0.4783, "y_min": 0.2131, "x_max": 0.5563, "y_max": 0.2965}	6240	12.46	2026-10-14 04:50:03.971431+00
ef9d0922-c79b-4331-8ddf-f6ac9bd2ad45	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4852, "y_min": 0.2206, "x_max": 0.5484, "y_max": 0.2416}	6240	12.46	2026-10-14 04:50:03.971431+00
1e84e579-7b6d-42d0-a4cc-45fd034d13b7	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4852, "y_min": 0.2206, "x_max": 0.5484, "y_max": 0.2416}	6268	12.91	2026-10-14 04:50:06.214177+00
64f7751a-f4dd-44e1-96f8-bbb146c29901	1	FIRE_SMOKE	gloves	0.2170686423778534	{"x_min": 0.4751, "y_min": 0.2248, "x_max": 0.5068, "y_max": 0.2706}	6268	12.91	2026-10-14 04:50:06.214177+00
9ac6a793-c707-4665-9ecd-7f499839067c	1	FIRE_SMOKE	person	0.5803213119506836	{"x_min": 0.4803, "y_min": 0.2129, "x_max": 0.5572, "y_max": 0.2965}	6344	12.16	2026-10-14 04:50:12.607166+00
d6eb2976-4c27-4065-82ac-2f9d559eaeb2	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4872, "y_min": 0.2206, "x_max": 0.5497, "y_max": 0.2416}	6344	12.16	2026-10-14 04:50:12.607166+00
0e425a4d-7c9c-471f-8c50-188704c06d53	1	FIRE_SMOKE	gloves	0.2202858030796051	{"x_min": 0.4772, "y_min": 0.2248, "x_max": 0.5095, "y_max": 0.2712}	6344	12.16	2026-10-14 04:50:12.607166+00
06798ac2-c5c1-4820-926f-8949af4e23f4	1	FIRE_SMOKE	person	0.4946381449699402	{"x_min": 0.4813, "y_min": 0.2131, "x_max": 0.5584, "y_max": 0.2965}	6372	11.84	2026-10-14 04:50:14.968422+00
14cb89a4-1869-424f-84e5-3f71826cb7f5	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4879, "y_min": 0.2206, "x_max": 0.5504, "y_max": 0.2416}	6412	14.71	2026-10-14 04:50:18.209298+00
be2d7cac-fe34-49c0-b12b-ef4474ecbcdd	1	FIRE_SMOKE	gloves	0.2559680640697479	{"x_min": 0.4791, "y_min": 0.2248, "x_max": 0.5144, "y_max": 0.2742}	6412	14.71	2026-10-14 04:50:18.209298+00
990fa1ad-d843-43c4-b874-f9221fea9efc	1	FIRE_SMOKE	person	0.6389968395233154	{"x_min": 0.4891, "y_min": 0.2129, "x_max": 0.5584, "y_max": 0.2967}	6564	12	2026-10-14 04:50:30.969933+00
e714c4ae-c865-4e83-9a38-cce2474165b6	1	FIRE_SMOKE	goggles	0.96	{"x_min": 0.4953, "y_min": 0.2206, "x_max": 0.5511, "y_max": 0.2416}	6564	12	2026-10-14 04:50:30.969933+00
95e7288d-71a8-4633-9671-41fcb6796b8c	1	FIRE_SMOKE	gloves	0.32236525416374207	{"x_min": 0.4872, "y_min": 0.2265, "x_max": 0.5281, "y_max": 0.2742}	6564	12	2026-10-14 04:50:30.969933+00
\.


--
-- Data for Name: dvrs; Type: TABLE DATA; Schema: public; Owner: cctv_user
--

COPY public.dvrs (id, name, management_host, management_port, rtsp_port, username, credential_reference, manufacturer, channels_count, enabled, status, last_health_check_at, last_successful_health_check_at, health_check_error, version_id, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: evidence; Type: TABLE DATA; Schema: public; Owner: cctv_user
--

COPY public.evidence (id, evidence_id, alert_id, camera_id, organization_id, site_id, snapshot_relative_path, video_relative_path, metadata_relative_path, file_size_bytes, metadata_envelope, retention_until, created_at) FROM stdin;
63deda91-d067-41ad-9123-d7ffaee23049	ev_6eb167cd3f55	test_ev_d71d49	1	\N	\N	CAM-01/2026-10-15/no_helmet_114022_7a5b848a.jpg	CAM-01/2026-10-15/no_helmet_114022_7a5b848a.mp4	\N	15027	{"evidence_id": "ev_6eb167cd3f55", "event_id": "test_ev_d71d49", "camera_id": 1, "camera_name": "hall", "class_name": "no_helmet", "confidence": 0.95, "timestamp": "2026-10-15T11:40:22.954156", "bounding_box": null, "frame_info": {"fps": 25.0}, "snapshot_file": "no_helmet_114022_7a5b848a.jpg", "video_file": "no_helmet_114022_7a5b848a.mp4"}	\N	2026-10-15 11:40:22.954156+00
\.


--
-- Data for Name: incidents; Type: TABLE DATA; Schema: public; Owner: cctv_user
--

COPY public.incidents (id, camera_id, zone_id, organization_id, site_id, incident_type, events, severity, status, person_id, evidence_id, start_time, cleared_time, metadata_json, created_at, updated_at) FROM stdin;
inc_199390a5a3e3	1	\N	\N	\N	ZONE_VIOLATION	["SMOKE_DETECTED", "PPE_VIOLATION"]	CRITICAL	ACTIVE	109	\N	2026-10-13 09:44:03.06606+00	\N	{}	2026-10-13 09:44:06.222158+00	2026-10-13 09:44:06.222163+00
inc_d1829dc103ba	1	\N	\N	\N	ZONE_VIOLATION	["SMOKE_DETECTED", "PPE_VIOLATION"]	CRITICAL	ACTIVE	113	\N	2026-10-13 09:46:29.135591+00	\N	{}	2026-10-13 09:46:31.856689+00	2026-10-13 09:46:31.856692+00
\.


--
-- Data for Name: licenses; Type: TABLE DATA; Schema: public; Owner: cctv_user
--

COPY public.licenses (id, organization_id, license_key, tier, max_cameras, enabled_modules, status, expires_at, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: notifications; Type: TABLE DATA; Schema: public; Owner: cctv_user
--

COPY public.notifications (id, alert_id, channel, recipient, status, error_message, sent_at) FROM stdin;
notif_a7cc865e41ee	04bb3d81-4abf-4066-8146-e434286ca957	email	admin@aicctv.local	DELIVERED	\N	2026-10-13 09:44:39.775373+00
notif_7e906bd76337	a30c037b-62f7-49f6-8f07-323f3724f658	email	admin@aicctv.local	DELIVERED	\N	2026-10-13 09:47:03.613539+00
notif_a7c357e78b6d	ppe_evt_de7c046000	email	admin@aicctv.local	DELIVERED	\N	2026-10-14 04:20:58.160657+00
notif_7b568d3efe38	ppe_evt_da92ec3b31	email	admin@aicctv.local	DELIVERED	\N	2026-10-14 04:30:06.055667+00
notif_f7fdb941e546	ppe_evt_f25dad12a0	email	admin@aicctv.local	DELIVERED	\N	2026-10-14 04:33:24.326602+00
notif_74860805c086	ppe_evt_acf4543c37	email	admin@aicctv.local	DELIVERED	\N	2026-10-14 04:37:27.322985+00
notif_1a43440e7c17	ppe_evt_4c243f0790	email	admin@aicctv.local	DELIVERED	\N	2026-10-14 04:43:46.873644+00
notif_14c731d86875	ppe_evt_d0a84191ee	email	admin@aicctv.local	DELIVERED	\N	2026-10-14 04:45:13.24701+00
\.


--
-- Data for Name: organization_users; Type: TABLE DATA; Schema: public; Owner: cctv_user
--

COPY public.organization_users (id, organization_id, user_id, role, created_at) FROM stdin;
\.


--
-- Data for Name: organizations; Type: TABLE DATA; Schema: public; Owner: cctv_user
--

COPY public.organizations (id, name, slug, is_active, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: person_detections; Type: TABLE DATA; Schema: public; Owner: cctv_user
--

COPY public.person_detections (id, camera_id, person_id, bounding_box, confidence, "timestamp") FROM stdin;
\.


--
-- Data for Name: ppe_profiles; Type: TABLE DATA; Schema: public; Owner: cctv_user
--

COPY public.ppe_profiles (id, name, description, required_equipment, optional_equipment, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: ppe_requirements; Type: TABLE DATA; Schema: public; Owner: cctv_user
--

COPY public.ppe_requirements (id, profile_id, equipment_type, is_required, severity, created_at) FROM stdin;
\.


--
-- Data for Name: ppe_violations; Type: TABLE DATA; Schema: public; Owner: cctv_user
--

COPY public.ppe_violations (id, camera_id, zone_id, person_id, profile_id, status, severity, missing_items, detected_items, required_items, confidence, "timestamp", evidence_id, created_at) FROM stdin;
violation_988995607a38	1	\N	114	\N	VIOLATION	HIGH	["vest"]	["goggles"]	["vest", "goggles"]	0.96	2026-10-14 04:20:16.858604+00	\N	2026-10-14 04:20:19.497551+00
violation_b1ab65ebc7a0	1	\N	128	\N	VIOLATION	HIGH	["vest"]	["goggles"]	["vest", "goggles"]	0.8464	2026-10-14 04:29:30.625264+00	\N	2026-10-14 04:29:33.97391+00
violation_59d7e026a0c4	1	\N	133	\N	VIOLATION	HIGH	["vest"]	["goggles", "gloves"]	["vest", "goggles"]	0.96	2026-10-14 04:32:43.841291+00	\N	2026-10-14 04:32:47.736248+00
violation_50f4a690c366	1	\N	147	\N	VIOLATION	HIGH	["vest"]	["goggles", "gloves"]	["vest", "goggles"]	0.96	2026-10-14 04:37:01.067755+00	\N	2026-10-14 04:37:04.988011+00
violation_ab4bf11eb16b	1	\N	104	\N	VIOLATION	HIGH	["vest"]	["goggles"]	["vest", "goggles"]	0.96	2026-10-14 04:43:18.788338+00	\N	2026-10-14 04:43:22.425346+00
violation_90c9ae555bae	1	\N	105	\N	VIOLATION	HIGH	["vest"]	["goggles"]	["vest", "goggles"]	0.96	2026-10-14 04:44:29.173714+00	\N	2026-10-14 04:44:34.439846+00
\.


--
-- Data for Name: refresh_tokens; Type: TABLE DATA; Schema: public; Owner: cctv_user
--

COPY public.refresh_tokens (id, family_id, user_id, token_hash, expires_at, is_revoked, replaced_by_id, created_at) FROM stdin;
42a0a836-072e-4b18-9444-8a6645190ed6	ed8faef8-81b4-48ba-9f3f-46592a4671f8	7cfa0577-7f0e-4a34-91db-730773f49c61	6caecdaa021f1fea2d3e55469c950f22ce1c3e034a494a2bae5fa87dc5ec458f	2026-10-19 11:07:14.448655+00	t	96c27468-d49f-49b5-a4ba-2395a53cd56c	2026-10-12 11:07:14.44992+00
3000feb7-343b-4ba1-b559-7504bc7221c2	f58597b5-35bc-4731-9863-362549d0c39e	7cfa0577-7f0e-4a34-91db-730773f49c61	20f0b9956b1b088efab40f518837d2692051c8572efed67db4e19822c64d9d85	2026-10-21 07:31:10.335193+00	t	a1147f05-042a-46d6-b861-4ef4c4cd47f8	2026-10-14 07:31:10.337165+00
309b8453-c5af-433a-9017-1fe446e08a66	ed8faef8-81b4-48ba-9f3f-46592a4671f8	7cfa0577-7f0e-4a34-91db-730773f49c61	2fea35b40bcc3e19c4cd18ed61f2776ab182c48c620d522d8ee2f08566ff1c81	2026-10-19 12:09:13.152721+00	f	\N	2026-10-12 12:09:13.154225+00
96c27468-d49f-49b5-a4ba-2395a53cd56c	ed8faef8-81b4-48ba-9f3f-46592a4671f8	7cfa0577-7f0e-4a34-91db-730773f49c61	2ad3bc7083196135b451391764bf67d5f82bc00b0327186bc3c8e793146b4e63	2026-10-19 11:38:13.162359+00	t	37140dd0-d4e6-43bd-933c-a7394c593fa5	2026-10-12 11:38:13.16593+00
37140dd0-d4e6-43bd-933c-a7394c593fa5	ed8faef8-81b4-48ba-9f3f-46592a4671f8	7cfa0577-7f0e-4a34-91db-730773f49c61	2fef86d8f8d6e88a148aac59b1dd8aabfc002b6a3e9c19c0a2283645908894e2	2026-10-19 12:09:13.154704+00	f	\N	2026-10-12 12:09:13.157914+00
e50eed73-28f6-474b-b01f-d37fc485b8b3	cdff9ba5-45cc-4ebf-98c0-442d42bed815	7cfa0577-7f0e-4a34-91db-730773f49c61	8dcbf6d90e734cf8f5ea22f16c06c1bf7f605c388a1e2941624350ad99b7d866	2026-10-20 07:16:09.436626+00	f	\N	2026-10-13 07:16:09.437964+00
7891c9b0-d729-4d18-84d1-ba34e07aa8b4	befbb36c-e952-439e-8356-1a73867e60f2	7cfa0577-7f0e-4a34-91db-730773f49c61	4776f6ce37ad91af640c3b477a256f6967d25199d5f538794bb7d028b535fc31	2026-10-20 07:19:42.011211+00	f	\N	2026-10-13 07:19:42.01199+00
2e27ffc5-d6cd-4a07-b37a-eb5d719afabe	f58597b5-35bc-4731-9863-362549d0c39e	7cfa0577-7f0e-4a34-91db-730773f49c61	c5268f0198013d0395ef443c957815a1104ceaf7fbba299cc3398b79647c139c	2026-10-20 07:12:46.210062+00	t	fa1aeb59-e69b-4b72-a065-dd96bf061cdf	2026-10-13 07:12:46.220701+00
fa1aeb59-e69b-4b72-a065-dd96bf061cdf	f58597b5-35bc-4731-9863-362549d0c39e	7cfa0577-7f0e-4a34-91db-730773f49c61	3670519f618e4820c7808633ee63a951c4f3c1c9fe02f709c62603d65c4832ea	2026-10-20 07:44:11.59902+00	t	3e29ce41-20e1-4d89-a829-48d141c6b679	2026-10-13 07:44:11.605742+00
3e29ce41-20e1-4d89-a829-48d141c6b679	f58597b5-35bc-4731-9863-362549d0c39e	7cfa0577-7f0e-4a34-91db-730773f49c61	b1f67e47875f902ae99c646816114d758ba8d0ef652a9b923ef262e8f0904226	2026-10-20 08:14:12.278607+00	t	841947e9-a7a6-4e11-9409-219183f5e4ed	2026-10-13 08:14:12.280828+00
841947e9-a7a6-4e11-9409-219183f5e4ed	f58597b5-35bc-4731-9863-362549d0c39e	7cfa0577-7f0e-4a34-91db-730773f49c61	1c6946a571a79e11da1a328133f2ab7c56c5ec3e77ffe96f980007314c179c1b	2026-10-20 08:45:12.435667+00	t	a62b18fe-5ba1-4e94-8421-ec70104789e5	2026-10-13 08:45:12.440792+00
e00fde65-8048-4c2d-bbf0-4e9b405f7bca	8f5848f0-da63-4eb9-a763-fe188f43264e	7cfa0577-7f0e-4a34-91db-730773f49c61	5810b4540ec7bc15dbe0065ee2d69bf8b46227b568c48db0a0fa5732507f182d	2026-10-21 04:26:03.260192+00	f	\N	2026-10-14 04:26:03.261444+00
a62b18fe-5ba1-4e94-8421-ec70104789e5	f58597b5-35bc-4731-9863-362549d0c39e	7cfa0577-7f0e-4a34-91db-730773f49c61	6df8bc6bbde3d4a9c7262273e9d3558e176f2669e1c3a63c94b51e5a8baa50dd	2026-10-20 09:18:12.353139+00	t	c85038f3-aa4c-4971-bd9e-b7444d628d03	2026-10-13 09:18:12.366953+00
c85038f3-aa4c-4971-bd9e-b7444d628d03	f58597b5-35bc-4731-9863-362549d0c39e	7cfa0577-7f0e-4a34-91db-730773f49c61	ad219fa21a752379dd4e4d328e661c5b13cf418176c27e7de3d4976031a4277b	2026-10-21 04:51:24.743742+00	t	e2b8618d-a3bc-4b4b-974b-940f5be10e0e	2026-10-14 04:51:24.760208+00
e2b8618d-a3bc-4b4b-974b-940f5be10e0e	f58597b5-35bc-4731-9863-362549d0c39e	7cfa0577-7f0e-4a34-91db-730773f49c61	2120a9caff11ca3a5f215fcc7c525371d84c706712b7e75e2fccda7a085eb657	2026-10-21 05:23:10.33033+00	t	048108e0-ff86-47d0-b706-24269e5af7b8	2026-10-14 05:23:10.333404+00
048108e0-ff86-47d0-b706-24269e5af7b8	f58597b5-35bc-4731-9863-362549d0c39e	7cfa0577-7f0e-4a34-91db-730773f49c61	416eba044c7a89b4986b4ccefb19ded5ab86a1edc4ebb8a49e3d647f4e6c19d3	2026-10-21 05:55:10.342527+00	t	8fbfb182-e656-44f1-9f36-49dae7461b1b	2026-10-14 05:55:10.344341+00
8fbfb182-e656-44f1-9f36-49dae7461b1b	f58597b5-35bc-4731-9863-362549d0c39e	7cfa0577-7f0e-4a34-91db-730773f49c61	9d471f69a2fdcc405acd97f7e272a2a68647153b1eaa770767c78299906e2941	2026-10-21 06:27:10.322144+00	t	4e7ce987-46b3-4425-b626-53a2a1338453	2026-10-14 06:27:10.326605+00
4e7ce987-46b3-4425-b626-53a2a1338453	f58597b5-35bc-4731-9863-362549d0c39e	7cfa0577-7f0e-4a34-91db-730773f49c61	15bc8da60a05b500bb7cb0f6db14d184828fcb119d45b528f5c6102eefb6c4f3	2026-10-21 06:59:10.338101+00	t	3000feb7-343b-4ba1-b559-7504bc7221c2	2026-10-14 06:59:10.342105+00
a1147f05-042a-46d6-b861-4ef4c4cd47f8	f58597b5-35bc-4731-9863-362549d0c39e	7cfa0577-7f0e-4a34-91db-730773f49c61	d7407b957b9ed8bcda7c15c69090bed4492cf285e3917680a5c742de24335bbb	2026-10-21 08:18:10.321461+00	t	15670c87-a97f-46bf-b07b-83c3d01fe988	2026-10-14 08:18:10.324314+00
15670c87-a97f-46bf-b07b-83c3d01fe988	f58597b5-35bc-4731-9863-362549d0c39e	7cfa0577-7f0e-4a34-91db-730773f49c61	19fbc29c42b5284443ef6a41a078095b917c6f02d2597b069b4658f0eb379ff2	2026-10-21 12:29:55.73609+00	f	\N	2026-10-14 12:29:55.758759+00
\.


--
-- Data for Name: safety_zones; Type: TABLE DATA; Schema: public; Owner: cctv_user
--

COPY public.safety_zones (id, camera_id, organization_id, site_id, name, zone_type, polygon_coordinates, ppe_profile_id, enabled, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: sites; Type: TABLE DATA; Schema: public; Owner: cctv_user
--

COPY public.sites (id, organization_id, name, address, is_active, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: system_logs; Type: TABLE DATA; Schema: public; Owner: cctv_user
--

COPY public.system_logs (id, level, module, message, correlation_id, camera_id, created_at) FROM stdin;
\.


--
-- Data for Name: users; Type: TABLE DATA; Schema: public; Owner: cctv_user
--

COPY public.users (id, username, email, hashed_password, full_name, role, is_active, is_superuser, organization_id, failed_login_attempts, locked_until, created_at, updated_at) FROM stdin;
7cfa0577-7f0e-4a34-91db-730773f49c61	admin	admin@aicctv.local	$argon2id$v=19$m=19456,t=2,p=1$JL/2MxGLpFQ3ICNTKxv85g$MstvsoqSGrEC1ntLzujM5fl2/2LirCT7jNZLSGOZGW4	System Administrator	ADMIN	t	t	\N	1	\N	2026-10-12 10:14:19.741522+00	2026-10-15 11:43:43.628733+00
\.


--
-- Name: cameras_id_seq; Type: SEQUENCE SET; Schema: public; Owner: cctv_user
--

SELECT pg_catalog.setval('public.cameras_id_seq', 1, true);


--
-- Name: dvrs_id_seq; Type: SEQUENCE SET; Schema: public; Owner: cctv_user
--

SELECT pg_catalog.setval('public.dvrs_id_seq', 1, false);


--
-- Name: ppe_profiles_id_seq; Type: SEQUENCE SET; Schema: public; Owner: cctv_user
--

SELECT pg_catalog.setval('public.ppe_profiles_id_seq', 1, false);


--
-- Name: ppe_requirements_id_seq; Type: SEQUENCE SET; Schema: public; Owner: cctv_user
--

SELECT pg_catalog.setval('public.ppe_requirements_id_seq', 1, false);


--
-- Name: safety_zones_id_seq; Type: SEQUENCE SET; Schema: public; Owner: cctv_user
--

SELECT pg_catalog.setval('public.safety_zones_id_seq', 1, false);


--
-- Name: alerts alerts_pkey; Type: CONSTRAINT; Schema: public; Owner: cctv_user
--

ALTER TABLE ONLY public.alerts
    ADD CONSTRAINT alerts_pkey PRIMARY KEY (id);


--
-- Name: audit_logs audit_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: cctv_user
--

ALTER TABLE ONLY public.audit_logs
    ADD CONSTRAINT audit_logs_pkey PRIMARY KEY (id);


--
-- Name: cameras cameras_pkey; Type: CONSTRAINT; Schema: public; Owner: cctv_user
--

ALTER TABLE ONLY public.cameras
    ADD CONSTRAINT cameras_pkey PRIMARY KEY (id);


--
-- Name: detections detections_pkey; Type: CONSTRAINT; Schema: public; Owner: cctv_user
--

ALTER TABLE ONLY public.detections
    ADD CONSTRAINT detections_pkey PRIMARY KEY (id);


--
-- Name: dvrs dvrs_name_key; Type: CONSTRAINT; Schema: public; Owner: cctv_user
--

ALTER TABLE ONLY public.dvrs
    ADD CONSTRAINT dvrs_name_key UNIQUE (name);


--
-- Name: dvrs dvrs_pkey; Type: CONSTRAINT; Schema: public; Owner: cctv_user
--

ALTER TABLE ONLY public.dvrs
    ADD CONSTRAINT dvrs_pkey PRIMARY KEY (id);


--
-- Name: evidence evidence_pkey; Type: CONSTRAINT; Schema: public; Owner: cctv_user
--

ALTER TABLE ONLY public.evidence
    ADD CONSTRAINT evidence_pkey PRIMARY KEY (id);


--
-- Name: incidents incidents_pkey; Type: CONSTRAINT; Schema: public; Owner: cctv_user
--

ALTER TABLE ONLY public.incidents
    ADD CONSTRAINT incidents_pkey PRIMARY KEY (id);


--
-- Name: licenses licenses_pkey; Type: CONSTRAINT; Schema: public; Owner: cctv_user
--

ALTER TABLE ONLY public.licenses
    ADD CONSTRAINT licenses_pkey PRIMARY KEY (id);


--
-- Name: notifications notifications_pkey; Type: CONSTRAINT; Schema: public; Owner: cctv_user
--

ALTER TABLE ONLY public.notifications
    ADD CONSTRAINT notifications_pkey PRIMARY KEY (id);


--
-- Name: organization_users organization_users_pkey; Type: CONSTRAINT; Schema: public; Owner: cctv_user
--

ALTER TABLE ONLY public.organization_users
    ADD CONSTRAINT organization_users_pkey PRIMARY KEY (id);


--
-- Name: organizations organizations_pkey; Type: CONSTRAINT; Schema: public; Owner: cctv_user
--

ALTER TABLE ONLY public.organizations
    ADD CONSTRAINT organizations_pkey PRIMARY KEY (id);


--
-- Name: person_detections person_detections_pkey; Type: CONSTRAINT; Schema: public; Owner: cctv_user
--

ALTER TABLE ONLY public.person_detections
    ADD CONSTRAINT person_detections_pkey PRIMARY KEY (id);


--
-- Name: ppe_profiles ppe_profiles_pkey; Type: CONSTRAINT; Schema: public; Owner: cctv_user
--

ALTER TABLE ONLY public.ppe_profiles
    ADD CONSTRAINT ppe_profiles_pkey PRIMARY KEY (id);


--
-- Name: ppe_requirements ppe_requirements_pkey; Type: CONSTRAINT; Schema: public; Owner: cctv_user
--

ALTER TABLE ONLY public.ppe_requirements
    ADD CONSTRAINT ppe_requirements_pkey PRIMARY KEY (id);


--
-- Name: ppe_violations ppe_violations_pkey; Type: CONSTRAINT; Schema: public; Owner: cctv_user
--

ALTER TABLE ONLY public.ppe_violations
    ADD CONSTRAINT ppe_violations_pkey PRIMARY KEY (id);


--
-- Name: refresh_tokens refresh_tokens_pkey; Type: CONSTRAINT; Schema: public; Owner: cctv_user
--

ALTER TABLE ONLY public.refresh_tokens
    ADD CONSTRAINT refresh_tokens_pkey PRIMARY KEY (id);


--
-- Name: safety_zones safety_zones_pkey; Type: CONSTRAINT; Schema: public; Owner: cctv_user
--

ALTER TABLE ONLY public.safety_zones
    ADD CONSTRAINT safety_zones_pkey PRIMARY KEY (id);


--
-- Name: sites sites_pkey; Type: CONSTRAINT; Schema: public; Owner: cctv_user
--

ALTER TABLE ONLY public.sites
    ADD CONSTRAINT sites_pkey PRIMARY KEY (id);


--
-- Name: system_logs system_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: cctv_user
--

ALTER TABLE ONLY public.system_logs
    ADD CONSTRAINT system_logs_pkey PRIMARY KEY (id);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: cctv_user
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: idx_alerts_camera_state; Type: INDEX; Schema: public; Owner: cctv_user
--

CREATE INDEX idx_alerts_camera_state ON public.alerts USING btree (camera_id, state);


--
-- Name: idx_alerts_class_start; Type: INDEX; Schema: public; Owner: cctv_user
--

CREATE INDEX idx_alerts_class_start ON public.alerts USING btree (class_name, start_time);


--
-- Name: idx_audit_logs_actor_time; Type: INDEX; Schema: public; Owner: cctv_user
--

CREATE INDEX idx_audit_logs_actor_time ON public.audit_logs USING btree (actor_id, created_at);


--
-- Name: idx_audit_logs_event_time; Type: INDEX; Schema: public; Owner: cctv_user
--

CREATE INDEX idx_audit_logs_event_time ON public.audit_logs USING btree (event_type, created_at);


--
-- Name: idx_camera_dvr_channel; Type: INDEX; Schema: public; Owner: cctv_user
--

CREATE INDEX idx_camera_dvr_channel ON public.cameras USING btree (dvr_id, dvr_channel);


--
-- Name: idx_camera_dvr_id; Type: INDEX; Schema: public; Owner: cctv_user
--

CREATE INDEX idx_camera_dvr_id ON public.cameras USING btree (dvr_id);


--
-- Name: idx_camera_priority; Type: INDEX; Schema: public; Owner: cctv_user
--

CREATE INDEX idx_camera_priority ON public.cameras USING btree (priority);


--
-- Name: idx_detections_camera_time; Type: INDEX; Schema: public; Owner: cctv_user
--

CREATE INDEX idx_detections_camera_time ON public.detections USING btree (camera_id, "timestamp");


--
-- Name: idx_detections_class_conf; Type: INDEX; Schema: public; Owner: cctv_user
--

CREATE INDEX idx_detections_class_conf ON public.detections USING btree (class_name, confidence);


--
-- Name: idx_dvr_mgmt_host; Type: INDEX; Schema: public; Owner: cctv_user
--

CREATE INDEX idx_dvr_mgmt_host ON public.dvrs USING btree (management_host);


--
-- Name: idx_dvr_status; Type: INDEX; Schema: public; Owner: cctv_user
--

CREATE INDEX idx_dvr_status ON public.dvrs USING btree (status);


--
-- Name: idx_evidence_camera_retention; Type: INDEX; Schema: public; Owner: cctv_user
--

CREATE INDEX idx_evidence_camera_retention ON public.evidence USING btree (camera_id, retention_until);


--
-- Name: idx_incidents_cam_type_status; Type: INDEX; Schema: public; Owner: cctv_user
--

CREATE INDEX idx_incidents_cam_type_status ON public.incidents USING btree (camera_id, incident_type, status);


--
-- Name: idx_incidents_sev_start; Type: INDEX; Schema: public; Owner: cctv_user
--

CREATE INDEX idx_incidents_sev_start ON public.incidents USING btree (severity, start_time);


--
-- Name: idx_logs_level_time; Type: INDEX; Schema: public; Owner: cctv_user
--

CREATE INDEX idx_logs_level_time ON public.system_logs USING btree (level, created_at);


--
-- Name: idx_notifications_status_time; Type: INDEX; Schema: public; Owner: cctv_user
--

CREATE INDEX idx_notifications_status_time ON public.notifications USING btree (status, sent_at);


--
-- Name: idx_org_user_unique; Type: INDEX; Schema: public; Owner: cctv_user
--

CREATE UNIQUE INDEX idx_org_user_unique ON public.organization_users USING btree (organization_id, user_id);


--
-- Name: idx_person_dets_cam_person; Type: INDEX; Schema: public; Owner: cctv_user
--

CREATE INDEX idx_person_dets_cam_person ON public.person_detections USING btree (camera_id, person_id);


--
-- Name: idx_person_dets_cam_time; Type: INDEX; Schema: public; Owner: cctv_user
--

CREATE INDEX idx_person_dets_cam_time ON public.person_detections USING btree (camera_id, "timestamp");


--
-- Name: idx_ppe_req_profile_equip; Type: INDEX; Schema: public; Owner: cctv_user
--

CREATE INDEX idx_ppe_req_profile_equip ON public.ppe_requirements USING btree (profile_id, equipment_type);


--
-- Name: idx_ppe_viol_cam_time; Type: INDEX; Schema: public; Owner: cctv_user
--

CREATE INDEX idx_ppe_viol_cam_time ON public.ppe_violations USING btree (camera_id, "timestamp");


--
-- Name: idx_ppe_viol_status_sev; Type: INDEX; Schema: public; Owner: cctv_user
--

CREATE INDEX idx_ppe_viol_status_sev ON public.ppe_violations USING btree (status, severity);


--
-- Name: idx_refresh_tokens_user_family; Type: INDEX; Schema: public; Owner: cctv_user
--

CREATE INDEX idx_refresh_tokens_user_family ON public.refresh_tokens USING btree (user_id, family_id);


--
-- Name: idx_safety_zone_cam_type; Type: INDEX; Schema: public; Owner: cctv_user
--

CREATE INDEX idx_safety_zone_cam_type ON public.safety_zones USING btree (camera_id, zone_type);


--
-- Name: ix_alerts_camera_id; Type: INDEX; Schema: public; Owner: cctv_user
--

CREATE INDEX ix_alerts_camera_id ON public.alerts USING btree (camera_id);


--
-- Name: ix_alerts_class_name; Type: INDEX; Schema: public; Owner: cctv_user
--

CREATE INDEX ix_alerts_class_name ON public.alerts USING btree (class_name);


--
-- Name: ix_alerts_module; Type: INDEX; Schema: public; Owner: cctv_user
--

CREATE INDEX ix_alerts_module ON public.alerts USING btree (module);


--
-- Name: ix_alerts_organization_id; Type: INDEX; Schema: public; Owner: cctv_user
--

CREATE INDEX ix_alerts_organization_id ON public.alerts USING btree (organization_id);


--
-- Name: ix_alerts_site_id; Type: INDEX; Schema: public; Owner: cctv_user
--

CREATE INDEX ix_alerts_site_id ON public.alerts USING btree (site_id);


--
-- Name: ix_alerts_start_time; Type: INDEX; Schema: public; Owner: cctv_user
--

CREATE INDEX ix_alerts_start_time ON public.alerts USING btree (start_time);


--
-- Name: ix_alerts_state; Type: INDEX; Schema: public; Owner: cctv_user
--

CREATE INDEX ix_alerts_state ON public.alerts USING btree (state);


--
-- Name: ix_audit_logs_actor_id; Type: INDEX; Schema: public; Owner: cctv_user
--

CREATE INDEX ix_audit_logs_actor_id ON public.audit_logs USING btree (actor_id);


--
-- Name: ix_audit_logs_created_at; Type: INDEX; Schema: public; Owner: cctv_user
--

CREATE INDEX ix_audit_logs_created_at ON public.audit_logs USING btree (created_at);


--
-- Name: ix_audit_logs_event_type; Type: INDEX; Schema: public; Owner: cctv_user
--

CREATE INDEX ix_audit_logs_event_type ON public.audit_logs USING btree (event_type);


--
-- Name: ix_audit_logs_status; Type: INDEX; Schema: public; Owner: cctv_user
--

CREATE INDEX ix_audit_logs_status ON public.audit_logs USING btree (status);


--
-- Name: ix_audit_logs_username; Type: INDEX; Schema: public; Owner: cctv_user
--

CREATE INDEX ix_audit_logs_username ON public.audit_logs USING btree (username);


--
-- Name: ix_cameras_organization_id; Type: INDEX; Schema: public; Owner: cctv_user
--

CREATE INDEX ix_cameras_organization_id ON public.cameras USING btree (organization_id);


--
-- Name: ix_cameras_site_id; Type: INDEX; Schema: public; Owner: cctv_user
--

CREATE INDEX ix_cameras_site_id ON public.cameras USING btree (site_id);


--
-- Name: ix_detections_camera_id; Type: INDEX; Schema: public; Owner: cctv_user
--

CREATE INDEX ix_detections_camera_id ON public.detections USING btree (camera_id);


--
-- Name: ix_detections_class_name; Type: INDEX; Schema: public; Owner: cctv_user
--

CREATE INDEX ix_detections_class_name ON public.detections USING btree (class_name);


--
-- Name: ix_detections_module; Type: INDEX; Schema: public; Owner: cctv_user
--

CREATE INDEX ix_detections_module ON public.detections USING btree (module);


--
-- Name: ix_detections_timestamp; Type: INDEX; Schema: public; Owner: cctv_user
--

CREATE INDEX ix_detections_timestamp ON public.detections USING btree ("timestamp");


--
-- Name: ix_evidence_alert_id; Type: INDEX; Schema: public; Owner: cctv_user
--

CREATE INDEX ix_evidence_alert_id ON public.evidence USING btree (alert_id);


--
-- Name: ix_evidence_camera_id; Type: INDEX; Schema: public; Owner: cctv_user
--

CREATE INDEX ix_evidence_camera_id ON public.evidence USING btree (camera_id);


--
-- Name: ix_evidence_evidence_id; Type: INDEX; Schema: public; Owner: cctv_user
--

CREATE UNIQUE INDEX ix_evidence_evidence_id ON public.evidence USING btree (evidence_id);


--
-- Name: ix_evidence_organization_id; Type: INDEX; Schema: public; Owner: cctv_user
--

CREATE INDEX ix_evidence_organization_id ON public.evidence USING btree (organization_id);


--
-- Name: ix_evidence_retention_until; Type: INDEX; Schema: public; Owner: cctv_user
--

CREATE INDEX ix_evidence_retention_until ON public.evidence USING btree (retention_until);


--
-- Name: ix_evidence_site_id; Type: INDEX; Schema: public; Owner: cctv_user
--

CREATE INDEX ix_evidence_site_id ON public.evidence USING btree (site_id);


--
-- Name: ix_incidents_camera_id; Type: INDEX; Schema: public; Owner: cctv_user
--

CREATE INDEX ix_incidents_camera_id ON public.incidents USING btree (camera_id);


--
-- Name: ix_incidents_incident_type; Type: INDEX; Schema: public; Owner: cctv_user
--

CREATE INDEX ix_incidents_incident_type ON public.incidents USING btree (incident_type);


--
-- Name: ix_incidents_organization_id; Type: INDEX; Schema: public; Owner: cctv_user
--

CREATE INDEX ix_incidents_organization_id ON public.incidents USING btree (organization_id);


--
-- Name: ix_incidents_severity; Type: INDEX; Schema: public; Owner: cctv_user
--

CREATE INDEX ix_incidents_severity ON public.incidents USING btree (severity);


--
-- Name: ix_incidents_site_id; Type: INDEX; Schema: public; Owner: cctv_user
--

CREATE INDEX ix_incidents_site_id ON public.incidents USING btree (site_id);


--
-- Name: ix_incidents_start_time; Type: INDEX; Schema: public; Owner: cctv_user
--

CREATE INDEX ix_incidents_start_time ON public.incidents USING btree (start_time);


--
-- Name: ix_incidents_status; Type: INDEX; Schema: public; Owner: cctv_user
--

CREATE INDEX ix_incidents_status ON public.incidents USING btree (status);


--
-- Name: ix_incidents_zone_id; Type: INDEX; Schema: public; Owner: cctv_user
--

CREATE INDEX ix_incidents_zone_id ON public.incidents USING btree (zone_id);


--
-- Name: ix_licenses_license_key; Type: INDEX; Schema: public; Owner: cctv_user
--

CREATE UNIQUE INDEX ix_licenses_license_key ON public.licenses USING btree (license_key);


--
-- Name: ix_licenses_organization_id; Type: INDEX; Schema: public; Owner: cctv_user
--

CREATE UNIQUE INDEX ix_licenses_organization_id ON public.licenses USING btree (organization_id);


--
-- Name: ix_notifications_alert_id; Type: INDEX; Schema: public; Owner: cctv_user
--

CREATE INDEX ix_notifications_alert_id ON public.notifications USING btree (alert_id);


--
-- Name: ix_notifications_sent_at; Type: INDEX; Schema: public; Owner: cctv_user
--

CREATE INDEX ix_notifications_sent_at ON public.notifications USING btree (sent_at);


--
-- Name: ix_notifications_status; Type: INDEX; Schema: public; Owner: cctv_user
--

CREATE INDEX ix_notifications_status ON public.notifications USING btree (status);


--
-- Name: ix_organization_users_organization_id; Type: INDEX; Schema: public; Owner: cctv_user
--

CREATE INDEX ix_organization_users_organization_id ON public.organization_users USING btree (organization_id);


--
-- Name: ix_organization_users_user_id; Type: INDEX; Schema: public; Owner: cctv_user
--

CREATE INDEX ix_organization_users_user_id ON public.organization_users USING btree (user_id);


--
-- Name: ix_organizations_slug; Type: INDEX; Schema: public; Owner: cctv_user
--

CREATE UNIQUE INDEX ix_organizations_slug ON public.organizations USING btree (slug);


--
-- Name: ix_person_detections_camera_id; Type: INDEX; Schema: public; Owner: cctv_user
--

CREATE INDEX ix_person_detections_camera_id ON public.person_detections USING btree (camera_id);


--
-- Name: ix_person_detections_person_id; Type: INDEX; Schema: public; Owner: cctv_user
--

CREATE INDEX ix_person_detections_person_id ON public.person_detections USING btree (person_id);


--
-- Name: ix_person_detections_timestamp; Type: INDEX; Schema: public; Owner: cctv_user
--

CREATE INDEX ix_person_detections_timestamp ON public.person_detections USING btree ("timestamp");


--
-- Name: ix_ppe_profiles_name; Type: INDEX; Schema: public; Owner: cctv_user
--

CREATE UNIQUE INDEX ix_ppe_profiles_name ON public.ppe_profiles USING btree (name);


--
-- Name: ix_ppe_requirements_profile_id; Type: INDEX; Schema: public; Owner: cctv_user
--

CREATE INDEX ix_ppe_requirements_profile_id ON public.ppe_requirements USING btree (profile_id);


--
-- Name: ix_ppe_violations_camera_id; Type: INDEX; Schema: public; Owner: cctv_user
--

CREATE INDEX ix_ppe_violations_camera_id ON public.ppe_violations USING btree (camera_id);


--
-- Name: ix_ppe_violations_person_id; Type: INDEX; Schema: public; Owner: cctv_user
--

CREATE INDEX ix_ppe_violations_person_id ON public.ppe_violations USING btree (person_id);


--
-- Name: ix_ppe_violations_severity; Type: INDEX; Schema: public; Owner: cctv_user
--

CREATE INDEX ix_ppe_violations_severity ON public.ppe_violations USING btree (severity);


--
-- Name: ix_ppe_violations_status; Type: INDEX; Schema: public; Owner: cctv_user
--

CREATE INDEX ix_ppe_violations_status ON public.ppe_violations USING btree (status);


--
-- Name: ix_ppe_violations_timestamp; Type: INDEX; Schema: public; Owner: cctv_user
--

CREATE INDEX ix_ppe_violations_timestamp ON public.ppe_violations USING btree ("timestamp");


--
-- Name: ix_ppe_violations_zone_id; Type: INDEX; Schema: public; Owner: cctv_user
--

CREATE INDEX ix_ppe_violations_zone_id ON public.ppe_violations USING btree (zone_id);


--
-- Name: ix_refresh_tokens_family_id; Type: INDEX; Schema: public; Owner: cctv_user
--

CREATE INDEX ix_refresh_tokens_family_id ON public.refresh_tokens USING btree (family_id);


--
-- Name: ix_refresh_tokens_token_hash; Type: INDEX; Schema: public; Owner: cctv_user
--

CREATE UNIQUE INDEX ix_refresh_tokens_token_hash ON public.refresh_tokens USING btree (token_hash);


--
-- Name: ix_refresh_tokens_user_id; Type: INDEX; Schema: public; Owner: cctv_user
--

CREATE INDEX ix_refresh_tokens_user_id ON public.refresh_tokens USING btree (user_id);


--
-- Name: ix_safety_zones_camera_id; Type: INDEX; Schema: public; Owner: cctv_user
--

CREATE INDEX ix_safety_zones_camera_id ON public.safety_zones USING btree (camera_id);


--
-- Name: ix_safety_zones_organization_id; Type: INDEX; Schema: public; Owner: cctv_user
--

CREATE INDEX ix_safety_zones_organization_id ON public.safety_zones USING btree (organization_id);


--
-- Name: ix_safety_zones_site_id; Type: INDEX; Schema: public; Owner: cctv_user
--

CREATE INDEX ix_safety_zones_site_id ON public.safety_zones USING btree (site_id);


--
-- Name: ix_safety_zones_zone_type; Type: INDEX; Schema: public; Owner: cctv_user
--

CREATE INDEX ix_safety_zones_zone_type ON public.safety_zones USING btree (zone_type);


--
-- Name: ix_sites_organization_id; Type: INDEX; Schema: public; Owner: cctv_user
--

CREATE INDEX ix_sites_organization_id ON public.sites USING btree (organization_id);


--
-- Name: ix_system_logs_camera_id; Type: INDEX; Schema: public; Owner: cctv_user
--

CREATE INDEX ix_system_logs_camera_id ON public.system_logs USING btree (camera_id);


--
-- Name: ix_system_logs_correlation_id; Type: INDEX; Schema: public; Owner: cctv_user
--

CREATE INDEX ix_system_logs_correlation_id ON public.system_logs USING btree (correlation_id);


--
-- Name: ix_system_logs_created_at; Type: INDEX; Schema: public; Owner: cctv_user
--

CREATE INDEX ix_system_logs_created_at ON public.system_logs USING btree (created_at);


--
-- Name: ix_system_logs_level; Type: INDEX; Schema: public; Owner: cctv_user
--

CREATE INDEX ix_system_logs_level ON public.system_logs USING btree (level);


--
-- Name: ix_system_logs_module; Type: INDEX; Schema: public; Owner: cctv_user
--

CREATE INDEX ix_system_logs_module ON public.system_logs USING btree (module);


--
-- Name: ix_users_email; Type: INDEX; Schema: public; Owner: cctv_user
--

CREATE UNIQUE INDEX ix_users_email ON public.users USING btree (email);


--
-- Name: ix_users_organization_id; Type: INDEX; Schema: public; Owner: cctv_user
--

CREATE INDEX ix_users_organization_id ON public.users USING btree (organization_id);


--
-- Name: ix_users_username; Type: INDEX; Schema: public; Owner: cctv_user
--

CREATE UNIQUE INDEX ix_users_username ON public.users USING btree (username);


--
-- Name: alerts alerts_camera_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cctv_user
--

ALTER TABLE ONLY public.alerts
    ADD CONSTRAINT alerts_camera_id_fkey FOREIGN KEY (camera_id) REFERENCES public.cameras(id) ON DELETE CASCADE;


--
-- Name: cameras cameras_dvr_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cctv_user
--

ALTER TABLE ONLY public.cameras
    ADD CONSTRAINT cameras_dvr_id_fkey FOREIGN KEY (dvr_id) REFERENCES public.dvrs(id) ON DELETE RESTRICT;


--
-- Name: cameras cameras_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cctv_user
--

ALTER TABLE ONLY public.cameras
    ADD CONSTRAINT cameras_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id) ON DELETE SET NULL;


--
-- Name: cameras cameras_site_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cctv_user
--

ALTER TABLE ONLY public.cameras
    ADD CONSTRAINT cameras_site_id_fkey FOREIGN KEY (site_id) REFERENCES public.sites(id) ON DELETE SET NULL;


--
-- Name: detections detections_camera_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cctv_user
--

ALTER TABLE ONLY public.detections
    ADD CONSTRAINT detections_camera_id_fkey FOREIGN KEY (camera_id) REFERENCES public.cameras(id) ON DELETE CASCADE;


--
-- Name: evidence evidence_alert_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cctv_user
--

ALTER TABLE ONLY public.evidence
    ADD CONSTRAINT evidence_alert_id_fkey FOREIGN KEY (alert_id) REFERENCES public.alerts(id) ON DELETE CASCADE;


--
-- Name: evidence evidence_camera_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cctv_user
--

ALTER TABLE ONLY public.evidence
    ADD CONSTRAINT evidence_camera_id_fkey FOREIGN KEY (camera_id) REFERENCES public.cameras(id) ON DELETE CASCADE;


--
-- Name: incidents incidents_camera_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cctv_user
--

ALTER TABLE ONLY public.incidents
    ADD CONSTRAINT incidents_camera_id_fkey FOREIGN KEY (camera_id) REFERENCES public.cameras(id) ON DELETE CASCADE;


--
-- Name: incidents incidents_zone_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cctv_user
--

ALTER TABLE ONLY public.incidents
    ADD CONSTRAINT incidents_zone_id_fkey FOREIGN KEY (zone_id) REFERENCES public.safety_zones(id) ON DELETE SET NULL;


--
-- Name: licenses licenses_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cctv_user
--

ALTER TABLE ONLY public.licenses
    ADD CONSTRAINT licenses_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id) ON DELETE CASCADE;


--
-- Name: notifications notifications_alert_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cctv_user
--

ALTER TABLE ONLY public.notifications
    ADD CONSTRAINT notifications_alert_id_fkey FOREIGN KEY (alert_id) REFERENCES public.alerts(id) ON DELETE CASCADE;


--
-- Name: organization_users organization_users_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cctv_user
--

ALTER TABLE ONLY public.organization_users
    ADD CONSTRAINT organization_users_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id) ON DELETE CASCADE;


--
-- Name: organization_users organization_users_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cctv_user
--

ALTER TABLE ONLY public.organization_users
    ADD CONSTRAINT organization_users_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: person_detections person_detections_camera_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cctv_user
--

ALTER TABLE ONLY public.person_detections
    ADD CONSTRAINT person_detections_camera_id_fkey FOREIGN KEY (camera_id) REFERENCES public.cameras(id) ON DELETE CASCADE;


--
-- Name: ppe_requirements ppe_requirements_profile_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cctv_user
--

ALTER TABLE ONLY public.ppe_requirements
    ADD CONSTRAINT ppe_requirements_profile_id_fkey FOREIGN KEY (profile_id) REFERENCES public.ppe_profiles(id) ON DELETE CASCADE;


--
-- Name: ppe_violations ppe_violations_camera_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cctv_user
--

ALTER TABLE ONLY public.ppe_violations
    ADD CONSTRAINT ppe_violations_camera_id_fkey FOREIGN KEY (camera_id) REFERENCES public.cameras(id) ON DELETE CASCADE;


--
-- Name: ppe_violations ppe_violations_profile_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cctv_user
--

ALTER TABLE ONLY public.ppe_violations
    ADD CONSTRAINT ppe_violations_profile_id_fkey FOREIGN KEY (profile_id) REFERENCES public.ppe_profiles(id) ON DELETE SET NULL;


--
-- Name: ppe_violations ppe_violations_zone_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cctv_user
--

ALTER TABLE ONLY public.ppe_violations
    ADD CONSTRAINT ppe_violations_zone_id_fkey FOREIGN KEY (zone_id) REFERENCES public.safety_zones(id) ON DELETE SET NULL;


--
-- Name: refresh_tokens refresh_tokens_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cctv_user
--

ALTER TABLE ONLY public.refresh_tokens
    ADD CONSTRAINT refresh_tokens_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: safety_zones safety_zones_camera_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cctv_user
--

ALTER TABLE ONLY public.safety_zones
    ADD CONSTRAINT safety_zones_camera_id_fkey FOREIGN KEY (camera_id) REFERENCES public.cameras(id) ON DELETE CASCADE;


--
-- Name: safety_zones safety_zones_ppe_profile_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cctv_user
--

ALTER TABLE ONLY public.safety_zones
    ADD CONSTRAINT safety_zones_ppe_profile_id_fkey FOREIGN KEY (ppe_profile_id) REFERENCES public.ppe_profiles(id) ON DELETE SET NULL;


--
-- Name: sites sites_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cctv_user
--

ALTER TABLE ONLY public.sites
    ADD CONSTRAINT sites_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id) ON DELETE CASCADE;


--
-- Name: users users_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cctv_user
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id) ON DELETE SET NULL;


--
-- PostgreSQL database dump complete
--

\unrestrict msWB7TwxfsIGKkfIP49PnGkeMvecXtdz8goSGIkfNYMQXicYK0kQUdqutfkNDup

