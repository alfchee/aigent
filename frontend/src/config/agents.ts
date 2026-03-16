export type AgentOption = {
  id: string
  label: string
  description: string
}

export const AGENT_OPTIONS: AgentOption[] = [
  {
    id: 'default',
    label: 'Default',
    description: 'Asistente general para consultas mixtas.',
  },
  {
    id: 'planner',
    label: 'Planner',
    description: 'Planificación y descomposición de tareas.',
  },
  { id: 'coder', label: 'Coder', description: 'Implementación y depuración técnica.' },
]

export function findAgentById(id: string) {
  return AGENT_OPTIONS.find((a) => a.id === id) ?? AGENT_OPTIONS[0]
}
