import { useEffect, useRef } from 'react'
import './ResponseEffects.css'

const FIREWORK_COLORS = ['#ff595e', '#ffca3a', '#8ac926', '#1982c4', '#6a4c93', '#ffffff', '#ff9f1c']

// Pháo hoa mừng khi DRES xác nhận đáp án đúng.
export default function SubmissionFireworks({ active, onDone }) {
  const canvasRef = useRef(null)

  useEffect(() => {
    if (!active) return undefined
    const canvas = canvasRef.current
    if (!canvas) return undefined
    const ctx = canvas.getContext('2d')
    let width = (canvas.width = window.innerWidth)
    let height = (canvas.height = window.innerHeight)

    const handleResize = () => {
      width = canvas.width = window.innerWidth
      height = canvas.height = window.innerHeight
    }
    window.addEventListener('resize', handleResize)

    let particles = []
    const spawnBurst = () => {
      const x = width * (0.18 + Math.random() * 0.64)
      const y = height * (0.15 + Math.random() * 0.35)
      const color = FIREWORK_COLORS[Math.floor(Math.random() * FIREWORK_COLORS.length)]
      const count = 46
      for (let i = 0; i < count; i += 1) {
        const angle = (Math.PI * 2 * i) / count
        const speed = 2 + Math.random() * 3.2
        particles.push({
          x,
          y,
          vx: Math.cos(angle) * speed,
          vy: Math.sin(angle) * speed,
          life: 1,
          decay: 0.011 + Math.random() * 0.012,
          color,
          size: 2 + Math.random() * 2,
        })
      }
    }

    let burstCount = 0
    const totalBursts = 5
    spawnBurst()
    burstCount += 1
    const burstInterval = setInterval(() => {
      spawnBurst()
      burstCount += 1
      if (burstCount >= totalBursts) clearInterval(burstInterval)
    }, 280)

    let animationFrame
    let stopTimeout
    const tick = () => {
      ctx.clearRect(0, 0, width, height)
      particles.forEach((p) => {
        p.x += p.vx
        p.y += p.vy
        p.vy += 0.035
        p.life -= p.decay
        ctx.globalAlpha = Math.max(p.life, 0)
        ctx.fillStyle = p.color
        ctx.beginPath()
        ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2)
        ctx.fill()
      })
      particles = particles.filter((p) => p.life > 0)
      ctx.globalAlpha = 1
      animationFrame = requestAnimationFrame(tick)
    }
    tick()

    stopTimeout = setTimeout(() => {
      onDone?.()
    }, totalBursts * 280 + 1400)

    return () => {
      clearInterval(burstInterval)
      clearTimeout(stopTimeout)
      cancelAnimationFrame(animationFrame)
      window.removeEventListener('resize', handleResize)
      ctx.clearRect(0, 0, width, height)
    }
  }, [active, onDone])

  if (!active) return null
  return <canvas ref={canvasRef} className="submission-fireworks" />
}
