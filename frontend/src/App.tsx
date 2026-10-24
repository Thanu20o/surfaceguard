import { useEffect, useState } from 'react'
import type { FormEvent, ReactNode } from 'react'
import { Link, NavLink, Outlet, Route, Routes, useParams } from 'react-router-dom'
import { Activity, AlertTriangle, ArrowDownToLine, ArrowUpRight, Box, CircleHelp, Clock3, Compass, FileText, Fingerprint, Gauge, LoaderCircle, Plus, Radar, RefreshCw, Search, ShieldCheck, ShieldAlert, SlidersHorizontal, Waypoints } from 'lucide-react'
import { Bar, BarChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api, createOrganization, getAsset, getAssets, getDashboard, getFindings, getOrganizations, getScanChanges, getScans, startScan, updateFinding } from './api'
import type { Asset, DashboardData, Finding, Organization, Scan, ScanChange } from './types'

const chartColors = ['#83d5b0', '#f4c37d', '#e47b67', '#a3a7a0', '#7593a3']
const date = (value?: string) => value ? new Date(value).toLocaleString() : '—'
const errorText = (error: unknown) => {
  if (typeof error === 'object' && error && 'response' in error) {
    const response = (error as { response?: { data?: { detail?: string } } }).response
    return response?.data?.detail ?? 'The request could not be completed.'
  }
  return error instanceof Error ? error.message : 'The API could not be reached.'
}

export default function App() {
  const [organizations, setOrganizations] = useState<Organization[]>([])
  const [selectedId, setSelectedId] = useState(Number(localStorage.getItem('surfaceguard.organization') ?? 0))
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const selected = organizations.find((item) => item.id === selectedId) ?? organizations[0]

  const reload = async () => {
    try {
      const result = await getOrganizations()
      setOrganizations(result)
      if (!result.some((item) => item.id === selectedId)) setSelectedId(result[0]?.id ?? 0)
      setError('')
    } catch (issue) { setError(errorText(issue)) }
    finally { setLoading(false) }
  }

  useEffect(() => { void reload() }, [])
  useEffect(() => { if (selectedId) localStorage.setItem('surfaceguard.organization', String(selectedId)) }, [selectedId])

  if (loading) return <div className="screen-center"><LoaderCircle className="spin" /> Loading workspace</div>
  if (!selected) return <SetupPage error={error} onCreated={async () => { await reload() }} />
  return <Routes>
    <Route element={<Shell organization={selected} organizations={organizations} onSelect={setSelectedId} onReload={reload} />}>
      <Route index element={<DashboardPage organization={selected} />} />
      <Route path="assets" element={<AssetsPage organization={selected} />} />
      <Route path="assets/:assetId" element={<AssetDetailsPage />} />
      <Route path="findings" element={<FindingsPage organization={selected} />} />
      <Route path="scans" element={<ScansPage organization={selected} />} />
      <Route path="reports" element={<ReportsPage organization={selected} />} />
      <Route path="settings" element={<SettingsPage organization={selected} onUpdated={reload} />} />
      <Route path="*" element={<DashboardPage organization={selected} />} />
    </Route>
  </Routes>
}

function Shell({ organization, organizations, onSelect, onReload }: { organization: Organization; organizations: Organization[]; onSelect: (id: number) => void; onReload: () => Promise<void> }) {
  const nav = [
    { to: '/', label: 'Overview', icon: Gauge }, { to: '/assets', label: 'Assets', icon: Box },
    { to: '/findings', label: 'Findings', icon: ShieldAlert }, { to: '/scans', label: 'Scans', icon: Radar },
  ]
  return <div className="app-shell">
    <aside className="sidebar">
      <Link to="/" className="brand"><span className="brand-mark"><Fingerprint size={21} /></span><span>surfaceguard<small>EXTERNAL EXPOSURE</small></span></Link>
      <div className="scope-switch">
        <label htmlFor="org-select">WORKSPACE</label>
        <select id="org-select" value={organization.id} onChange={(event) => onSelect(Number(event.target.value))}>
          {organizations.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
        </select>
        <span className="scope-domain"><span className="dot" />{organization.root_domain}</span>
      </div>
      <div className="nav-label">MONITOR</div>
      <nav className="main-nav">{nav.map(({ to, label, icon: Icon }) => <NavLink key={to} end={to === '/'} to={to} className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}><Icon size={17} strokeWidth={1.8} />{label}</NavLink>)}</nav>
      <div className="nav-label lower-label">WORKSPACE</div>
      <nav className="main-nav">
        <NavLink to="/reports" className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}><FileText size={17} />Reports</NavLink>
        <NavLink to="/settings" className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}><SlidersHorizontal size={17} />Settings</NavLink>
      </nav>
      <div className="sidebar-bottom"><ApiConnection /><a href="http://localhost:8000/docs" target="_blank" rel="noreferrer"><CircleHelp size={15} /> API reference <ArrowUpRight size={13} /></a></div>
    </aside>
    <main className="main-area">
      <header className="topbar"><div><span className="breadcrumb">Surfaceguard</span><span className="crumb-slash">/</span><span>{organization.name}</span></div><div className="topbar-right"><span className="scope-pill"><ShieldCheck size={14} /> Authorized scope</span><button className="icon-button" title="Refresh organization data" onClick={() => void onReload()}><RefreshCw size={16} /></button></div></header>
      <div className="content"><Outlet /></div>
    </main>
  </div>
}

function PageHeading({ eyebrow, title, subtitle, action }: { eyebrow: string; title: string; subtitle?: string; action?: React.ReactNode }) {
  return <div className="page-heading"><div><div className="eyebrow">{eyebrow}</div><h1>{title}</h1>{subtitle && <p>{subtitle}</p>}</div>{action}</div>
}

function DashboardPage({ organization }: { organization: Organization }) {
  const [data, setData] = useState<DashboardData | null>(null)
  const [error, setError] = useState('')
  useEffect(() => { getDashboard(organization.id).then(setData).catch((issue) => setError(errorText(issue))) }, [organization.id])
  const scoreBands = data?.risk_scores.reduce((result, score) => { const label = score >= 80 ? 'Critical' : score >= 60 ? 'High' : score >= 40 ? 'Medium' : score >= 20 ? 'Low' : 'Info'; result[label] = (result[label] ?? 0) + 1; return result }, {} as Record<string, number>) ?? {}
  const riskData = Object.entries(scoreBands).map(([name, value]) => ({ name, value }))
  const assetsData = Object.entries(data?.assets_by_type ?? {}).map(([name, value]) => ({ name, value }))
  const findingsData = ['Critical', 'High', 'Medium', 'Low', 'Informational'].map((severity) => ({ name: severity, count: data?.findings_by_severity[severity] ?? 0 }))
  return <>
    <PageHeading eyebrow="SECURITY POSTURE / LIVE INVENTORY" title="Overview" subtitle={`Authorized perimeter · ${organization.root_domain}`} action={<Link to="/scans" className="button button-primary"><Radar size={16} /> Run a scan</Link>} />
    {error && <ErrorBanner message={error} />}
    <div className="metric-grid">
      <Metric label="Discovered assets" value={data?.total_assets ?? '—'} icon={<Waypoints />} note={`${data?.active_assets ?? 0} currently observed`} />
      <Metric label="Open findings" value={data?.open_findings ?? '—'} icon={<ShieldAlert />} note="Open or acknowledged" tone="amber" />
      <Metric label="Critical findings" value={data?.critical_findings ?? '—'} icon={<AlertTriangle />} note="Require immediate review" tone="red" />
      <Metric label="High-risk assets" value={data?.high_risk_assets ?? '—'} icon={<Activity />} note="Risk score 60 or higher" />
    </div>
    <div className="overview-grid">
      <section className="panel chart-panel"><div className="panel-heading"><div><h2>Asset composition</h2><p>Observed hostnames by classification</p></div><span className="panel-index">01</span></div>
        {assetsData.length ? <div className="chart-layout"><div className="donut-wrap"><ResponsiveContainer width="100%" height={210}><PieChart><Pie data={assetsData} dataKey="value" nameKey="name" innerRadius={63} outerRadius={88} paddingAngle={3} stroke="none">{assetsData.map((item, index) => <Cell key={item.name} fill={chartColors[index % chartColors.length]} />)}</Pie><Tooltip contentStyle={{ background: '#202925', border: '1px solid #39443e', borderRadius: 6, color: '#f4f1e9' }} /></PieChart></ResponsiveContainer><div className="donut-center"><strong>{data?.total_assets ?? 0}</strong><span>assets</span></div></div><div className="legend">{assetsData.map((item, index) => <div key={item.name}><span style={{ background: chartColors[index % chartColors.length] }} />{item.name}<b>{item.value}</b></div>)}</div></div> : <EmptyChart message="No discovered assets yet" />}
      </section>
      <section className="panel chart-panel"><div className="panel-heading"><div><h2>Findings by severity</h2><p>Open items from completed assessments</p></div><span className="panel-index">02</span></div>
        <div className="bar-chart"><ResponsiveContainer width="100%" height={235}><BarChart data={findingsData} margin={{ top: 10, right: 4, left: -24, bottom: 0 }}><CartesianGrid stroke="#303a34" vertical={false} /><XAxis dataKey="name" tick={{ fill: '#929b93', fontSize: 11 }} axisLine={false} tickLine={false} /><YAxis allowDecimals={false} tick={{ fill: '#737d75', fontSize: 11 }} axisLine={false} tickLine={false} /><Tooltip cursor={{ fill: '#2c3731' }} contentStyle={{ background: '#202925', border: '1px solid #39443e', borderRadius: 6, color: '#f4f1e9' }} /><Bar dataKey="count" radius={[3, 3, 0, 0]}>{findingsData.map((item, index) => <Cell key={item.name} fill={chartColors[index % chartColors.length]} />)}</Bar></BarChart></ResponsiveContainer></div>
      </section>
    </div>
    <div className="bottom-grid">
      <section className="panel"><div className="panel-heading"><div><h2>Latest scan</h2><p>Most recent assessment result</p></div><Link to="/scans" className="text-link">Scan history <ArrowUpRight size={14} /></Link></div>
        {data?.latest_scan ? <div className="latest-scan"><StatusTag value={data.latest_scan.status} /><strong>Scan #{data.latest_scan.id}</strong><span><Clock3 size={14} />{date(data.latest_scan.started_at)}</span><span>{data.latest_scan.assets_found} new assets · {data.latest_scan.findings_found} findings</span></div> : <EmptyInline title="No scans run" text="Start with a manual scan of the authorized root domain." />}
      </section>
      <section className="panel risk-panel"><div className="panel-heading"><div><h2>Risk distribution</h2><p>Asset scores, 0–100</p></div></div>
        {riskData.length ? <div className="risk-list">{['Critical', 'High', 'Medium', 'Low', 'Info'].map((level) => { const count = scoreBands[level] ?? 0; const total = data?.total_assets || 1; return <div className="risk-row" key={level}><span>{level}</span><div className="risk-track"><i style={{ width: `${count / total * 100}%` }} /></div><b>{count}</b></div> })}</div> : <EmptyInline title="No risk scores yet" text="Scores appear when a scan completes." />}
      </section>
    </div>
  </>
}

function Metric({ label, value, icon, note, tone = '' }: { label: string; value: string | number; icon: ReactNode; note: string; tone?: string }) {
  return <div className={`metric ${tone}`}><div className="metric-top"><span>{label}</span><i>{icon}</i></div><strong>{value}</strong><small>{note}</small></div>
}

function AssetsPage({ organization }: { organization: Organization }) {
  const [assets, setAssets] = useState<Asset[]>([])
  const [query, setQuery] = useState('')
  const [error, setError] = useState('')
  useEffect(() => { getAssets(organization.id, query).then(setAssets).catch((issue) => setError(errorText(issue))) }, [organization.id, query])
  return <><PageHeading eyebrow="INVENTORY / AUTHORIZED SCOPE" title="Assets" subtitle={`${organization.root_domain} · ${assets.length} observed hostnames`} />{error && <ErrorBanner message={error} />}
    <section className="panel table-panel"><div className="table-toolbar"><label className="search-field"><Search size={16} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search hostnames" /></label><span className="table-count">{assets.length} assets</span></div>
      {assets.length ? <div className="table-scroll"><table><thead><tr><th>Hostname</th><th>Type</th><th>IP address</th><th>Last observed</th><th>Risk</th><th>Status</th><th></th></tr></thead><tbody>{assets.map((asset) => <tr key={asset.id}><td><Link className="host-link" to={`/assets/${asset.id}`}>{asset.hostname}<ArrowUpRight size={13} /></Link></td><td><span className="type-label">{asset.asset_type}</span></td><td className="mono">{asset.ips?.join(', ') || '—'}</td><td>{date(asset.last_seen)}</td><td><RiskPill score={asset.risk_score} /></td><td><span className={`status-dot asset-${asset.status.toLowerCase().replaceAll(' ', '-')}`}>{asset.status}</span></td><td><Link to={`/assets/${asset.id}`} className="row-open" title="Open asset"><ArrowUpRight size={15} /></Link></td></tr>)}</tbody></table></div> : <EmptyInline title="No assets discovered" text="Run a scan to populate this inventory with real DNS observations." />}
    </section></>
}

function AssetDetailsPage() {
  const { assetId = '' } = useParams()
  const [data, setData] = useState<Awaited<ReturnType<typeof getAsset>> | null>(null)
  const [findings, setFindings] = useState<Finding[]>([])
  const [error, setError] = useState('')
  useEffect(() => { getAsset(Number(assetId)).then(async (detail) => { setData(detail); setFindings(await getFindings(detail.asset.organization_id, { q: detail.asset.hostname })) }).catch((issue) => setError(errorText(issue))) }, [assetId])
  const asset = data?.asset
  return <><PageHeading eyebrow="INVENTORY / ASSET DETAIL" title={asset?.hostname ?? 'Asset'} subtitle="Observed configuration and assessment evidence" action={<Link to="/assets" className="button button-quiet">Back to assets</Link>} />{error && <ErrorBanner message={error} />}
    {asset && <><div className="detail-summary"><div><span className="eyebrow">HOSTNAME</span><strong>{asset.hostname}</strong><small>{asset.ips?.join(' · ') || 'No IP addresses returned'}</small></div><div><span className="eyebrow">RISK SCORE</span><RiskPill score={asset.risk_score} large /></div><div><span className="eyebrow">CLASSIFICATION</span><strong className="detail-type">{asset.asset_type}</strong><small>Based on observed hostname and response signals</small></div><div><span className="eyebrow">FIRST OBSERVED</span><strong className="detail-date">{date(asset.first_seen)}</strong><small>Last: {date(asset.last_seen)}</small></div></div>
      <div className="detail-grid"><section className="panel"><div className="panel-heading"><div><h2>Assessment observations</h2><p>Latest recorded DNS, TLS and HTTP check outcomes</p></div></div>{data?.observations.length ? <div className="observation-list">{data.observations.map((observation, index) => <div className="observation" key={`${observation.kind}-${index}`}><div className="observation-title"><span className="observation-kind">{observation.kind}</span><span>{date(observation.observed_at)}</span></div><pre>{JSON.stringify(observation.value, null, 2)}</pre></div>)}</div> : <EmptyInline title="No observations" text="The next scan will add results here." />}</section>
        <section className="panel"><div className="panel-heading"><div><h2>Discovery record</h2><p>Provenance and current state</p></div></div><dl className="definition-list"><dt>Source</dt><dd>{asset.discovery_sources?.join(', ') || '—'}</dd><dt>Current status</dt><dd>{asset.status}</dd><dt>Latest scan</dt><dd>#{asset.latest_scan_id ?? '—'}</dd><dt>Risk method</dt><dd>Severity × 40% + exposure × 25% + confidence × 20% + impact × 15%</dd></dl><p className="notice">The score is a project-specific prioritization aid, not a probability of compromise.</p></section>
        <section className="panel"><div className="panel-heading"><div><h2>Risk calculation</h2><p>Weighted inputs saved with this score</p></div></div>{asset.risk_details?.factors ? <div className="factor-list">{Object.entries(asset.risk_details.factors).map(([key, value]) => <div className="factor-row" key={key}><span>{key.replaceAll('_', ' ')}</span><div className="risk-track"><i style={{ width: `${value}%` }} /></div><b>{value}</b><small>× {Math.round((asset.risk_details?.weights[key] ?? 0) * 100)}%</small></div>)}</div> : <EmptyInline title="Score factors unavailable" text="A scan has not stored a calculated score for this asset yet." />}<p className="notice">The project-specific score is a prioritization aid, not a probability of compromise. Maximum active finding severity is used; findings are not summed.</p></section>
        <section className="panel"><div className="panel-heading"><div><h2>Associated findings</h2><p>Evidence and remediation for this hostname</p></div></div>{findings.length ? <div className="associated-findings">{findings.map((finding) => <div key={finding.id}><div><SeverityTag value={finding.severity} /><strong>{finding.title}</strong></div><p>{finding.description}</p><small>{finding.recommendation}</small></div>)}</div> : <EmptyInline title="No findings recorded" text="Findings appear here when an assessment observes a condition worth reviewing." />}</section></div></>}
  </>
}

function FindingsPage({ organization }: { organization: Organization }) {
  const [findings, setFindings] = useState<Finding[]>([])
  const [severity, setSeverity] = useState('')
  const [status, setStatus] = useState('')
  const [query, setQuery] = useState('')
  const [error, setError] = useState('')
  const load = () => getFindings(organization.id, { ...(severity ? { severity } : {}), ...(status ? { finding_status: status } : {}), ...(query ? { q: query } : {}) }).then(setFindings).catch((issue) => setError(errorText(issue)))
  useEffect(() => { void load() }, [organization.id, severity, status, query])
  const changeStatus = async (finding: Finding, next: string) => { try { await updateFinding(finding.id, next); await load() } catch (issue) { setError(errorText(issue)) } }
  return <><PageHeading eyebrow="ASSESSMENT / EVIDENCE" title="Findings" subtitle="Review evidence, disposition and remediation guidance" />{error && <ErrorBanner message={error} />}
    <section className="panel table-panel"><div className="table-toolbar"><label className="search-field"><Search size={16} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search by hostname" /></label><select className="filter-select" value={severity} onChange={(event) => setSeverity(event.target.value)}><option value="">All severities</option>{['Critical', 'High', 'Medium', 'Low', 'Informational'].map((value) => <option key={value}>{value}</option>)}</select><select className="filter-select" value={status} onChange={(event) => setStatus(event.target.value)}><option value="">All statuses</option>{['Open', 'Acknowledged', 'Resolved', 'Accepted risk'].map((value) => <option key={value}>{value}</option>)}</select><span className="table-count">{findings.length} findings</span></div>
      {findings.length ? <div className="table-scroll"><table><thead><tr><th>Finding</th><th>Severity</th><th>Category</th><th>Hostname</th><th>Detected</th><th>Status</th></tr></thead><tbody>{findings.map((finding) => <tr key={finding.id}><td><strong className="finding-title">{finding.title}</strong><small className="finding-desc">{finding.description}</small><details className="finding-details"><summary>Evidence &amp; guidance</summary><pre>{JSON.stringify(finding.evidence, null, 2)}</pre><p>{finding.recommendation}</p></details></td><td><SeverityTag value={finding.severity} /></td><td>{finding.category}</td><td className="mono">{finding.hostname}</td><td>{date(finding.detected_at)}</td><td><select className="status-select" aria-label={`Status for ${finding.title}`} value={finding.status} onChange={(event) => void changeStatus(finding, event.target.value)}>{['Open', 'Acknowledged', 'Resolved', 'Accepted risk'].map((value) => <option key={value}>{value}</option>)}</select></td></tr>)}</tbody></table></div> : <EmptyInline title="No findings match" text="Findings are created only from observed assessment results. Try a scan or adjust filters." />}
    </section></>
}

function ScansPage({ organization }: { organization: Organization }) {
  const [scans, setScans] = useState<Scan[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [expandedScan, setExpandedScan] = useState(0)
  const [changes, setChanges] = useState<ScanChange[]>([])
  const load = () => getScans(organization.id).then(setScans).catch((issue) => setError(errorText(issue)))
  useEffect(() => { void load() }, [organization.id])
  useEffect(() => { if (!scans.some((scan) => ['queued', 'running'].includes(scan.status))) return; const timer = window.setInterval(() => void load(), 3000); return () => window.clearInterval(timer) }, [scans, organization.id])
  useEffect(() => { if (expandedScan) getScanChanges(expandedScan).then(setChanges).catch((issue) => setError(errorText(issue))) }, [expandedScan])
  const launch = async () => { setBusy(true); setError(''); try { await startScan(organization.id); await load() } catch (issue) { setError(errorText(issue)) } finally { setBusy(false) } }
  return <><PageHeading eyebrow="MONITORING / MANUAL ASSESSMENT" title="Scans" subtitle={`Scope is fixed to ${organization.root_domain}. One active scan per organization.`} action={<button className="button button-primary" disabled={busy || scans.some((scan) => ['queued', 'running'].includes(scan.status))} onClick={() => void launch()}>{busy ? <LoaderCircle className="spin" size={16} /> : <Radar size={16} />}Start scan</button>} />{error && <ErrorBanner message={error} />}
    <div className="scan-safety"><ShieldCheck size={17} /><span><strong>Authorized scope locked</strong> — passive certificate transparency plus DNS, and bounded HTTPS checks to validated public addresses. Redirects are never followed.</span></div>
    <section className="panel table-panel"><div className="panel-heading"><div><h2>Scan history</h2><p>{scans.length} recorded runs · newest first</p></div></div>{scans.length ? <div className="table-scroll"><table><thead><tr><th>Scan</th><th>Started</th><th>Status</th><th>New assets</th><th>Findings</th><th>Finished</th><th>Changes</th></tr></thead><tbody>{scans.map((scan) => <tr key={scan.id}><td className="mono">#{scan.id}</td><td>{date(scan.started_at)}</td><td><StatusTag value={scan.status} /></td><td>{scan.assets_found}</td><td>{scan.findings_found}</td><td>{date(scan.finished_at)}</td><td><button className="change-button" onClick={() => setExpandedScan(expandedScan === scan.id ? 0 : scan.id)}><Waypoints size={13} />Compare</button></td></tr>)}</tbody></table></div> : <EmptyInline title="No scan history" text="Start a manual scan to collect DNS and safe HTTPS observations." />}</section>
    {expandedScan > 0 && <section className="panel changes-panel"><div className="panel-heading"><div><h2>Changes in scan #{expandedScan}</h2><p>{changes.length} recorded changes since the previous completed scan</p></div></div>{changes.length ? <div className="change-list">{changes.map((change) => <div key={change.id}><span>{change.kind.replaceAll('_', ' ')}</span><strong>{change.hostname}</strong><time>{date(change.detected_at)}</time><pre>{JSON.stringify(change.details, null, 2)}</pre></div>)}</div> : <EmptyInline title="No changes recorded" text="This scan had no asset, DNS, HTTP, or TLS deltas to report." />}</section>}
    {scans.filter((scan) => scan.error).map((scan) => <div className="scan-warning" key={scan.id}><AlertTriangle size={15} /><div><strong>Scan #{scan.id} warnings</strong><pre>{scan.error}</pre></div></div>)}
  </>
}

function ReportsPage({ organization }: { organization: Organization }) {
  const [error, setError] = useState('')
  const download = async () => { try { const response = await api.get(`/organizations/${organization.id}/reports/assets.csv`, { responseType: 'blob' }); const url = URL.createObjectURL(response.data); const link = document.createElement('a'); link.href = url; link.download = `surfaceguard-${organization.id}-assets.csv`; link.click(); URL.revokeObjectURL(url) } catch (issue) { setError(errorText(issue)) } }
  return <><PageHeading eyebrow="REPORTING / EXPORT" title="Reports" subtitle="Exports are generated from observations stored for this organization." />{error && <ErrorBanner message={error} />}<section className="report-band"><div className="report-icon"><FileText size={22} /></div><div><h2>Asset inventory export</h2><p>CSV containing authorized scope, hostname, observed IPs, risk score and observation dates.</p><span className="scope-domain"><span className="dot" />{organization.root_domain}</span></div><button className="button button-secondary" onClick={() => void download()}><ArrowDownToLine size={16} />Export CSV</button></section><p className="notice report-note">PDF export is not included. Review scan-to-scan changes on the Scans page.</p></>
}

function SettingsPage({ organization, onUpdated }: { organization: Organization; onUpdated: () => Promise<void> }) {
  return <><PageHeading eyebrow="WORKSPACE / CONFIGURATION" title="Settings" subtitle="Organization scope and assessment safeguards" /><div className="settings-grid"><section className="panel"><div className="panel-heading"><div><h2>Authorized organization</h2><p>Scope domain is immutable after creation in this version.</p></div></div><dl className="definition-list"><dt>Organization</dt><dd>{organization.name}</dd><dt>Authorized root</dt><dd className="mono">{organization.root_domain}</dd><dt>Ownership</dt><dd>Provided by user; not independently verified</dd><dt>Network policy</dt><dd>Public IP destinations only</dd><dt>Request timeout</dt><dd>4 seconds per request</dd></dl></section><section className="panel"><div className="panel-heading"><div><h2>Service status</h2><p>Backend connection and current inventory</p></div></div><button className="button button-quiet" onClick={() => void onUpdated()}><RefreshCw size={15} />Refresh organization list</button><p className="notice">Private and loopback targets are blocked unless explicitly enabled by local backend configuration. Never enable that option for internet-facing deployments.</p></section></div></>
}

function SetupPage({ error, onCreated }: { error: string; onCreated: () => Promise<void> }) {
  const [name, setName] = useState(''); const [domain, setDomain] = useState(''); const [issue, setIssue] = useState(''); const [busy, setBusy] = useState(false)
  const submit = async (event: FormEvent) => { event.preventDefault(); setBusy(true); setIssue(''); try { const organization = await createOrganization(name, domain); localStorage.setItem('surfaceguard.organization', String(organization.id)); await onCreated() } catch (err) { setIssue(errorText(err)) } finally { setBusy(false) } }
  return <main className="setup-screen"><div className="setup-aside"><div className="brand"><span className="brand-mark"><Fingerprint size={21} /></span><span>surfaceguard<small>EXTERNAL EXPOSURE</small></span></div><div className="setup-mark"><Compass size={30} /><span>01 / DEFINE SCOPE</span></div><h1>Start with what<br />you’re authorized to see.</h1><p>Register an organization and its root domain. Every discovery result is checked against that boundary before it is stored.</p><div className="scope-rule"><ShieldCheck size={17} /><span>Scope ownership is not independently verified. Only add domains you are authorized to assess.</span></div></div><div className="setup-main"><form className="setup-form" onSubmit={(event) => void submit(event)}><div className="eyebrow">NEW WORKSPACE</div><h2>Create your organization</h2><p>Set up your first authorized asset inventory.</p>{(issue || error) && <ErrorBanner message={issue || error} />}<label>Organization name<input required minLength={2} maxLength={120} value={name} onChange={(event) => setName(event.target.value)} placeholder="Acme Security Team" /></label><label>Authorized root domain<input required value={domain} onChange={(event) => setDomain(event.target.value)} placeholder="example.com" /><small>Enter a domain only. URLs and IP addresses are rejected.</small></label><button className="button button-primary setup-submit" disabled={busy}>{busy ? <LoaderCircle className="spin" size={16} /> : <Plus size={16} />}Create workspace</button><div className="setup-foot"><ShieldCheck size={15} />No scanning happens until you explicitly start it.</div></form></div></main>
}

function RiskPill({ score, large = false }: { score: number; large?: boolean }) {
  const level = score >= 80 ? 'Critical' : score >= 60 ? 'High' : score >= 40 ? 'Medium' : score >= 20 ? 'Low' : 'Info'
  return <span className={`risk-pill risk-${level.toLowerCase()}${large ? ' large' : ''}`}><b>{score.toFixed(1)}</b><span>{level}</span></span>
}
function ApiConnection() {
  const [online, setOnline] = useState(false)
  useEffect(() => {
    const check = () => api.get('/health').then(() => setOnline(true)).catch(() => setOnline(false))
    void check()
    const timer = window.setInterval(() => void check(), 15000)
    return () => window.clearInterval(timer)
  }, [])
  return <div className="connection"><span className={`dot${online ? '' : ' offline'}`} />API {online ? 'connected' : 'unavailable'}</div>
}
function SeverityTag({ value }: { value: string }) { return <span className={`severity severity-${value.toLowerCase()}`}>{value}</span> }
function StatusTag({ value }: { value: string }) { return <span className={`scan-status status-${value.replaceAll('_', '-').toLowerCase()}`}><i />{value.replaceAll('_', ' ')}</span> }
function ErrorBanner({ message }: { message: string }) { return <div className="error-banner"><AlertTriangle size={16} /><span>{message}</span></div> }
function EmptyInline({ title, text }: { title: string; text: string }) { return <div className="empty-inline"><div className="empty-symbol"><ShieldCheck size={19} /></div><strong>{title}</strong><p>{text}</p></div> }
function EmptyChart({ message }: { message: string }) { return <div className="empty-chart"><div className="empty-symbol"><Waypoints size={19} /></div><span>{message}</span></div> }