import { useState, useEffect } from 'react'
import {
  Plus, Trash2, FolderOpen, Play, Square,
  Settings, Zap, Film, ChevronRight
} from 'lucide-react'

const STATUS_BADGE = {
  queued:     { cls: 'badge-queue',   label: '⏳ Na fila'      },
  processing: { cls: 'badge-active',  label: '⚡ Processando'  },
  done:       { cls: 'badge-done',    label: '✅ Concluído'     },
  cancelled:  { cls: 'badge-error',   label: '✕ Cancelado'     },
  no_persons: { cls: 'badge-warning', label: '⚠ Sem pessoas'   },
  error:      { cls: 'badge-error',   label: '❌ Erro'          },
}

export default function Sidebar({
  processing, videoStatuses,
  onStartProcessing, onCancelProcessing, onOpenSettings,
  queueProgress,
}) {
  const [queue, setQueue]       = useState([])
  const [outputDir, setOutputDir] = useState(null)
  const [status, setStatus]     = useState(null)   // mensagem de status rápido

  // Buscar fila inicial
  useEffect(() => {
    fetch('/api/queue').then(r => r.json()).then(setQueue)
    fetch('/api/output').then(r => r.json()).then(d => setOutputDir(d.output_dir))
  }, [])

  const addVideos = async () => {
    const res = await fetch('/api/dialog/videos', { method: 'POST' })
    const { paths } = await res.json()
    if (!paths.length) return
    const res2 = await fetch('/api/queue/add', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ paths })
    })
    const d = await res2.json()
    setQueue(d.queue)
    setStatus(`✅ ${paths.length} vídeo(s) adicionado(s)`)
    setTimeout(() => setStatus(null), 3000)
  }

  const removeVideo = async (path) => {
    const res = await fetch('/api/queue/remove', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path })
    })
    const d = await res.json()
    setQueue(d.queue)
  }

  const clearQueue = async () => {
    await fetch('/api/queue/clear', { method: 'POST' })
    setQueue([])
  }

  const selectOutput = async () => {
    const res = await fetch('/api/dialog/output', { method: 'POST' })
    const { path } = await res.json()
    if (path) {
      setOutputDir(path)
      setStatus(`📁 ${path.split(/[\\/]/).pop()}`)
      setTimeout(() => setStatus(null), 3000)
    }
  }

  const queuePct = queueProgress.total
    ? queueProgress.done / queueProgress.total
    : 0

  return (
    <aside className="flex flex-col w-72 min-w-[18rem] h-full bg-surface border-r border-border overflow-hidden">

      {/* Logo */}
      <div className="px-5 py-5 border-b border-border">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-accent/20 flex items-center justify-center shadow-glow-sm">
            <Zap size={18} className="text-accent" />
          </div>
          <div>
            <p className="font-bold text-text leading-none">Auto-Cutter Pro</p>
            <p className="text-[11px] text-subtext mt-0.5">Edição Profissional</p>
          </div>
        </div>
      </div>

      {/* Queue section */}
      <div className="flex flex-col flex-1 min-h-0 px-4 pt-5">
        <div className="section-label">Fila de Vídeos</div>

        {/* Add + Clear buttons */}
        <div className="flex gap-2 mb-3">
          <button onClick={addVideos} disabled={processing} className="btn-primary flex-1">
            <Plus size={15} /> Adicionar
          </button>
          <button onClick={clearQueue} disabled={processing || !queue.length} className="btn-ghost">
            <Trash2 size={14} />
          </button>
        </div>

        {/* Queue list */}
        <div className="flex-1 overflow-y-auto space-y-2 min-h-0 pr-0.5">
          {queue.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-32 text-center">
              <Film size={28} className="text-muted mb-2 opacity-50" />
              <p className="text-subtext text-xs">Nenhum vídeo na fila</p>
              <p className="text-muted text-[10px] mt-1">Clique em Adicionar</p>
            </div>
          ) : (
            queue.map((path) => {
              const name = path.split(/[\\/]/).pop()
              const rawStatus = videoStatuses[path] || 'queued'
              const { cls, label } = STATUS_BADGE[rawStatus] || STATUS_BADGE.queued
              const isActive = rawStatus === 'processing'
              return (
                <div
                  key={path}
                  className={`card p-3 flex items-center gap-3 group transition-all duration-200
                    ${isActive ? 'border-accent/40 shadow-glow-sm' : ''}`}
                >
                  <div className={`w-7 h-7 rounded-md flex items-center justify-center flex-shrink-0
                    ${isActive ? 'bg-accent/20' : 'bg-border'}`}>
                    <Film size={13} className={isActive ? 'text-accent' : 'text-muted'} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-medium text-text truncate">{name}</p>
                    <span className={`${cls} mt-1`}>{label}</span>
                  </div>
                  {!processing && (
                    <button
                      onClick={() => removeVideo(path)}
                      className="opacity-0 group-hover:opacity-100 p-1 rounded hover:text-danger transition-all"
                    >
                      <Trash2 size={12} />
                    </button>
                  )}
                </div>
              )
            })
          )}
        </div>

        {/* Queue progress bar */}
        {queueProgress.total > 0 && (
          <div className="mt-3 pt-3 border-t border-border">
            <div className="flex justify-between text-[11px] text-subtext mb-1.5">
              <span>Progresso da fila</span>
              <span className="text-success font-medium">
                {queueProgress.done} / {queueProgress.total}
              </span>
            </div>
            <div className="progress-track">
              <div
                className="progress-bar bg-success"
                style={{ width: `${queuePct * 100}%` }}
              />
            </div>
          </div>
        )}
      </div>

      {/* Output + Actions */}
      <div className="px-4 pt-4 pb-5 border-t border-border space-y-3">
        {/* Output dir */}
        <div>
          <div className="section-label">Pasta de Saída</div>
          <button onClick={selectOutput} disabled={processing} className="btn-ghost w-full justify-start">
            <FolderOpen size={14} />
            <span className="truncate text-xs">
              {outputDir ? outputDir.split(/[\\/]/).pop() : "Padrão (output_cortes)"}
            </span>
          </button>
        </div>

        {/* Status flash */}
        {status && (
          <p className="text-[11px] text-success text-center animate-fade-in">{status}</p>
        )}

        {/* Settings */}
        <button onClick={onOpenSettings} disabled={processing} className="btn-ghost w-full">
          <Settings size={14} /> Configurações
        </button>

        {/* Start / Cancel */}
        {!processing ? (
          <button
            onClick={onStartProcessing}
            disabled={queue.length === 0}
            className="btn-primary w-full justify-center text-base py-3"
          >
            <Play size={16} fill="currentColor" /> Iniciar Processamento
          </button>
        ) : (
          <button onClick={onCancelProcessing} className="btn-danger w-full justify-center py-3">
            <Square size={14} fill="currentColor" /> Cancelar
          </button>
        )}
      </div>
    </aside>
  )
}
