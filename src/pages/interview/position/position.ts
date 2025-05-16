// pages/interview/position/position.ts

// 岗位类型定义
interface Position {
  id: string;
  name: string;
  icon: string;
  description: string;
  tags: string[];
  questionCount: number;
  duration: number; // 面试时长（分钟）
}

Page({
  data: {
    positions: [] as Position[],
    filteredPositions: [] as Position[],
    loading: true,
    selectedId: '',
    searchValue: '',
    filteredPositionsCount: 0
  },

  onLoad() {
    // 加载岗位数据
    this.loadPositions();
  },

  // 加载岗位数据
  loadPositions() {
    // 模拟从服务器获取数据
    // 实际项目中应该从API获取
    setTimeout(() => {
      const positions: Position[] = [
        {
          id: 'ai_engineer',
          name: 'AI算法工程师',
          icon: '/assets/images/position_ai.png',
          description: '负责AI算法研发，包括机器学习模型设计、训练和优化',
          tags: ['机器学习', 'Python', '深度学习', '算法优化'],
          questionCount: 15,
          duration: 30
        },
        {
          id: 'data_analyst',
          name: '大数据分析师',
          icon: '/assets/images/position_data.png',
          description: '负责大数据处理、分析和可视化，提供数据洞察和决策支持',
          tags: ['数据分析', 'SQL', 'Hadoop', '数据可视化'],
          questionCount: 12,
          duration: 25
        },
        {
          id: 'frontend',
          name: '前端开发工程师',
          icon: '/assets/images/position_frontend.png',
          description: '负责Web前端开发，实现用户界面和交互功能',
          tags: ['JavaScript', 'React', 'Vue', 'CSS'],
          questionCount: 18,
          duration: 35
        },
        {
          id: 'backend',
          name: '后端开发工程师',
          icon: '/assets/images/position_backend.png',
          description: '负责服务器端开发，实现业务逻辑和数据处理',
          tags: ['Java', 'Spring', '微服务', '数据库'],
          questionCount: 16,
          duration: 30
        },
        {
          id: 'product',
          name: '产品经理',
          icon: '/assets/images/position_product.png',
          description: '负责产品规划、需求分析和产品设计，推动产品落地',
          tags: ['产品设计', '用户研究', '需求分析', '项目管理'],
          questionCount: 14,
          duration: 40
        }
      ];

      this.setData({
        positions,
        loading: false,
        filteredPositionsCount: positions.length
      });
    }, 1000); // 模拟网络延迟
  },

  // 选择岗位
  selectPosition(e: WechatMiniprogram.TouchEvent) {
    const id = e.currentTarget.dataset.id;
    this.setData({
      selectedId: id
    });
  },

  // 开始面试
  startInterview() {
    if (!this.data.selectedId) {
      wx.showToast({
        title: '请先选择岗位',
        icon: 'none'
      });
      return;
    }

    // 获取选中的岗位信息
    const position = this.data.positions.find(p => p.id === this.data.selectedId);
    
    // 将岗位信息存储到本地，以便在面试页面使用
    wx.setStorageSync('selectedPosition', position);
    
    // 跳转到面试问题页面
    wx.navigateTo({
      url: '/pages/interview/question/question'
    });
  },

  // 搜索岗位
  onSearch(e: WechatMiniprogram.Input) {
    const searchValue = e.detail.value.trim().toLowerCase();
    
    // 过滤符合搜索条件的岗位
    let filteredPositions = [];
    if (searchValue) {
      filteredPositions = this.data.positions.filter(p => 
        p.name.toLowerCase().includes(searchValue) || 
        p.description.toLowerCase().includes(searchValue) ||
        p.tags.some(tag => tag.toLowerCase().includes(searchValue))
      );
    } else {
      // 如果没有搜索词，显示全部岗位
      filteredPositions = [...this.data.positions];
    }
    
    this.setData({ 
      searchValue,
      filteredPositions,
      filteredPositionsCount: filteredPositions.length
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

  // 返回首页
  goBack() {
    wx.navigateBack();
  }
})