// hooks/useResponsive.ts
// Role: Responsive breakpoint detection hook

'use client'

import { useState, useEffect } from 'react'

export function useResponsive() {
  const [width, setWidth] = useState(0)

  useEffect(() => {
    const update = () => setWidth(window.innerWidth)
    update()
    window.addEventListener('resize', update)
    return () => window.removeEventListener('resize', update)
  }, [])

  return {
    width,
    isMobile: width > 0 && width < 768,
    isTablet: width >= 768 && width < 1024,
    isDesktop: width >= 1024,
    isSmall: width > 0 && width < 1024,
  }
}
