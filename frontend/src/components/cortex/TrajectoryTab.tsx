import { LineChart, Line, AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import type { CortexPlayer } from '@/data/cortexTypes'
import Card from '@/components/ui/Card'
import SectionHeader from '@/components/ui/SectionHeader'
import { getChartProps, getChartTheme } from '@/lib/chartTheme'

export default function TrajectoryTab({ player }: { player: CortexPlayer }) {
  const theme = getChartTheme()
  const chart = getChartProps()

  return (
    <div>
      {/* Career Arc */}
      <SectionHeader title="Career Arc" />
      <Card className="mb-6">
        <ResponsiveContainer width="100%" height={350}>
          <LineChart data={player.timeline} margin={{ top: 10, right: 30, left: 10, bottom: 10 }}>
            <CartesianGrid {...chart.grid} />
            <XAxis dataKey="season" tick={chart.axisTick} axisLine={chart.axisLine} />
            <YAxis tick={chart.axisTick} axisLine={chart.axisLine} />
            <Tooltip
              contentStyle={chart.tooltipContentStyle}
              labelStyle={chart.tooltipLabelStyle}
              itemStyle={chart.tooltipItemStyle}
            />
            <Legend wrapperStyle={chart.legendStyle} />
            <Line type="monotone" dataKey="per" stroke={theme.primary} strokeWidth={2} dot={{ fill: theme.primary, r: 4 }} name="PER" />
            <Line type="monotone" dataKey="bpm" stroke={theme.pos} strokeWidth={2} dot={{ fill: theme.pos, r: 4 }} name="BPM" />
            <Line type="monotone" dataKey="epm" stroke={theme.warn} strokeWidth={2} dot={{ fill: theme.warn, r: 4 }} name="EPM" />
          </LineChart>
        </ResponsiveContainer>
      </Card>

      {/* Win Shares Trajectory */}
      <SectionHeader title="Win Shares Trajectory" />
      <Card>
        <ResponsiveContainer width="100%" height={300}>
          <AreaChart data={player.timeline} margin={{ top: 10, right: 30, left: 10, bottom: 10 }}>
            <CartesianGrid {...chart.grid} />
            <XAxis dataKey="season" tick={chart.axisTick} axisLine={chart.axisLine} />
            <YAxis tick={chart.axisTick} axisLine={chart.axisLine} />
            <Tooltip
              contentStyle={chart.tooltipContentStyle}
              labelStyle={chart.tooltipLabelStyle}
              itemStyle={chart.tooltipItemStyle}
              formatter={(value: unknown) => Number(value).toFixed(3)}
            />
            <Area type="monotone" dataKey="ws48" stroke={theme.primary} fill={theme.primary} fillOpacity={0.1} strokeWidth={2} name="WS/48" />
          </AreaChart>
        </ResponsiveContainer>
      </Card>
    </div>
  )
}
