export type ResearchStatus =
  | "PLANNING"
  | "RESEARCHING"
  | "VERIFYING"
  | "SYNTHESIZING"
  | "COMPLETED"
  | "FAILED"
  | "CANCELLED";

export interface ResearchSnapshot {
  id: string;
  goal: string;
  depth: string;
  status: ResearchStatus;
  progress: number;
  current_agent: string | null;
  current_task: string | null;
  searches_count: number;
  corrections_count: number;
  sources_count: number;
  tasks_total: number;
  tasks_completed: number;
  error: string | null;
  created_at: string;
  completed_at: string | null;
}

export interface AgentLog {
  id: number;
  agent_name: string;
  action: string;
  input: string | null;
  output: string | null;
  status: string;
  timestamp: string;
  duration_ms: number | null;
}

export interface SearchRecord {
  id: number;
  task_id: number | null;
  query: string;
  attempt_number: number;
  result_count: number;
  relevance_score: number | null;
  status: string;
  was_correction: boolean;
  created_at: string;
}

export type SourceTier = "official" | "high" | "medium" | "low";

export interface EvidenceItem {
  id: number;
  claim: string;
  supporting_content: string;
  source_title: string;
  source_url: string;
  source_domain: string;
  source_tier: SourceTier;
  freshness: number;
  confidence_score: number;
  verified: boolean;
  created_at: string;
}

export interface ResearchTask {
  id: number;
  task: string;
  status: string;
  order_index: number;
  result: string | null;
  completed_at: string | null;
}

export interface ReportData {
  research_id: string;
  content: string;
  created_at: string;
}

export interface StartResearchResponse {
  research_id: string;
  status: string;
}

export type HistoryItem = ResearchSnapshot;