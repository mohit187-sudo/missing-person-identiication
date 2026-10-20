// API type mirrors of the backend Pydantic schemas.

export type Role = 'administrator' | 'investigator' | 'rescue_team';

export interface UserBrief {
  id: string;
  email: string;
  full_name: string;
  role: Role;
  agency: string;
  is_active: boolean;
}

export interface User extends UserBrief {
  phone: string;
  created_at: string;
  last_login_at: string | null;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user: UserBrief;
}

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface Photo {
  id: string;
  case_id: string;
  original_filename: string;
  content_type: string;
  file_size: number;
  is_primary: boolean;
  quality_score: number | null;
  blur_score: number | null;
  width: number | null;
  height: number | null;
  embedding_count: number;
  created_at: string;
  ai?: { embedding_generated: boolean; reason: string };
}

export interface StatusHistory {
  id: string;
  from_status: string | null;
  to_status: string;
  note: string;
  created_at: string;
}

export interface MissingPersonCase {
  id: string;
  case_number: string;
  full_name: string | null;
  name_unknown: boolean;
  age_min: number | null;
  age_max: number | null;
  gender: string | null;
  last_seen_date: string | null;
  last_seen_location: string;
  physical_description: string;
  clothing_description: string;
  additional_notes: string;
  contact_agency: string;
  contact_info: string;
  status: string;
  consent_recorded: boolean;
  legal_basis: string;
  authorization_reference: string;
  is_demo: boolean;
  created_at: string;
  updated_at: string;
  photos: Photo[];
  status_history: StatusHistory[];
}

export interface CaseListItem {
  id: string;
  case_number: string;
  full_name: string | null;
  name_unknown: boolean;
  age_min: number | null;
  age_max: number | null;
  last_seen_date: string | null;
  last_seen_location: string;
  status: string;
  is_demo: boolean;
  photo_count: number;
  created_at: string;
}

export interface Match {
  id: string;
  source_type: string;
  candidate_case_id: string;
  candidate_case_number: string;
  candidate_name: string | null;
  query_photo_id: string | null;
  detected_face_id: string | null;
  similarity_score: number;
  threshold_used: number;
  model_name: string;
  model_version: string;
  image_quality: Record<string, unknown>;
  status: string;
  source_timestamp_seconds: number | null;
  processing_timestamp: string;
  is_demo: boolean;
  created_at: string;
}

export interface Review {
  id: string;
  match_id: string;
  reviewer_id: string | null;
  reviewer_name: string;
  decision: string;
  notes: string;
  created_at: string;
}

export interface MatchDetail extends Match {
  reviews: Review[];
}

export interface SearchResult {
  job_id: string;
  status: string;
  model_name: string;
  model_version: string;
  threshold_used: number;
  matches: Match[];
  faces_detected: number;
  quality: Record<string, unknown>;
  disclaimer: string;
}

export interface VideoJob {
  id: string;
  video_id: string;
  status: string;
  progress: number;
  sampling_interval_seconds: number;
  frames_sampled: number;
  faces_detected: number;
  matches_found: number;
  error_message: string;
  cancel_requested: boolean;
  model_name: string;
  model_version: string;
  threshold_used: number | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
}

export interface Video {
  id: string;
  title: string;
  description: string;
  case_id: string | null;
  original_filename: string;
  content_type: string;
  file_size: number;
  duration_seconds: number | null;
  width: number | null;
  height: number | null;
  fps: number | null;
  authorization_reference: string;
  lawfully_obtained: boolean;
  is_demo: boolean;
  created_at: string;
  latest_job_status: string | null;
  latest_job_progress: number | null;
}

export interface Notification {
  id: string;
  type: string;
  title: string;
  body: string;
  link: string;
  is_read: boolean;
  created_at: string;
}

export interface AuditLogEntry {
  id: string;
  user_id: string | null;
  user_email: string;
  action: string;
  resource_type: string;
  resource_id: string;
  detail: Record<string, unknown>;
  ip_address: string;
  user_agent: string;
  created_at: string;
}

export interface RetentionPolicy {
  id: string;
  resource_type: string;
  retention_days: number;
  action: string;
  is_active: boolean;
  description: string;
}

export interface OverviewStats {
  total_cases: number;
  active_cases: number;
  located_cases: number;
  total_photos: number;
  total_videos: number;
  jobs_running: number;
  jobs_completed: number;
  matches_pending_review: number;
  matches_confirmed: number;
  matches_rejected: number;
  demo_cases: number;
  ai_available: boolean;
  cases_by_status: Record<string, number>;
  matches_last_7_days: number;
  cases_last_30_days: number;
}

export interface AIStatus {
  backend: string;
  available: boolean;
  model_name: string;
  model_version: string;
  embedding_dim: number | null;
  license: string;
  detail: string;
  setup_steps: string[];
}

export interface ApiError {
  code: string;
  message: string;
  details: Record<string, unknown>;
}
