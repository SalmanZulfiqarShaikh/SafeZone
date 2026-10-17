import { useParams } from 'react-router'

export default function Responder() {
  const { token } = useParams<{ token: string }>()

  return (
    <main className="p-6">
      <h1 className="text-2xl font-semibold">Responder case</h1>
      <p className="text-muted-foreground">Case token: {token}</p>
      <p className="text-sm text-muted-foreground">
        Handoff link is read-only. Map, Navigate, vulnerability summary and Call button
        land here.
      </p>
    </main>
  )
}
