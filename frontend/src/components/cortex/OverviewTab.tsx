import { Radar, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Cell, LabelList } from 'recharts'
import type { CortexPlayer } from '@/data/cortexTypes'
import Card from '@/components/ui/Card'
import SectionHeader from '@/components/ui/SectionHeader'
import Stat from '@/components/ui/Stat'
import { getChartTheme } from '@/lib/chartTheme'

export default function OverviewTab({ player }: { player: CortexPlayer }) {
  const t = player.traditional
  const a = player.advanced
  const theme = getChartTheme()

  const impactModels = [
    { name: 'RAPM', value: player.impact.rapm },
    { name: 'RPM', value: player.impact.rpm },
    { name: 'EPM', value: player.impact.epm },
    { name: 'LEBRON', value: player.impact.lebron },
    { name: 'DARKO', value: player.impact.darko },
    { name: 'LAKER', value: player.impact.laker },
    { name: 'MAMBA', value: player.impact.mamba },
  ]

  return (
    <div>
      {/* Traditional Stats */}
      <SectionHeader title="Traditional Stats" />
      <div className="grid grid-cols-3 sm:grid-cols-5 lg:grid-cols-9 gap-2">
        {[
          ['PPG', t.ppg], ['RPG', t.rpg], ['APG', t.apg], ['SPG', t.spg], ['BPG', t.bpg],
          ['FG%', (t.fgPct * 100).toFixed(1)], ['3P%', (t.threePct * 100).toFixed(1)],
          ['FT%', (t.ftPct * 100).toFixed(1)], ['TOV', t.tov],
        ].map(([label, val]) => (
          <Card key={label as string} variant="inset">
            <Stat label={label as string} value={val as string | number} size="md" />
          </Card>
        ))}
      </div>

      {/* Advanced Composites */}
      <SectionHeader title="Advanced Metrics" tag="COMPOSITE" />
      <div className="grid grid-cols-3 sm:grid-cols-5 lg:grid-cols-10 gap-2">
        {[
          ['PER', a.per.toFixed(1)], ['TS%', (a.ts * 100).toFixed(1)], ['WS/48', a.ws48.toFixed(3)],
          ['BPM', a.bpm.toFixed(1)], ['VORP', a.vorp.toFixed(1)], ['ORtg', a.ortg],
          ['DRtg', a.drtg], ['USG%', a.usg.toFixed(1)], ['OWS', a.ows.toFixed(1)], ['DWS', a.dws.toFixed(1)],
        ].map(([label, val]) => (
          <Card key={label as string} variant="inset">
            <Stat label={label as string} value={val as string | number} size="md" />
          </Card>
        ))}
      </div>

      {/* Two Column: Radar + Impact Models */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-8">
        <Card>
          <h4 className="text-caption text-text-muted uppercase tracking-wider mb-4">
            Percentile Profile
          </h4>
          <ResponsiveContainer width="100%" height={320}>
            <RadarChart data={player.radarData} cx="50%" cy="50%" outerRadius="75%">
              <PolarGrid stroke={theme.grid} />
              <PolarAngleAxis dataKey="stat" tick={{ fill: theme.axis, fontSize: 11 }} />
              <PolarRadiusAxis angle={90} domain={[0, 100]} tick={false} axisLine={false} />
              <Radar dataKey="value" stroke={theme.primary} fill={theme.primary} fillOpacity={0.15} strokeWidth={2} />
            </RadarChart>
          </ResponsiveContainer>
        </Card>

        <Card>
          <h4 className="text-caption text-text-muted uppercase tracking-wider mb-4">
            All-In-One Impact Models
          </h4>
          <ResponsiveContainer width="100%" height={320}>
            <BarChart data={impactModels} layout="vertical" margin={{ left: 60, right: 40 }}>
              <XAxis type="number" tick={{ fill: theme.axis, fontSize: 11 }} axisLine={{ stroke: theme.grid }} />
              <YAxis type="category" dataKey="name" tick={{ fill: theme.axis, fontSize: 12 }} axisLine={false} tickLine={false} />
              <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                {impactModels.map((entry, i) => (
                  <Cell key={i} fill={entry.value >= 0 ? theme.primary : theme.neg} />
                ))}
                <LabelList
                  dataKey="value"
                  position="right"
                  formatter={(v: unknown) => Number(v).toFixed(1)}
                  style={{ fill: theme.textPrimary, fontSize: 11 }}
                />
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Card>
      </div>
    </div>
  )
}
