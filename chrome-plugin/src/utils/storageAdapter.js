export class StorageAdapter {
  constructor(area = 'local') {
    this.area = area
  }
 
  get isChromeStorageAvailable() {
    return typeof chrome !== 'undefined' && !!chrome.storage && !!chrome.storage[this.area]
  }
 
  async get(key) {
    if (this.isChromeStorageAvailable) {
      return await new Promise((resolve) => {
        chrome.storage[this.area].get([key], (result) => {
          resolve(result ? result[key] : undefined)
        })
      })
    }
    return this.getFromLocalStorage(key)
  }
 
  async set(key, value) {
    if (this.isChromeStorageAvailable) {
      await new Promise((resolve) => {
        chrome.storage[this.area].set({ [key]: value }, () => resolve())
      })
      return
    }
    localStorage.setItem(key, JSON.stringify(value))
  }
 
  async remove(key) {
    if (this.isChromeStorageAvailable) {
      await new Promise((resolve) => {
        chrome.storage[this.area].remove([key], () => resolve())
      })
      return
    }
    localStorage.removeItem(key)
  }
 
  onChanged(callback) {
    if (this.isChromeStorageAvailable && chrome.storage.onChanged) {
      const handler = (changes, areaName) => {
        if (areaName !== this.area) return
        callback(changes)
      }
      chrome.storage.onChanged.addListener(handler)
      return () => chrome.storage.onChanged.removeListener(handler)
    }
 
    const handler = (e) => {
      if (!e.key) return
      callback({
        [e.key]: {
          newValue: e.newValue,
          oldValue: e.oldValue
        }
      })
    }
    window.addEventListener('storage', handler)
    return () => window.removeEventListener('storage', handler)
  }

  getFromLocalStorage(key) {
    const raw = localStorage.getItem(key)
    try {
      return raw == null ? undefined : JSON.parse(raw)
    } catch {
      return raw == null ? undefined : raw
    }
  }
}
