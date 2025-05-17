
// index.ts
// 获取应用实例
const app = getApp<IAppOption>()

interface IComponentData {
  motto: string
  searchValue: string
  filteredPositions: any[]
  filteredPositionsCount: number
  positions: any[]
  loading: boolean
}

Component({
  data: {
    motto: '智能面试助手',
    searchValue: '',
    filteredPositions: [],
    filteredPositionsCount: 0,
    positions: [],
    loading: false,
  } as IComponentData,

  methods: {
    // 事件处理函数
    bindViewTap() {
      wx.navigateTo({
        url: '../logs/logs',
      })
    },
    
    // 跳转到个人中心
    navigateToProfile() {
      wx.switchTab({
        url: '/pages/user/profile/profile'
      })
    },
    
    // 开始面试
    startInterview() {
      // 直接跳转到岗位选择页面
      wx.navigateTo({
        url: '/pages/interview/position/position'
      });
    },

    // 清除搜索
    clearSearch() {
      this.setData({
        searchValue: '',
        filteredPositions: [...this.data.positions],
        filteredPositionsCount: this.data.positions.length
      });
    },

    // 加载岗位数据
    loadPositions() {
      // 这里应该是从API获取数据的逻辑
      // 示例数据
      const positions = [
        // 你的岗位数据
      ];
      
      this.setData({
        positions,
        filteredPositions: [...positions], // 初始化过滤后的列表
        loading: false,
        filteredPositionsCount: positions.length
      });
    },
  },
})