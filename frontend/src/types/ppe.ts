export interface PPEProfile {
  id: number;
  name: string;
  description?: string;
  required_equipment: string[];
  optional_equipment: string[];
  created_at: string;
  updated_at: string;
}

export interface SafetyZone {
  id: number;
  camera_id: number;
  name: string;
  zone_type: 'HAZARD' | 'RESTRICTED' | 'GENERAL';
  polygon_coordinates: number[][];
  ppe_profile_id?: number;
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface PPEViolation {
  id: string;
  camera_id: number;
  zone_id?: number;
  person_id: number;
  profile_id?: number;
  status: 'PASS' | 'VIOLATION' | 'UNKNOWN';
  severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
  missing_items: string[];
  detected_items: string[];
  required_items: string[];
  confidence: number;
  timestamp: string;
  evidence_id?: string;
  created_at: string;
}

export interface Incident {
  id: string;
  camera_id: number;
  zone_id?: number;
  incident_type: 'FIRE' | 'SMOKE' | 'PPE_VIOLATION' | 'ZONE_VIOLATION' | 'SAFETY_INCIDENT';
  events: string[];
  severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
  status: 'ACTIVE' | 'ACKNOWLEDGED' | 'RESOLVED';
  person_id?: number;
  evidence_id?: string;
  start_time: string;
  cleared_time?: string;
  metadata_json: Record<string, any>;
  created_at: string;
}

export interface SafetyStatistics {
  total_cameras: number;
  online_cameras: number;
  offline_cameras: number;
  active_fire_alerts: number;
  active_smoke_alerts: number;
  ppe_violations_24h: number;
  workers_detected_24h: number;
  zone_violations_24h: number;
  critical_incidents_active: number;
  daily_compliance_percentage: number;
  calculated_at: string;
}
