import { useRef, useEffect, useState } from 'react'
import { User, RotateCcw, RotateCw } from 'lucide-react'

const QUALITY_OPTIONS = [
  { label: 'Total', value: 'Total' },
  { label: '½',     value: 'Metade' },
  { label: '¼',     value: '1/4' },
  { label: 'Off',   value: 'Desligado' },
]

function ProgressBar({ value, max, color = 'bg-accent' }) {
  const pct = max > 0 ? Math.min(100, (value / max) * 100) : 0
  return (
    <div className="progress-track">
      <div
        className={`progress-bar ${color} relative overflow-hidden`}
        style={{ width: `${pct}%` }}
      >
        <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/20 to-transparent
          bg-[length:200%_100%] animate-shimmer" />
      </div>
    </div>
  )
}

export default function ProcessingTab({ processing, progress, queueProgress, logs, persons, previewFrame }) {
  const logRef = useRef(null)
  const [rotation, setRotation]   = useState(0)
  const [quality, setQuality]     = useState('Metade')

  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight
    }
  }, [logs])

  // Carregar quality atual das configurações
  useEffect(() => {
    fetch('/api/settings').then(r => r.json()).then(s => {
      if (s?.preview_mode) setQuality(s.preview_mode)
    })
  }, [])

  const rotate = (dir) => setRotation(r => (r + dir * 90 + 360) % 360)

  const changeQuality = async (q) => {
    setQuality(q)
    const s = await fetch('/api/settings').then(r => r.json())
    await fetch('/api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...s, preview_mode: q }),
    })
  }

  const phasePct = progress.total > 0 ? (progress.current / progress.total) * 100 : 0
  const isRotated90 = rotation === 90 || rotation === 270

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

      {/* Preview do vídeo com controles integrados */}
      {(previewFrame || processing) && (
        <div className="card overflow-hidden relative bg-black">
          {/* Imagem com rotação CSS */}
          <div
            className="flex items-center justify-center overflow-hidden"
            style={{ minHeight: '120px', maxHeight: '220px' }}
          >
            {previewFrame ? (
              <img
                src={previewFrame}
                alt="Preview"
                style={{
                  transform: `rotate(${rotation}deg)`,
                  transition: 'transform 0.3s ease',
                  maxHeight: isRotated90 ? '200px' : '220px',
                  maxWidth: isRotated90 ? '120px' : '100%',
                  objectFit: 'contain',
                }}
              />
            ) : (
              <div className="text-muted text-xs py-8">Aguardando frames...</div>
            )}
          </div>

          {/* Barra superior: AO VIVO + controles de rotação */}
          <div className="absolute top-0 left-0 right-0 flex items-center justify-between px-2 py-1.5 bg-gradient-to-b from-black/70 to-transparent">
            {/* AO VIVO */}
            {previewFrame && (
              <div className="flex items-center gap-1.5">
                <div className="w-1.5 h-1.5 rounded-full bg-danger animate-pulse" />
                <span className="text-[10px] text-white font-semibold">AO VIVO</span>
              </div>
            )}
            {!previewFrame && <div />}

            {/* Botões de rotação */}
            <div className="flex items-center gap-1">
              <button
                onClick={() => rotate(-1)}
                className="p-1 rounded bg-black/50 hover:bg-black/80 text-white transition-colors"
                title="Girar esquerda"
              >
                <RotateCcw size={12} />
              </button>
              <span className="text-[10px] text-white/70 px-1">{rotation}°</span>
              <button
                onClick={() => rotate(1)}
                className="p-1 rounded bg-black/50 hover:bg-black/80 text-white transition-colors"
                title="Girar direita"
              >
                <RotateCw size={12} />
              </button>
            </div>
          </div>

          {/* Barra inferior: qualidade do preview */}
          <div className="absolute bottom-0 left-0 right-0 flex items-center justify-center gap-1 px-2 py-1.5 bg-gradient-to-t from-black/70 to-transparent">
            {QUALITY_OPTIONS.map(opt => (
              <button
                key={opt.value}
                onClick={() => changeQuality(opt.value)}
                className={`text-[10px] font-semibold px-2 py-0.5 rounded transition-all
                  ${quality === opt.value
                    ? 'bg-accent text-white'
                    : 'bg-black/50 text-white/60 hover:text-white hover:bg-black/70'}`}
              >
                {opt.label}
              </button>
            ))}
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
