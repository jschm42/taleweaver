import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import '@fontsource/caveat/600.css'
import './assets/main.css'
import './assets/portal-theme.css'
import './skins/index.css'
import { installBackendWatch } from './services/backendStatus'

// Before mounting, so even the first API calls are observed.
installBackendWatch()

createApp(App).use(router).mount('#app')

