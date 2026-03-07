import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatMetric(value: number | null): string {
  if (value === null) return '-'
  return Number(value).toFixed(1)
}

export function getPercentileColor(percentile: number | null): string {
  if (percentile === null) return 'text-gray-400'
  if (percentile >= 90) return 'text-green-600'
  if (percentile >= 75) return 'text-green-500'
  if (percentile >= 50) return 'text-yellow-500'
  if (percentile >= 25) return 'text-orange-500'
  return 'text-red-500'
}
