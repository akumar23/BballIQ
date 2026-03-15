import { LineChart, Line, AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import type { CortexPlayer } from '@/data/cortexTypes'
import { SectionHeader } from './shared'

export default function TrajectoryTab({ player }: { player: CortexPlayer }) {
  return (
    <div>
      {/* Career Arc */}
      <SectionHeader title="Career Arc" />
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4 mb-6">
        <ResponsiveContainer width="100%" height={350}>
          <LineChart data={player.timeline} margin={{ top: 10, right: 30, left: 10, bottom: 10 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
            <XAxis dataKey="season" tick={{ fill: '#6b7280', fontSize: 11 }} axisLine={{ stroke: '#e5e7eb' }} />
            <YAxis tick={{ fill: '#6b7280', fontSize: 11 }} axisLine={{ stroke: '#e5e7eb' }} />
            <Tooltip
              contentStyle={{ backgroundColor: '#ffffff', border: '1px solid #e5e7eb', borderRadius: 8, fontSize: 12 }}
              labelStyle={{ color: '#374151' }}
            />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            <Line type="monotone" dataKey="per" stroke="#2563eb" strokeWidth={2} dot={{ fill: '#2563eb', r: 4 }} name="PER" />
            <Line type="monotone" dataKey="bpm" stroke="#16a34a" strokeWidth={2} dot={{ fill: '#16a34a', r: 4 }} name="BPM" />
            <Line type="monotone" dataKey="epm" stroke="#f59e0b" strokeWidth={2} dot={{ fill: '#f59e0b', r: 4 }} name="EPM" />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Win Shares Trajectory */}
      <SectionHeader title="Win Shares Trajectory" />
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
        <ResponsiveContainer width="100%" height={300}>
          <AreaChart data={player.timeline} margin={{ top: 10, right: 30, left: 10, bottom: 10 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
            <XAxis dataKey="season" tick={{ fill: '#6b7280', fontSize: 11 }} axisLine={{ stroke: '#e5e7eb' }} />
            <YAxis tick={{ fill: '#6b7280', fontSize: 11 }} axisLine={{ stroke: '#e5e7eb' }} />
            <Tooltip
              contentStyle={{ backgroundColor: '#ffffff', border: '1px solid #e5e7eb', borderRadius: 8, fontSize: 12 }}
              labelStyle={{ color: '#374151' }}
              formatter={(value: unknown) => Number(value).toFixed(3)}
            />
            <Area type="monotone" dataKey="ws48" stroke="#2563eb" fill="#2563eb" fillOpacity={0.1} strokeWidth={2} name="WS/48" />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
