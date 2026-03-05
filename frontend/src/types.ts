export interface DashboardSnapshot {
  frame_number: number;
  fps: number;
  current_people: number;
  entries_today: number;
  last_entry_time: string | null;
  uptime_seconds: number;
  event_log: EventLogEntry[];
  tracked_people: TrackedPerson[];
  camera_connected: boolean;
  webhook_status: Record<string, unknown>;
  calibration: Record<string, unknown>;
  detector_running: boolean;
  wake_lock_active: boolean;
}

export interface EventLogEntry {
  event: string;
  timestamp: string;
  person_id: number;
  confidence: number;
  queued?: boolean;
  snapshot?: string;
}

export interface TrackedPerson {
  person_id: number;
  direction: string;
  score: number;
  confidence: number;
}

export interface TranscribeResult {
  text: string;
  cnp: string | null;
  email: string | null;
}
