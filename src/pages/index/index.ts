
// index.ts
import { IAppOption } from '../../app'

// 获取应用实例并验证
const app = getApp<IAppOption>()
if (!app.requireLogin) {
  console.error('App实例缺少requireLogin方法')
  // 开发环境直接抛出错误以便及时发现
  // if (process.env.NODE_ENV === 'development') {
  //   throw new Error('App实例缺少requireLogin方法')
  // }
}

// 定义岗位接口
interface Position {
  id: string;
  title: string;
  company?: string;
  description?: string;
  requirements?: string[];
  location?: string;
  salary?: string;
  // 根据实际需求添加更多字段
}

interface IComponentData {
  motto: string;
  searchValue: string;
  filteredPositions: Position[];
  filteredPositionsCount: number;
  positions: Position[];
  loading: boolean;
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
      const app = getApp<IAppOption>();
      app.requireLogin({
        success: () => {
          wx.navigateTo({
            url: '/pages/interview/position/position'
          });
        },
        fail: () => {
          // 登录失败的提示已经在 requireLogin 中处理
          // 这里可以添加额外的失败处理逻辑
          console.log('用户取消登录或登录失败');
        }
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
      const positions: Position[] = [
        {
          id: '1',
          title: '前端开发工程师',
          company: '示例科技有限公司',
          description: '负责公司前端项目开发',
          requirements: ['熟悉React', '3年以上经验'],
          location: '深圳',
          salary: '15k-25k'
        }
        // 更多岗位数据...
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