import axios from 'axios'
import type { Asset, DashboardData, Finding, Organization, Scan, ScanChange } from './types'

export const api = axios.create({ baseURL: import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api', timeout: 10000 })

export const getOrganizations = async () => (await api.get<Organization[]>('/organizations')).data
export const createOrganization = async (name: string, root_domain: string) => (await api.post<Organization>('/organizations', { name, root_domain })).data
export const getDashboard = async (id: number) => (await api.get<DashboardData>(`/organizations/${id}/dashboard`)).data
export const getAssets = async (id: number, q = '') => (await api.get<Asset[]>(`/organizations/${id}/assets`, { params: { q } })).data
export const getAsset = async (id: number) => (await api.get<{ asset: Asset; observations: { kind: string; value: Record<string, unknown>; observed_at: string }[] }>(`/assets/${id}`)).data
export const getFindings = async (id: number, params: Record<string, string> = {}) => (await api.get<Finding[]>(`/organizations/${id}/findings`, { params })).data
export const updateFinding = async (id: number, status: string) => (await api.patch<Finding>(`/findings/${id}`, { status })).data
export const getScans = async (id: number) => (await api.get<Scan[]>(`/organizations/${id}/scans`)).data
export const getScanChanges = async (id: number) => (await api.get<ScanChange[]>(`/scans/${id}/changes`)).data
export const startScan = async (id: number) => (await api.post<Scan>(`/organizations/${id}/scans`)).data