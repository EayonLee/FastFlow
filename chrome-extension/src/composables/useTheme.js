import { ref, onMounted, onBeforeUnmount } from 'vue'
import { themeManager } from '@/utils/themeManager.js'

const theme = ref('dark')

export function useTheme() {
  let unsubscribe = null

  const setTheme = (val) => themeManager.setTheme(val)

  onMounted(async () => {
    await themeManager.ready
    themeManager.register(document.documentElement)
    theme.value = themeManager.getTheme()
    unsubscribe = themeManager.subscribe((val) => {
      theme.value = val
    })
  })

  onBeforeUnmount(() => {
    if (unsubscribe) unsubscribe()
  })

  return {
    theme,
    setTheme,
    options: [
      { label: '深色', value: 'dark' },
      { label: '浅色', value: 'light' },
      { label: '跟随系统', value: 'system' }
    ]
  }
}
