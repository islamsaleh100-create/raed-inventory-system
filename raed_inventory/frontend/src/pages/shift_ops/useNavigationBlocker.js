// useNavigationBlocker.js — in-app leave guard for BrowserRouter (useBlocker needs data router).
import { useContext, useEffect, useRef } from 'react'
import { UNSAFE_NavigationContext as NavigationContext } from 'react-router-dom'

export function useNavigationBlocker(when, message) {
  const { navigator } = useContext(NavigationContext)
  const whenRef = useRef(when)
  whenRef.current = when

  useEffect(() => {
    const push = navigator.push
    const replace = navigator.replace

    navigator.push = (...args) => {
      if (whenRef.current && !window.confirm(message)) return
      push.apply(navigator, args)
    }
    navigator.replace = (...args) => {
      if (whenRef.current && !window.confirm(message)) return
      replace.apply(navigator, args)
    }

    return () => {
      navigator.push = push
      navigator.replace = replace
    }
  }, [navigator, message])
}

export default useNavigationBlocker
