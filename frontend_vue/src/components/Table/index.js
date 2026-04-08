import T from 'ant-design-vue/es/table/Table'
import get from 'lodash.get'

export default {
  data () {
    return {
      needTotalList: [],

      selectedRows: [],
      selectedRowKeys: [],

      localLoading: false,
      localDataSource: [],
      localPagination: Object.assign({}, this.pagination),

      // Store filters and sorter objects from the table onchange event
      filters: {},
      sorter: {}
    }
  },
  props: Object.assign({}, T.props, {
    rowKey: {
      type: [String, Function],
      default: 'key'
    },
    data: {
      type: Function,
      required: true
    },
    pageNum: {
      type: Number,
      default: 1
    },
    pageSize: {
      type: Number,
      default: 10
    },
    showSizeChanger: {
      type: Boolean,
      default: true
    },
    size: {
      type: String,
      default: 'default'
    },
    /**
     * alert: {
     *   show: true,
     *   clear: Function
     * }
     */
    alert: {
      type: [Object, Boolean],
      default: null
    },
    rowSelection: {
      type: Object,
      default: null
    },
    /** @Deprecated */
    showAlertInfo: {
      type: Boolean,
      default: false
    },
    showPagination: {
      type: String | Boolean,
      default: 'auto'
    },
    /**
     * enable page URI mode
     *
     * e.g:
     * /users/1
     * /users/2
     * /users/3?queryParam=test
     * ...
     */
    pageURI: {
      type: Boolean,
      default: false
    }
  }),
  watch: {
    'localPagination.current' (val) {
      this.pageURI && this.$router.push({
        ...this.$route,
        name: this.$route.name,
        params: Object.assign({}, this.$route.params, {
          pageNo: val
        })
      })
      // change pagination, reset total data
      this.needTotalList = this.initTotalList(this.columns)
      this.selectedRowKeys = []
      this.selectedRows = []
    },
    pageNum (val) {
      Object.assign(this.localPagination, {
        current: val
      })
    },
    pageSize (val) {
      Object.assign(this.localPagination, {
        pageSize: val
      })
    },
    showSizeChanger (val) {
      Object.assign(this.localPagination, {
        showSizeChanger: val
      })
    }
  },
  created () {
    const { pageNo } = this.$route.params
    const localPageNum = this.pageURI && (pageNo && parseInt(pageNo)) || this.pageNum
    this.localPagination = ['auto', true].includes(this.showPagination) && Object.assign({}, this.localPagination, {
      current: localPageNum,
      pageSize: this.pageSize,
      showSizeChanger: this.showSizeChanger
    }) || false
    this.needTotalList = this.initTotalList(this.columns)
    this.loadData()
  },
  methods: {
    /**
     * Table reload method
     * If the argument is true, force refresh from the first page
     * @param Boolean bool
     */
    refresh (bool = false) {
      bool && (this.localPagination = Object.assign({}, {
        current: 1, pageSize: this.pageSize
      }))
      this.loadData()
    },
    /**
     * Data loading method
     * @param {Object} pagination pagination options
     * @param {Object} filters filters
     * @param {Object} sorter sorter
     */
    loadData (pagination, filters = this.filters, sorter = this.sorter) {
      this.filters = filters
      this.sorter = sorter

      this.localLoading = true
      const parameter = Object.assign({
        pageNo: (pagination && pagination.current) ||
          this.showPagination && this.localPagination.current || this.pageNum,
        pageSize: (pagination && pagination.pageSize) ||
          this.showPagination && this.localPagination.pageSize || this.pageSize
      },
      (sorter && sorter.field && {
        sortField: sorter.field
      }) || {},
      (sorter && sorter.order && {
        sortOrder: sorter.order
      }) || {}, {
        ...filters
      }
      )
      const result = this.data(parameter)
      // Adjust r.pageNo, r.totalCount, and r.data below to match your generic data API
      // eslint-disable-next-line
      if ((typeof result === 'object' || typeof result === 'function') && typeof result.then === 'function') {
        result.then(r => {
          this.localPagination = this.showPagination && Object.assign({}, this.localPagination, {
            current: r.pageNo, // current page number from the response
            total: r.totalCount, // total record count from the response
            showSizeChanger: this.showSizeChanger,
            pageSize: (pagination && pagination.pageSize) ||
              this.localPagination.pageSize
          }) || false
          // Automatically move to the previous page if deleting data leaves the current page empty
          if (r.data.length === 0 && this.showPagination && this.localPagination.current > 1) {
            this.localPagination.current--
            this.loadData()
            return
          }

          // This checks whether the API returned r.totalCount, pagination is enabled, pageNo and pageSize exist,
          // and totalCount is less than or equal to pageNo * pageSize.
          // When this condition is met, disable table pagination because the data no longer requires it.
          try {
            if ((['auto', true].includes(this.showPagination) && r.totalCount <= (r.pageNo * this.localPagination.pageSize))) {
              this.localPagination.hideOnSinglePage = true
            }
          } catch (e) {
            this.localPagination = false
          }
          this.localDataSource = r.data // array data from the response
        })
        .finally(() => {
          this.localLoading = false
        })
      }
    },
    initTotalList (columns) {
      const totalList = []
      columns && columns instanceof Array && columns.forEach(column => {
        if (column.needTotal) {
          totalList.push({
            ...column,
            total: 0
          })
        }
      })
      return totalList
    },
    /**
     * Used to update total statistics for selected rows
     * @param selectedRowKeys
     * @param selectedRows
     */
    updateSelect (selectedRowKeys, selectedRows) {
      this.selectedRows = selectedRows
      this.selectedRowKeys = selectedRowKeys
      const list = this.needTotalList
      this.needTotalList = list.map(item => {
        return {
          ...item,
          total: selectedRows.reduce((sum, val) => {
            const total = sum + parseInt(get(val, item.dataIndex))
            return isNaN(total) ? 0 : total
          }, 0)
        }
      })
    },
    /**
     * Clear selected table rows
     */
    clearSelected () {
      if (this.rowSelection) {
        this.rowSelection.onChange([], [])
        this.updateSelect([], [])
      }
    },
    /**
     * When clear is handled externally by the table consumer, also update the internal selection statistics
     * @param callback
     * @returns {*}
     */
    renderClear (callback) {
      if (this.selectedRowKeys.length <= 0) return null
      return (
        <a style="margin-left: 24px" onClick={() => {
          callback()
          this.clearSelected()
        }}>Clear</a>
      )
    },
    renderAlert () {
      // Render summary column data
      const needTotalItems = this.needTotalList.map((item) => {
        return (<span style="margin-right: 12px">
          {item.title} Total <a style="font-weight: 600">{!item.customRender ? item.total : item.customRender(item.total)}</a>
        </span>)
      })

      // Render the clear button
      const clearItem = (typeof this.alert.clear === 'boolean' && this.alert.clear) ? (
        this.renderClear(this.clearSelected)
      ) : (this.alert !== null && typeof this.alert.clear === 'function') ? (
        this.renderClear(this.alert.clear)
      ) : null

      // Render the alert component
      return (
        <a-alert showIcon={true} style="margin-bottom: 16px">
          <template slot="message">
            <span style="margin-right: 12px">Selected: <a style="font-weight: 600">{this.selectedRows.length}</a></span>
            {needTotalItems}
            {clearItem}
          </template>
        </a-alert>
      )
    }
  },

  render () {
    const props = {}
    const localKeys = Object.keys(this.$data)
    const showAlert = (typeof this.alert === 'object' && this.alert !== null && this.alert.show) && typeof this.rowSelection.selectedRowKeys !== 'undefined' || this.alert

    Object.keys(T.props).forEach(k => {
      const localKey = `local${k.substring(0, 1).toUpperCase()}${k.substring(1)}`
      if (localKeys.includes(localKey)) {
        props[k] = this[localKey]
        return props[k]
      }
      if (k === 'rowSelection') {
        if (showAlert && this.rowSelection) {
          // Rebind the rowSelection event when alert support is enabled
          props[k] = {
            ...this.rowSelection,
            selectedRows: this.selectedRows,
            selectedRowKeys: this.selectedRowKeys,
            onChange: (selectedRowKeys, selectedRows) => {
              this.updateSelect(selectedRowKeys, selectedRows)
              typeof this[k].onChange !== 'undefined' && this[k].onChange(selectedRowKeys, selectedRows)
            }
          }
          return props[k]
        } else if (!this.rowSelection) {
          // Clear the default selection if rowSelection is not enabled
          props[k] = null
          return props[k]
        }
      }
      this[k] && (props[k] = this[k])
      return props[k]
    })
    const table = (
      <a-table {...{ props, scopedSlots: { ...this.$scopedSlots } }} onChange={this.loadData} onExpand={ (expanded, record) => { this.$emit('expand', expanded, record) } }>
        { Object.keys(this.$slots).map(name => (<template slot={name}>{this.$slots[name]}</template>)) }
      </a-table>
    )

    return (
      <div class="table-wrapper">
        { showAlert ? this.renderAlert() : null }
        { table }
      </div>
    )
  }
}
