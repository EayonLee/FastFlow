import { createRouter, createWebHistory } from 'vue-router'
import LandingPage from '../views/LandingPage.vue'
import WorkflowListView from '../views/WorkflowListView.vue'
import WorkflowEditor from '../views/WorkflowEditor.vue'
import LoginPage from '../views/auth/LoginPage.vue'
import RegisterPage from '../views/auth/RegisterPage.vue'
import { useUserStore } from '@/stores/userStore'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'landing',
      component: LandingPage
    },
    {
      path: '/login',
      name: 'login',
      component: LoginPage
    },
    {
      path: '/register',
      name: 'register',
      component: RegisterPage
    },
    {
      path: '/workflows',
      name: 'workflow-list',
      component: WorkflowListView
    },
    {
      path: '/workflow/:id',
      name: 'editor',
      component: WorkflowEditor
    }
  ]
})

router.beforeEach((to, _from, next) => {
  const userStore = useUserStore()
  const publicPages = ['/', '/login', '/register']
  const authRequired = !publicPages.includes(to.path)
  
  // Also check if route is landing page which is public
  if (authRequired && !userStore.isLoggedIn.value) {
    return next('/login')
  }

  if (userStore.isLoggedIn.value && (to.path === '/login')) {
    return next('/')
  }

  next()
})

export default router
