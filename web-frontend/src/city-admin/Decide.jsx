import { useState } from 'react'
import { useSubmit } from '../shared/api'
import { Button, ErrorText, Field, inputCls } from '../shared/ui'

/** Approve / Reject buttons. Reject asks for the reason the member will see (FR-13). */
export default function Decide({ onApprove, onReject, approveLabel = 'Approve', small }) {
  const [rejecting, setRejecting] = useState(false)
  const approve = useSubmit(() => onApprove())
  const reject = useSubmit(({ reason }) => onReject(reason.trim()))
  const size = small ? 'h-8 px-3' : ''

  if (rejecting) return (
    <form onSubmit={reject.onSubmit} className="flex min-w-64 flex-col gap-2 text-left">
      <Field label="Reason (the member sees this)">
        <textarea name="reason" required maxLength={500} rows={2} autoFocus className={`${inputCls} h-auto py-2`} />
      </Field>
      <ErrorText>{reject.error}</ErrorText>
      <div className="flex justify-end gap-2">
        <Button variant="text" className={size} onClick={() => setRejecting(false)}>Back</Button>
        <Button type="submit" variant="danger" className={size} disabled={reject.busy}>{reject.busy ? 'Rejecting…' : 'Reject'}</Button>
      </div>
    </form>
  )
  return (
    <form onSubmit={approve.onSubmit} className="flex flex-col gap-2">
      <ErrorText>{approve.error}</ErrorText>
      <div className="flex justify-end gap-2">
        <Button variant="outline" className={size} onClick={() => setRejecting(true)}>Reject</Button>
        <Button type="submit" className={size} disabled={approve.busy}>{approve.busy ? 'Approving…' : approveLabel}</Button>
      </div>
    </form>
  )
}
