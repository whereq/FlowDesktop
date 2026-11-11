import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'

export function useSimAccounts() {
  return useQuery({ queryKey: ['sim-accounts'], queryFn: api.listSimAccounts })
}

export function useSimAccount(id: number | null) {
  return useQuery({
    queryKey: ['sim-account', id],
    queryFn: () => api.getSimAccount(id as number),
    enabled: id != null,
    refetchInterval: 30_000, // live-ish valuation
  })
}

export function useSimOrders(id: number | null) {
  return useQuery({
    queryKey: ['sim-orders', id],
    queryFn: () => api.listSimOrders(id as number),
    enabled: id != null,
    refetchInterval: 30_000,
  })
}

export function useSimSnapshots(id: number | null) {
  return useQuery({
    queryKey: ['sim-snapshots', id],
    queryFn: () => api.getSimSnapshots(id as number),
    enabled: id != null,
    staleTime: 600_000,
  })
}
