import { defineStore } from 'pinia'

export const useAppStore = defineStore('app', {
  state: () => ({
    darkMode: localStorage.getItem('dark-mode') === 'true',
  }),
  actions: {
    toggleDarkMode() {
      this.darkMode = !this.darkMode
      localStorage.setItem('dark-mode', this.darkMode)
      this._applyDarkMode()
    },
    initDarkMode() {
      this._applyDarkMode()
    },
    _applyDarkMode() {
      if (this.darkMode) {
        document.documentElement.classList.add('dark')
      } else {
        document.documentElement.classList.remove('dark')
      }
    },
  },
})
