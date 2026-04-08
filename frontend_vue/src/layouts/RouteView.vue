<script>
export default {
  name: 'RouteView',
  props: {
    keepAlive: {
      type: Boolean,
      default: true
    }
  },
  data () {
    return {}
  },
  render () {
    const { $route: { meta }, $store: { getters } } = this
    const inKeep = (
      <keep-alive>
        <router-view />
      </keep-alive>
    )
    const notKeep = (
      <router-view />
    )
    // This adds a multiTab check. When multiTab is enabled,
    // all components should be cached, otherwise switching pages may reset them to their initial state.
    // If that is not needed, change it to return meta.keepAlive ? inKeep : notKeep
    if (!getters.multiTab && !meta.keepAlive) {
      return notKeep
    }
    return this.keepAlive || getters.multiTab || meta.keepAlive ? inKeep : notKeep
  }
}
</script>
