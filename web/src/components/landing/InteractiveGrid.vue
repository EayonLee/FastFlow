<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'

const canvasRef = ref<HTMLCanvasElement | null>(null)
const mouse = { x: 0, y: 0 }

const draw = (ctx: CanvasRenderingContext2D, width: number, height: number, _time: number) => {
  ctx.clearRect(0, 0, width, height)
  
  const gridSize = 40
  const cols = Math.ceil(width / gridSize)
  const rows = Math.ceil(height / gridSize)
  
  // Base grid
  // Using a slightly tinted green for a tech feel, slightly increased opacity
  ctx.strokeStyle = 'rgba(0, 255, 65, 0.08)' 
  ctx.lineWidth = 1
  
  // Draw vertical lines
  for (let i = 0; i <= cols; i++) {
    const x = i * gridSize
    ctx.beginPath()
    ctx.moveTo(x, 0)
    ctx.lineTo(x, height)
    ctx.stroke()
  }
  
  // Draw horizontal lines
  for (let i = 0; i <= rows; i++) {
    const y = i * gridSize
    ctx.beginPath()
    ctx.moveTo(0, y)
    ctx.lineTo(width, y)
    ctx.stroke()
  }

  // Mouse crosshair highlight effect
  // Calculate nearest grid lines to mouse
  const nearestX = Math.round(mouse.x / gridSize) * gridSize
  const nearestY = Math.round(mouse.y / gridSize) * gridSize

  // Draw highlight crosshair
  const gradientSize = 300
  
  // Vertical highlight
  const vGradient = ctx.createLinearGradient(0, nearestY - gradientSize, 0, nearestY + gradientSize)
  vGradient.addColorStop(0, 'rgba(0, 255, 65, 0)')
  vGradient.addColorStop(0.5, 'rgba(0, 255, 65, 0.3)')
  vGradient.addColorStop(1, 'rgba(0, 255, 65, 0)')
  
  ctx.strokeStyle = vGradient
  ctx.lineWidth = 2
  ctx.beginPath()
  ctx.moveTo(nearestX, 0)
  ctx.lineTo(nearestX, height)
  ctx.stroke()

  // Horizontal highlight
  const hGradient = ctx.createLinearGradient(nearestX - gradientSize, 0, nearestX + gradientSize, 0)
  hGradient.addColorStop(0, 'rgba(0, 255, 65, 0)')
  hGradient.addColorStop(0.5, 'rgba(0, 255, 65, 0.3)')
  hGradient.addColorStop(1, 'rgba(0, 255, 65, 0)')
  
  ctx.strokeStyle = hGradient
  ctx.beginPath()
  ctx.moveTo(0, nearestY)
  ctx.lineTo(width, nearestY)
  ctx.stroke()

  // Interactive points - Spotlight Effect (No Lines)
  ctx.fillStyle = '#00ff41'
  
  for (let i = 0; i <= cols; i++) {
    for (let j = 0; j <= rows; j++) {
      const x = i * gridSize
      const y = j * gridSize
      
      const dx = mouse.x - x
      const dy = mouse.y - y
      const dist = Math.sqrt(dx * dx + dy * dy)
      const maxDist = 200 // Increased range for softer glow
      
      if (dist < maxDist) {
        // Calculate opacity based on distance - smooth falloff
        const alpha = Math.pow(1 - dist / maxDist, 2) * 0.8
        
        // Draw glowy point
        ctx.fillStyle = `rgba(0, 255, 65, ${alpha})`
        ctx.beginPath()
        // Slight size variation based on proximity
        const size = 1.5 + (1 - dist / maxDist) * 1.5
        ctx.arc(x, y, size, 0, Math.PI * 2)
        ctx.fill()
      }
    }
  }
}

const handleResize = () => {
  if (!canvasRef.value) return
  canvasRef.value.width = window.innerWidth
  canvasRef.value.height = window.innerHeight
}

const handleMouseMove = (e: MouseEvent) => {
  mouse.x = e.clientX
  mouse.y = e.clientY
}

onMounted(() => {
  if (!canvasRef.value) return
  
  handleResize()
  window.addEventListener('resize', handleResize)
  window.addEventListener('mousemove', handleMouseMove)
  
  const ctx = canvasRef.value.getContext('2d')
  if (!ctx) return
  
  let animationFrameId: number
  const render = (time: number) => {
    if (!canvasRef.value) return
    draw(ctx, canvasRef.value.width, canvasRef.value.height, time)
    animationFrameId = requestAnimationFrame(render)
  }
  
  render(0)
  
  onBeforeUnmount(() => {
    window.removeEventListener('resize', handleResize)
    window.removeEventListener('mousemove', handleMouseMove)
    cancelAnimationFrame(animationFrameId)
  })
})
</script>

<template>
  <canvas ref="canvasRef" class="interactive-grid"></canvas>
</template>

<style scoped>
.interactive-grid {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
  z-index: 0;
}
</style>
