import { useState, useEffect } from 'react'
import { X, Save } from 'lucide-react'

const PRESETS = {
  mode:         ['Ambos', 'Apenas Vídeo', 'Apenas Imagens'],
  duration:     ['10', '15', '20', '30', '40', '50'],
  min_dur:      ['3', '5', '8', '10', '12', '15'],
  photos:       ['5', '10', '15', '20'],
  quality:      ['Baixa', 'Média', 'Boa', 'Alta', 'Superior'],
  hw:           ['CPU', 'NVIDIA', 'AMD', 'Intel'],
  sound:        ['Nenhum', 'Soft Bell', 'Success Chime', 'Arcade Level Up'],
  precision:    ['Alta (a cada 5 frames)', 'Média (a cada 10 frames)', 'Rápida (a cada 15 frames)'],
}

function SelectField({ label, field, settings, onChange }) {
  return (
    <div>
      <label className="block text-xs text-subtext font-medium mb-1.5">{label}</label>
      <select
        className="select"
        value={settings[field] ?? ''}
        onChange={e => onChange({ ...settings, [field]: e.target.value })}
      >
        {PRESETS[field].map(v => <option key={v} value={v}>{v}</option>)}
      </select>
    </div>
  )
}

export default function SettingsModal({ onClose }) {
  const [settings, setSettings] = useState(null)
  const [saved, setSaved]       = useState(false)

  useEffect(() => {
    fetch('/api/settings').then(r => r.json()).then(setSettings)
  }, [])

  const save = async () => {
    await fetch('/api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(settings),
    })
    setSaved(true)
    setTimeout(() => { setSaved(false); onClose() }, 800)
  }

  const showVideo = settings?.mode !== 'Apenas Imagens'

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 animate-fade-in">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />

      {/* Modal */}
      <div className="relative card w-full max-w-md max-h-[90vh] overflow-y-auto animate-slide-up">
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-border sticky top-0 bg-card z-10">
          <div>
            <h2 className="font-bold text-text">⚙️ Configurações</h2>
            <p className="text-[11px] text-subtext mt-0.5">Parâmetros de processamento</p>
          </div>
          <button onClick={onClose} className="btn-ghost p-2">
            <X size={16} />
          </button>
        </div>

        {!settings ? (
          <div className="p-6 text-center text-subtext text-sm">Carregando...</div>
        ) : (
          <div className="p-5 space-y-4">
            <div>
              <div className="section-label">Modo de Operação</div>
              <SelectField label="Modo" field="mode" settings={settings} onChange={setSettings} />
            </div>

            {showVideo && (
              <div>
                <div className="section-label">Vídeo</div>
                <div className="space-y-3">
                  <SelectField label="Duração máxima (s)" field="duration" settings={settings} onChange={setSettings} />
                  <SelectField label="Duração mínima / câmera lenta (s)" field="min_dur" settings={settings} onChange={setSettings} />
                  <SelectField label="Qualidade" field="quality" settings={settings} onChange={setSettings} />
                  <SelectField label="Aceleração de hardware" field="hw" settings={settings} onChange={setSettings} />
                </div>
              </div>
            )}

            <div>
              <div className="section-label">IA</div>
              <div className="space-y-3">
                <SelectField label="Precisão de rastreamento" field="precision" settings={settings} onChange={setSettings} />
                <SelectField label="Fotos extraídas por pessoa" field="photos" settings={settings} onChange={setSettings} />
              </div>
            </div>

            <div>
              <div className="section-label">Notificação</div>
              <SelectField label="Sinal sonoro de conclusão" field="sound" settings={settings} onChange={setSettings} />
            </div>
          </div>
        )}

        {/* Footer */}
        <div className="p-5 border-t border-border sticky bottom-0 bg-card flex gap-3">
          <button onClick={onClose} className="btn-ghost flex-1 justify-center">
            Cancelar
          </button>
          <button onClick={save} disabled={!settings} className="btn-primary flex-1 justify-center">
            {saved ? '✅ Salvo!' : <><Save size={14} /> Salvar</>}
          </button>
        </div>
      </div>
    </div>
  )
}
