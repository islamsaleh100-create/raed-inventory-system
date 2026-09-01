// useNavigationBlocker.js — in-app leave guard via react-router useBlocker (data router).
import { useEffect, useRef } from 'react'
import { useBlocker } from 'react-router-dom'

export function useNavigationBlocker(when, message) {
  const blocker = useBlocker(when)
  const messageRef = useRef(message)
  messageRef.current = message

  useEffect(() => {
    if (blocker.state !== 'blocked') return
    const ok = window.confirm(messageRef.current)
    if (ok) {
      blocker.proceed()
    } else {
      blocker.reset()
    }
  }, [blocker, blocker.state])
}

export default useNavigationBlocker
