export type Organization = { id: number; name: string; root_domain: string; created_at: string }
export type Scan = { id: number; organization_id: number; status: string; started_at: string; finished_at?: string; assets_found: number; findings_found: number; error?: string }
export type ScanChange = { id: number; kind: string; hostname: string; details: Record<string, unknown>; detected_at: string }
export type Asset = { id: number; organization_id: number; hostname: string; asset_type: string; status: string; ips: string[]; risk_score: number; risk_details?: { score: number; level: string; factors: Record<string, number>; weights: Record<string, number> }; first_seen: string; last_seen: string; latest_scan_id?: number; discovery_sources: string[] }
export type Finding = { id: number; hostname: string; title: string; category: string; severity: string; status: string; description: string; evidence: Record<string, unknown>; recommendation: string; detected_at: string }
export type DashboardData = {
  total_assets: number; active_assets: number; open_findings: number; critical_findings: number; high_risk_assets: number
  assets_by_type: Record<string, number>; findings_by_severity: Record<string, number>; latest_scan: Scan | null; recent_scans: Scan[]; risk_scores: number[]
}