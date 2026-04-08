import router, {
  resetRouter
} from './router'
import store from './store'
import storage from 'store'
import NProgress from 'nprogress' // progress bar
import '@/components/NProgress/nprogress.less' // progress bar custom style
import {
  setDocumentTitle,
  domTitle
} from '@/utils/domUtil'
import {
  ACCESS_TOKEN
} from '@/store/mutation-types'
import {
  i18nRender
} from '@/locales'

NProgress.configure({
  showSpinner: false
}) // NProgress Configuration

const allowList = ['login'] // no redirect allowList
const loginRoutePath = '/user/login'
const defaultRoutePath = '/ai-asset-analysis'

router.beforeEach((to, from, next) => {
  NProgress.start() // start progress bar
  to.meta && typeof to.meta.title !== 'undefined' && setDocumentTitle(`${i18nRender(to.meta.title)} - ${domTitle}`)

  // Check whether we have a token (local-only auth).
  // Handle tokens stored as either strings or objects
  let token = storage.get(ACCESS_TOKEN)
  if (token && typeof token !== 'string') {
    token = token.token || token.value || (typeof token === 'object' ? null : token)
  }
  token = typeof token === 'string' ? token : null

  if (token) {
    // Token present, allow access to all pages
    // If visiting the login page, redirect to the default page
    if (to.path === loginRoutePath) {
      next({ path: defaultRoutePath })
      NProgress.done()
    } else {
      // Check whether user info has been loaded
      if (store.getters.roles.length === 0) {
        store.dispatch('GetInfo')
          .then(res => {
            // User info loaded successfully
            // const roles = res && res.role
            // Generate routes
            store.dispatch('GenerateRoutes', { token }).then(() => {
              // Dynamically add accessible routes
              resetRouter() // Reset routes
              store.getters.addRouters.forEach(r => {
                router.addRoute(r)
              })
              // If a redirect query is present, automatically redirect there after login
              const redirect = decodeURIComponent(from.query.redirect || to.path)
              if (to.path === redirect) {
                // Hack to ensure addRoutes has completed. Use replace: true so navigation does not create a history entry
                next({ ...to, replace: true })
              } else {
                // Navigate to the target route
                next({ path: redirect })
              }
            })
          })
          .catch((err) => {
            // If token is invalid/expired, clear local auth and redirect to login.
            const status = err && err.response && err.response.status
            if (status === 401) {
              store.dispatch('Logout').finally(() => {
                next({ path: loginRoutePath, query: { redirect: to.fullPath } })
                NProgress.done()
              })
              return
            }

            // Do NOT hard-logout on transient failures (backend down, proxy issue, etc).
            // Instead, degrade gracefully with a default role and continue.
            store.commit('SET_ROLES', [{ id: 'default', permissionList: [] }])
            store.dispatch('GenerateRoutes', { token }).then(() => {
              resetRouter()
              store.getters.addRouters.forEach(r => router.addRoute(r))
              next({ ...to, replace: true })
            }).catch(() => {
              next()
            })
          })
      } else {
        // Check whether routes have been initialized
        const addRouters = store.getters.addRouters
        // Initialize routes first if they are not ready
        if (!addRouters || addRouters.length === 0) {
          store.dispatch('GenerateRoutes', { token }).then(() => {
            // Dynamically add accessible routes
            resetRouter() // Reset routes to avoid duplicates after logout or token expiration without a page refresh
            store.getters.addRouters.forEach(r => {
              router.addRoute(r)
            })
            // Re-enter the current route to avoid a blank first refresh
            next({ ...to, replace: true })
          }).catch(() => {
            next()
          })
        } else {
          next()
        }
      }
    }
  } else {
    // No token
    if (allowList.includes(to.name)) {
      // Allow direct access to public routes
      next()
    } else {
      // Redirect to the login page
      next({ path: loginRoutePath, query: { redirect: to.fullPath } })
      NProgress.done() // if current page is login will not trigger afterEach hook, so manually handle it
    }
  }
})

router.afterEach(() => {
  NProgress.done() // finish progress bar
})
