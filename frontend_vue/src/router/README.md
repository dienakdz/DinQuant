Router and Menu Notes
====


Format and Overview
----

```ecmascript 6
const routerObject = {
  redirect: noredirect,
  name: 'router-name',
  hidden: true,
  meta: {
    title: 'title',
    icon: 'a-icon',
    target: '_blank|_self|_top|_parent',
    keepAlive: true,
    hiddenHeaderContent: true,
  }
}
```



`{ Route }` object

| Field | Description | Type | Default |
| ----- | ----------- | ---- | ------- |
| hidden | Controls whether the route is shown in the sidebar | boolean | false |
| redirect | Redirect target used when the route is accessed | string | - |
| name | Route name. Must be unique and is required | string | - |
| meta | Route metadata (extended route information) | object | {} |
| hideChildrenInMenu | Forces the menu to render as an item instead of a submenu, typically used with `meta.hidden` | boolean | - |


`{ Meta }` route metadata object

| Field | Description | Type | Default |
| ----- | ----------- | ---- | ------- |
| title | Route title used for breadcrumbs and page titles. Recommended | string | - |
| icon | Icon shown in the menu | [string,svg] | - |
| keepAlive | Whether the route should be cached | boolean | false |
| target | Link target for menu navigation, similar to the HTML `a` tag | string | - |
| hidden | Used together with `hideChildrenInMenu` to keep the correct parent menu item selected when the current menu node is hidden | boolean | false |
| hiddenHeaderContent | Hides the breadcrumb and page header content in the [PageHeader](https://github.com/vueComponent/ant-design-vue-pro/blob/master/src/components/PageHeader/PageHeader.vue#L6) component | boolean | false |
| permission | Permission keys checked by the app permission guard. Routes without a matching permission are blocked | array | [] |

> For a custom route `Icon`, import the corresponding custom `svg` file and pass it through the route `meta.icon` field.

Example Route Configuration
----

```ecmascript 6
const asyncRouterMap = [
  {
    path: '/',
    name: 'index',
    component: BasicLayout,
    meta: { title: 'Home' },
    redirect: '/ai-analysis',
    children: [
      {
        path: '/dashboard',
        component: RouteView,
        name: 'dashboard',
        redirect: '/dashboard/workplace',
        meta: { title: 'Dashboard', icon: 'dashboard', permission: ['dashboard'] },
        children: [
          {
            path: '/ai-analysis',
            name: 'Analysis',
            component: () => import('@/views/dashboard/Analysis'),
            meta: { title: 'Analysis', permission: ['dashboard'] }
          },
          {
            path: '/dashboard/monitor',
            name: 'Monitor',
            hidden: true,
            component: () => import('@/views/dashboard/Monitor'),
            meta: { title: 'Monitor', permission: ['dashboard'] }
          },
          {
            path: '/dashboard/workplace',
            name: 'Workplace',
            component: () => import('@/views/dashboard/Workplace'),
            meta: { title: 'Workplace', permission: ['dashboard'] }
          }
        ]
      },

      // Result pages
      {
        path: '/result',
        name: 'result',
        component: PageView,
        redirect: '/result/success',
        meta: { title: 'Result', icon: 'check-circle-o', permission: [ 'result' ] },
        children: [
          {
            path: '/result/success',
            name: 'ResultSuccess',
            component: () => import(/* webpackChunkName: "result" */ '@/views/result/Success'),
            // This page hides breadcrumbs and the page title bar.
            meta: { title: 'Success', hiddenHeaderContent: true, permission: [ 'result' ] }
          },
          {
            path: '/result/fail',
            name: 'ResultFail',
            component: () => import(/* webpackChunkName: "result" */ '@/views/result/Error'),
            // This page hides breadcrumbs and the page title bar.
            meta: { title: 'Failure', hiddenHeaderContent: true, permission: [ 'result' ] }
          }
        ]
      },
      ...
    ]
  },
]
```

> 1. `component: () => import('..')` uses lazy-loaded route components. See the [Vue Router docs](https://router.vuejs.org/guide/advanced/lazy-loading.html) for details.
> 2. New top-level application routes should usually be added under the `'/'` route `children`.
> 3. A parent route for nested children must expose `router-view`, otherwise child routes cannot render.
> 4. The `permission` system can be customized in the corresponding permission module, for example [src/store/modules/permission.js#L10](https://github.com/vueComponent/ant-design-vue-pro/blob/master/src/store/modules/permission.js#L10).


Permission Route Structure

![Permission Structure](https://static-2.loacg.com/open/static/github/permissions.png)


If you prefer backend-driven dynamic route generation, refer to the official documentation:
https://pro.antdv.com/docs/authority-management
