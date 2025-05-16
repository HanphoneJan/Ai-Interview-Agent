// index.ts
// 获取应用实例
const app = getApp<IAppOption>()
const defaultAvatarUrl = 'https://mmbiz.qpic.cn/mmbiz/icTdbqWNOwNRna42FI242Lcia07jQodd2FJGIYQfG0LAJGFxM4FbnQP6yfMxBgJ0F3YRqJCJ1aPAK2dQagdusBZg/0'

Component({
  data: {
    motto: '智能面试助手',
    userInfo: {
      avatarUrl: defaultAvatarUrl,
      nickName: '',
    },
    hasUserInfo: false,
    canIUseGetUserProfile: wx.canIUse('getUserProfile'),
    canIUseNicknameComp: wx.canIUse('input.type.nickname'),
    searchValue: '',
    filteredPositions: [],
    filteredPositionsCount: 0,
  },
  methods: {
    // 事件处理函数
    bindViewTap() {
      wx.navigateTo({
        url: '../logs/logs',
      })
    },
    onChooseAvatar(e: any) {
      const { avatarUrl } = e.detail
      const { nickName } = this.data.userInfo
      this.setData({
        "userInfo.avatarUrl": avatarUrl,
        hasUserInfo: nickName && avatarUrl && avatarUrl !== defaultAvatarUrl,
      })
    },
    onInputChange(e: any) {
      const nickName = e.detail.value
      const { avatarUrl } = this.data.userInfo
      this.setData({
        "userInfo.nickName": nickName,
        hasUserInfo: nickName && avatarUrl && avatarUrl !== defaultAvatarUrl,
      })
    },
    getUserProfile() {
      // 推荐使用wx.getUserProfile获取用户信息，开发者每次通过该接口获取用户个人信息均需用户确认，开发者妥善保管用户快速填写的头像昵称，避免重复弹窗
      wx.getUserProfile({
        desc: '用于完善个人资料', // 声明获取用户个人信息后的用途，后续会展示在弹窗中，请谨慎填写
        success: (res) => {
          console.log(res)
          this.setData({
            userInfo: res.userInfo,
            hasUserInfo: true
          })
          
          // 登录获取code
          wx.login({
            success: loginRes => {
              if (loginRes.code) {
                console.log('登录成功，code:', loginRes.code)
                // TODO: 发送code到后端换取openId等信息
              }
            }
          })
        }
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
      // 检查是否已登录
      if (!this.data.hasUserInfo) {
        wx.showToast({
          title: '请先登录',
          icon: 'none'
        });
        return;
      }
      
      // 检查是否填写了用户名
      if (!this.data.userInfo.nickName) {
        wx.showToast({
          title: '请填写昵称',
          icon: 'none'
        });
        return;
      }
      
      // 跳转到岗位选择页面
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
      // ...其他代码不变...
      this.setData({
        positions,
        filteredPositions: [...positions], // 初始化过滤后的列表
        loading: false,
        filteredPositionsCount: positions.length
      });
      // ...其他代码不变...
    },
  },
})