import { Icon } from '../ui/Icon'

export type FlowStep = 'lote' | 'lluvia' | 'resultado'

interface StepNavProps {
  currentStep: FlowStep
  completedSteps: FlowStep[]
  onSelectStep: (step: FlowStep) => void
  lotSummary?: string | null
  rainSummary?: string | null
  resultSummary?: string | null
  className?: string
}

export function StepNav({
  currentStep,
  completedSteps,
  onSelectStep,
  lotSummary,
  rainSummary,
  resultSummary,
  className = '',
}: StepNavProps) {
  const steps: { id: FlowStep; title: string; summary?: string | null }[] = [
    { id: 'lote', title: '1. Lote', summary: lotSummary },
    { id: 'lluvia', title: '2. Lluvia', summary: rainSummary },
    { id: 'resultado', title: '3. Resultado', summary: resultSummary },
  ]

  return (
    <nav className={`step-nav ${className}`} aria-label="Flujo de simulación">
      <ol className="step-nav-list">
        {steps.map((st) => {
          const isCurrent = currentStep === st.id
          const isDone = completedSteps.includes(st.id) && !isCurrent
          const isPending = !isCurrent && !isDone
          const canClick = isDone || isCurrent

          return (
            <li
              key={st.id}
              className={`step-nav-item ${isCurrent ? 'current' : ''} ${isDone ? 'done' : ''} ${isPending ? 'pending' : ''}`}
            >
              <button
                type="button"
                className="step-nav-btn"
                onClick={() => canClick && onSelectStep(st.id)}
                disabled={!canClick}
                aria-current={isCurrent ? 'step' : undefined}
              >
                <span className="step-nav-bullet" aria-hidden="true">
                  {isDone ? <Icon name="check" size={12} /> : null}
                  {isCurrent ? <span className="step-dot" /> : null}
                </span>
                <span className="step-nav-content">
                  <span className="step-nav-title">{st.title}</span>
                  {st.summary && (
                    <span className="step-nav-summary">{st.summary}</span>
                  )}
                </span>
              </button>
            </li>
          )
        })}
      </ol>
    </nav>
  )
}
