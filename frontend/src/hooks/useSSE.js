import { useEffect, useRef } from 'react'

/**
 * Hook para consumir Server-Sent Events (SSE) do Flask.
 * handlers: { eventName: (data) => void }
 */
export function useSSE(url, handlers) {
  const handlersRef = useRef(handlers)
  handlersRef.current = handlers

  useEffect(() => {
    const es = new EventSource(url)

    Object.keys(handlers).forEach(eventName => {
      es.addEventListener(eventName, (e) => {
        try {
          const data = JSON.parse(e.data)
          handlersRef.current[eventName]?.(data)
        } catch {}
      })
    })

    es.onerror = () => {
      // Reconectar automaticamente é comportamento padrão do EventSource
    }

    return () => es.close()
  }, [url])
}
