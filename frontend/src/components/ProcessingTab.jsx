import { useRef, useEffect } from 'react'
import { User } from 'lucide-react'

function ProgressBar({ value, max, color = 'bg-accent' }) {
  const pct = max > 0 ? Math.min(100, (value / max) * 100) : 0
  return (
    <div className="progress-track">
      <div
        className={`progress-bar ${color} relative overflow-hidden`}
        style={{ width: `${pct}%` }}
      >
        {/* Shimmer effect */}
        <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/20 to-transparent
          bg-[length:200%_100%] animate-shimmer" />
      </div>
    </div>
  )
}

export default function ProcessingTab({ processing, progress, queueProgress, logs, persons, previewFrame }) {
  const logRef = useRef(null)

  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight
    }
  }, [logs])

  const phasePct = progress.total > 0 ? (progress.current / progress.total) * 100 : 0

  return (
    <div className="flex flex-col h-full p-4 gap-4 overflow-hidden animate-fade-in">

      {/* Status card */}
      <div className="card p-4">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            {processing && <div className="glow-dot bg-accent" />}
            <span className="text-sm font-semibold text-text">
              {processing
                ? `⚡ Fase ${progress.phase}: ${progress.phase === 1 ? 'Rastreando rostos' : 'Renderizando'}`
                : '⏸ Aguardando'}
            </span>
          </div>
          <span className="text-xs text-subtext">
            {progress.total > 0 ? `${progress.current} / ${progress.total}` : ''}
          </span>
        </div>
        <ProgressBar
          value={progress.current}
          max={progress.total}
          color={progress.phase === 1 ? 'bg-accent' : 'bg-success'}
        />
        {progress.video && (
          <p className="text-[11px] text-subtext mt-1.5 truncate">{progress.video}</p>
        )}
      </div>

      {/* Persons gallery */}
      <div className="card p-4">
        <p className="section-label">Rostos Detectados ({persons.length})</p>
        {persons.length === 0 ? (
          <div className="flex items-center gap-3 text-subtext text-xs py-2">
            <User size={16} className="opacity-40" />
            Nenhum rosto detectado ainda
          </div>
        ) : (
          <div className="flex gap-3 overflow-x-auto pb-1">
            {persons.map((p, i) => (
              <div key={i} className="flex flex-col items-center gap-1.5 flex-shrink-0 animate-slide-up">
                <div className="w-14 h-14 rounded-xl overflow-hidden border-2 border-accent/30
                  shadow-glow-sm bg-card flex items-center justify-center">
                  {p.image ? (
                    <img
                      src={`data:image/jpeg;base64,${p.image}`}
                      alt={p.name}
                      className="w-full h-full object-cover"
                    />
                  ) : (
                    <User size={20} className="text-muted" />
                  )}
                </div>
                <span className="text-[10px] text-subtext font-medium">{p.name}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Preview do vídeo */}
      {previewFrame && (
        <div className="card overflow-hidden relative">
          <img
            src={previewFrame}
            alt="Preview"
            className="w-full object-contain max-h-52"
            style={{ imageRendering: 'crisp-edges' }}
          />
          <div className="absolute top-2 right-2 flex items-center gap-1.5 bg-black/60 rounded-full px-2.5 py-1">
            <div className="w-1.5 h-1.5 rounded-full bg-danger animate-pulse" />
            <span className="text-[10px] text-white font-semibold">AO VIVO</span>
          </div>
        </div>
      )}

      {/* Log console */}
      <div className="card flex flex-col flex-1 min-h-0 overflow-hidden">
        <div className="flex items-center justify-between px-4 py-3 border-b border-border">
          <p className="text-xs font-semibold text-subtext uppercase tracking-wider">Log do Sistema</p>
          {processing && (
            <div className="flex items-center gap-1.5">
              <div className="w-1.5 h-1.5 rounded-full bg-success animate-pulse" />
              <span className="text-[10px] text-success">ao vivo</span>
            </div>
          )}
        </div>
        <div
          ref={logRef}
          className="flex-1 overflow-y-auto p-4 font-mono text-[11px] space-y-0.5"
        >
          {logs.length === 0 ? (
            <p className="text-muted italic">Aguardando início do processamento...</p>
          ) : (
            logs.map((l, i) => {
              const isError   = l.text.includes('❌') || l.text.includes('Erro')
              const isSuccess = l.text.includes('✅') || l.text.includes('🎉')
              const isWarn    = l.text.includes('⚠')
              const isPhase   = l.text.startsWith('===')
              return (
                <div key={i} className={`leading-relaxed transition-colors
                  ${isError   ? 'text-danger'  : ''}
                  ${isSuccess ? 'text-success' : ''}
                  ${isWarn    ? 'text-warning' : ''}
                  ${isPhase   ? 'text-accent font-semibold mt-2' : ''}
                  ${!isError && !isSuccess && !isWarn && !isPhase ? 'text-subtext' : ''}
                `}>
                  <span className="text-muted mr-2">{l.ts}</span>
                  {l.text}
                </div>
              )
            })
          )}
        </div>
      </div>
    </div>
  )
}
