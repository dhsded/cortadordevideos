import { useState, useEffect, useRef, useCallback } from 'react'
import Sidebar from './components/Sidebar'
import ProcessingTab from './components/ProcessingTab'
import ReportTab from './components/ReportTab'
import BatchTab from './components/BatchTab'
import SettingsModal from './components/SettingsModal'
import { useSSE } from './hooks/useSSE'

const TABS = [
  { id: 'processing', label: '⚡ Processamento' },
  { id: 'report',     label: '📊 Relatório'     },
  { id: 'batch',      label: '🎞️ Editor em Lote' },
]

export default function App() {
  const [activeTab, setActiveTab]     = useState('processing')
  const [showSettings, setShowSettings] = useState(false)
  const [stats, setStats]             = useState(null)
  const [processing, setProcessing]   = useState(false)
  const [logs, setLogs]               = useState([])
  const [persons, setPersons]         = useState([])
  const [progress, setProgress]       = useState({ current: 0, total: 100, phase: 1 })
  const [queueProgress, setQueueProgress] = useState({ done: 0, total: 0 })
  const [videoStatuses, setVideoStatuses] = useState({})

  const appendLog = useCallback((text) => {
    const ts = new Date().toLocaleTimeString('pt-BR', { hour12: false })
    setLogs(prev => [...prev.slice(-400), { ts, text }])
  }, [])

  // ── SSE listener ──────────────────────────────────────────────────────────
  useSSE('/api/stream', {
    log:            (d) => appendLog(d.text),
    started:        (d) => { setProcessing(true); setQueueProgress({ done: 0, total: d.total }); setPersons([]); setLogs([]) },
    progress:       (d) => setProgress(d),
    queue_progress: (d) => setQueueProgress(d),
    new_person:     (d) => setPersons(prev => [...prev, d]),
    video_start:    (d) => appendLog(`▶ ${d.name} (${d.index + 1}/${d.total})`),
    video_status:   (d) => setVideoStatuses(prev => ({ ...prev, [d.path]: d.status })),
    done:           (d) => { setProcessing(false); setStats(d); setActiveTab('report') },
    error:          (d) => { setProcessing(false); appendLog(`❌ ${d.message}`) },
  })

  return (
    <div className="flex h-screen overflow-hidden bg-bg font-sans">
      {/* Sidebar */}
      <Sidebar
        processing={processing}
        videoStatuses={videoStatuses}
        onStartProcessing={startProcessing}
        onCancelProcessing={cancelProcessing}
        onOpenSettings={() => setShowSettings(true)}
        queueProgress={queueProgress}
      />

      {/* Main area */}
      <div className="flex flex-col flex-1 min-w-0 overflow-hidden">
        {/* Tab bar */}
        <div className="flex items-center gap-1 px-4 pt-4 pb-0 border-b border-border bg-surface">
          {TABS.map(t => (
            <button
              key={t.id}
              onClick={() => setActiveTab(t.id)}
              className={`px-4 py-2 text-sm font-medium rounded-t-lg transition-all duration-200 border-b-2 -mb-px
                ${activeTab === t.id
                  ? 'text-accent border-accent bg-card'
                  : 'text-subtext border-transparent hover:text-text hover:border-border'}`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {/* Tab content */}
        <div className="flex-1 overflow-hidden">
          {activeTab === 'processing' && (
            <ProcessingTab
              processing={processing}
              progress={progress}
              queueProgress={queueProgress}
              logs={logs}
              persons={persons}
            />
          )}
          {activeTab === 'report' && <ReportTab stats={stats} />}
          {activeTab === 'batch'  && <BatchTab />}
        </div>
      </div>

      {showSettings && <SettingsModal onClose={() => setShowSettings(false)} />}
    </div>
  )
}

async function startProcessing() {
  await fetch('/api/process/start', { method: 'POST' })
}
async function cancelProcessing() {
  await fetch('/api/process/cancel', { method: 'POST' })
}
