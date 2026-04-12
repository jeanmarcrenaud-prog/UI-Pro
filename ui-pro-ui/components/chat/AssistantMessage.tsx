// components/chat/AssistantMessage.tsx
import { useEffect, useState } from "react"

type Props = {
  content: string
}

export default function AssistantMessage({ content }: Props) {
  const [displayed, setDisplayed] = useState("")

  useEffect(() => {
    let i = 0

    const interval = setInterval(() => {
      setDisplayed(content.slice(0, i))
      i++
      if (i > content.length) clearInterval(interval)
    }, 10) // vitesse typing

    return () => clearInterval(interval)
  }, [content])

  return (
    <div className="bg-[#1e293b] text-white px-4 py-3 rounded-2xl max-w-xl shadow">
      <pre className="whitespace-pre-wrap">{displayed}</pre>

      {/* curseur */}
      <span className="animate-pulse">▍</span>
    </div>
  )
}
