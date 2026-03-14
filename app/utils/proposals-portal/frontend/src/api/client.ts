import { Proposal, CreateProposalInput, ProposalFilters, Directive } from '../types';

const API_URL = import.meta.env.VITE_API_URL || '';

async function fetchJSON<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ message: response.statusText }));
    throw new Error(error.message || `HTTP ${response.status}`);
  }

  return response.json();
}

// Proposals API
export async function fetchProposals(filters?: ProposalFilters): Promise<{ proposals: Proposal[]; total: number }> {
  const params = new URLSearchParams();
  if (filters?.status) params.set('status', filters.status);
  if (filters?.type) params.set('type', filters.type);
  if (filters?.author) params.set('author', filters.author);
  if (filters?.q) params.set('q', filters.q);

  const query = params.toString();
  const url = `${API_URL}/api/proposals${query ? `?${query}` : ''}`;
  return fetchJSON(url);
}

export async function fetchProposal(sk: string): Promise<{ proposal: Proposal }> {
  return fetchJSON(`${API_URL}/api/proposals/${encodeURIComponent(sk)}`);
}

export async function createProposal(input: CreateProposalInput): Promise<{ proposal: Proposal }> {
  return fetchJSON(`${API_URL}/api/proposals`, {
    method: 'POST',
    body: JSON.stringify(input),
  });
}

export async function approveProposal(sk: string): Promise<{ proposal: Proposal }> {
  return fetchJSON(`${API_URL}/api/proposals/${encodeURIComponent(sk)}/approve`, {
    method: 'PATCH',
  });
}

export async function rejectProposal(sk: string, reason?: string): Promise<{ proposal: Proposal }> {
  return fetchJSON(`${API_URL}/api/proposals/${encodeURIComponent(sk)}/reject`, {
    method: 'PATCH',
    body: JSON.stringify({ reason }),
  });
}

export async function deleteProposal(sk: string): Promise<void> {
  await fetchJSON(`${API_URL}/api/proposals/${encodeURIComponent(sk)}`, {
    method: 'DELETE',
  });
}

export async function generatePlan(sk: string): Promise<{ success: boolean }> {
  return fetchJSON(`${API_URL}/api/proposals/${encodeURIComponent(sk)}/generate-plan`, {
    method: 'POST',
  });
}

export async function fetchPlan(sk: string): Promise<{ plan: string | null }> {
  return fetchJSON(`${API_URL}/api/proposals/${encodeURIComponent(sk)}/plan`);
}

// Directives API
export async function fetchDirectives(): Promise<{ directives: Directive[]; total: number }> {
  return fetchJSON(`${API_URL}/api/directives`);
}

export async function fetchDirective(sk: string): Promise<{ directive: Directive }> {
  return fetchJSON(`${API_URL}/api/directives/${encodeURIComponent(sk)}`);
}
