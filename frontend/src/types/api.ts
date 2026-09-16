export type UserRole = "ADMIN" | "MANAGER" | "OPERATOR" | "VIEWER";

export interface User {
  id: string;
  username: string;
  email: string;
  full_name: string;
  role: UserRole;
  is_active: boolean;
  is_superuser: boolean;
  created_at: string;
}

export interface Camera {
  id: number;
  name: string;
  camera_number: string;
  dvr_address?: string;
  sanitized_rtsp_url: string;
  source_type: string;
  location?: string;
  enabled: boolean;
  fire_smoke_enabled: boolean;
  ppe_enabled: boolean;
  person_enabled: boolean;
  zone_enabled: boolean;
  ppe_inference_interval_sec: number;
  fps_limit: number;
  connection_timeout: number;
  reconnect_interval: number;
  created_at: string;
  updated_at: string;
}

export interface CameraRuntimeState {
  camera_id: number;
  status: "CONNECTED" | "DISCONNECTED" | "CONNECTING" | "RECONNECTING" | "ERROR";
  fps: number;
  resolution?: string;
  reconnect_attempts: number;
  last_frame_timestamp?: string;
  error_message?: string;
}

export interface CameraCreatePayload {
  name: string;
  camera_number: string;
  dvr_address?: string;
  rtsp_url: string;
  source_type: string;
  location?: string;
  fps_limit?: number;
  enabled?: boolean;
  fire_smoke_enabled?: boolean;
  ppe_enabled?: boolean;
  person_enabled?: boolean;
  zone_enabled?: boolean;
  ppe_inference_interval_sec?: number;
}

export interface CameraUpdatePayload {
  name?: string;
  camera_number?: string;
  dvr_address?: string;
  rtsp_url?: string;
  source_type?: string;
  location?: string;
  fps_limit?: number;
  enabled?: boolean;
  fire_smoke_enabled?: boolean;
  ppe_enabled?: boolean;
  person_enabled?: boolean;
  zone_enabled?: boolean;
  ppe_inference_interval_sec?: number;
}

export interface Alert {
  id: number | string;
  alert_id: string;
  camera_id: number;
  camera_name?: string;
  camera_location?: string;
  location?: string;
  class_name: "fire" | "smoke" | string;
  severity?: "CRITICAL" | "WARNING" | "INFO";
  state?: string;
  status?: "NEW" | "ACKNOWLEDGED" | "RESOLVED" | string;
  confidence: number;
  max_confidence?: number;
  latest_confidence?: number;
  snapshot_url?: string;
  video_url?: string;
  details?: string;
  start_time?: string;
  cleared_time?: string;
  triggered_at?: string;
  acknowledged_at?: string;
  resolved_at?: string;
  remedial_action?: string;
  remedy_notes?: string;
  resolved_by?: string;
}

export interface Detection {
  id: number;
  camera_id: number;
  camera_name?: string;
  class_name: "fire" | "smoke";
  confidence: number;
  bounding_box?: {
    x_min: number;
    y_min: number;
    x_max: number;
    y_max: number;
  };
  snapshot_url?: string;
  timestamp: string;
}

export interface EvidenceItem {
  evidence_id: string;
  id?: string;
  alert_id: string;
  camera_id: number;
  snapshot_url: string;
  video_url?: string;
  file_size_bytes?: number;
  metadata_envelope?: Record<string, any>;
  created_at: string;
}

export interface SystemStatus {
  status: "OPERATIONAL" | "DEGRADED" | "CRITICAL";
  version: string;
  environment: string;
  active_cameras_count: number;
  total_cameras_count: number;
  ai_detection_enabled: boolean;
  uptime_seconds: number;
}

export interface SystemStats {
  total_cameras: number;
  online_cameras: number;
  offline_cameras: number;
  active_fire_alerts: number;
  active_smoke_alerts: number;
  total_alerts_24h: number;
  cpu_percent?: number;
  memory_percent?: number;
}

export interface VerificationSettings {
  fire_min_confidence: number;
  fire_min_consecutive_frames: number;
  fire_min_duration_seconds: number;
  smoke_min_confidence: number;
  smoke_min_consecutive_frames: number;
  smoke_min_duration_seconds: number;
  ppe_verification_frames: number;
  ppe_verification_duration_seconds: number;
  verification_cooldown_seconds: number;
}

export interface ApiResponse<T> {
  success: boolean;
  data: T;
  pagination?: {
    total: number;
    limit: number;
    offset: number;
    has_more: boolean;
  };
  request_id?: string;
}

export interface WSEventEnvelope<T = any> {
  event_id: string;
  seq: number;
  event: string;
  version: string;
  timestamp: string;
  data: T;
  payload?: T;
}
