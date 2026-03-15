import { DefaultApolloClient } from '@vue/apollo-composable'
import { createApp, h, provide } from 'vue'
import { createPinia } from 'pinia'

import './styles.css'
import './theme.scss'

import App from './App.vue'
import { apolloClient } from './graphql/client/apollo'
import router from './router'

const app = createApp({
  setup() {
    provide(DefaultApolloClient, apolloClient)
  },
  render: () => h(App),
})

app.use(createPinia())
app.use(router)

app.mount('#app')
