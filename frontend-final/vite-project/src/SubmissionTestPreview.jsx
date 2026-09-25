import { useState } from 'react'
import { Button } from 'antd'
import SubmissionModal from './SubmissionModal.jsx'

export default function SubmissionTestPreview() {
  const [open, setOpen] = useState(true)
  return (
    <div style={{ padding: 40 }}>
      <Button onClick={() => setOpen(true)}>Mở lại modal nộp bài</Button>
      <SubmissionModal
        open={open}
        onClose={() => setOpen(false)}
        draft={{ mstime: 5000 }}
        defaultTaskType="kis"
      />
    </div>
  )
}
