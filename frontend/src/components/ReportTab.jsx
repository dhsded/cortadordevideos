import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell
} from 'recharts'
import { Video, Users, Scissors, Camera, Clock, TrendingUp } from 'lucide-react'

const KPI_CONFIG = [
  { key: 'total_videos_processed', label: 'Vídeos na fila',     icon: Video,    color: '#6C63FF' },
  { key: 'total_persons_found',    label: 'Pessoas encontradas', icon: Users,    color: '#8B5CF6' },
  { key: 'videos_cut',             label: 'Vídeos cortados',     icon: Scissors, color: '#10B981' },
  { key: 'photos_exported',        label: 'Fotos exportadas',    icon: Camera,   color: '#F59E0B' },
]

function fmt(seconds) {
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return m > 0 ? `${m}m ${s}s` : `${s}s`
}

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div className="card px-3 py-2 text-xs">
      <p className="text-text font-semibold">{label}</p>
      <p className="text-accent">{fmt(payload[0].value)}</p>
    </div>
  )
}

export default function ReportTab({ stats }) {
  if (!stats) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-center gap-4 animate-fade-in">
        <TrendingUp size={48} className="text-muted opacity-30" />
        <div>
          <p className="text-text font-semibold">Relatório de Desempenho</p>
          <p className="text-subtext text-sm mt-1">Execute um processamento para ver os resultados aqui.</p>
        </div>
      </div>
    )
  }

  const trackingTime = stats.tracking_time || 0
  const renderTime   = stats.video_render_time || 0
  const photoTime    = stats.image_export_time || 0
  const totalTime    = trackingTime + renderTime + photoTime

  const barData = [
    { name: 'Rastreamento IA', value: trackingTime, color: '#6C63FF' },
    { name: 'Renderização',    value: renderTime,   color: '#EF4444' },
    { name: 'Fotos',           value: photoTime,    color: '#10B981' },
  ].filter(d => d.value > 0)

  return (
    <div className="h-full overflow-y-auto p-4 space-y-4 animate-fade-in">

      {/* KPI cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {KPI_CONFIG.map(({ key, label, icon: Icon, color }) => (
          <div key={key} className="card p-4 flex items-center gap-4">
            <div className="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0"
              style={{ background: `${color}20` }}>
              <Icon size={18} style={{ color }} />
            </div>
            <div>
              <p className="text-2xl font-bold text-text leading-none">{stats[key] ?? 0}</p>
              <p className="text-[11px] text-subtext mt-0.5">{label}</p>
            </div>
          </div>
        ))}

        {/* Tempo total */}
        <div className="card p-4 flex items-center gap-4 col-span-2 lg:col-span-4">
          <div className="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 bg-blue-500/20">
            <Clock size={18} className="text-blue-400" />
          </div>
          <div className="flex-1">
            <p className="text-2xl font-bold text-text leading-none">{fmt(totalTime)}</p>
            <p className="text-[11px] text-subtext mt-0.5">Tempo total de processamento</p>
          </div>
          {/* Mini breakdown */}
          <div className="hidden lg:flex gap-6 text-xs text-subtext">
            <div className="text-center">
              <p className="text-accent font-semibold">{fmt(trackingTime)}</p>
              <p>Rastreamento</p>
            </div>
            <div className="text-center">
              <p className="text-danger font-semibold">{fmt(renderTime)}</p>
              <p>Renderização</p>
            </div>
            <div className="text-center">
              <p className="text-success font-semibold">{fmt(photoTime)}</p>
              <p>Fotos</p>
            </div>
          </div>
        </div>
      </div>

      {/* Bar chart */}
      <div className="card p-4">
        <p className="text-sm font-semibold text-text mb-4">Tempo por Fase (segundos)</p>
        <div className="h-48">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={barData} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1E1E2E" />
              <XAxis dataKey="name" tick={{ fill: '#6B6B8A', fontSize: 11 }} axisLine={false} tickLine={false} />
              <YAxis tickFormatter={v => `${v}s`} tick={{ fill: '#6B6B8A', fontSize: 11 }} axisLine={false} tickLine={false} />
              <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(108,99,255,0.05)' }} />
              <Bar dataKey="value" radius={[6, 6, 0, 0]}>
                {barData.map((entry, i) => (
                  <Cell key={i} fill={entry.color} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  )
}
