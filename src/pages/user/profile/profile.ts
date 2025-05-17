// pages/user/profile/profile.ts
Page({
  data: {
    userInfo: {
      avatarUrl: '',
      nickName: ''
    },
    hasUserInfo: false,
    resumeUrl: '',
    userName: ''
  },

  onLoad() {
    // 尝试从本地存储获取用户信息
    const userInfo = wx.getStorageSync('userInfo')
    const resumeUrl = wx.getStorageSync('resumeUrl')
    const userName = wx.getStorageSync('userName')
    
    if (userInfo) {
      this.setData({
        userInfo,
        hasUserInfo: true,
        resumeUrl,
        userName
      })
    }
  },

  // 获取用户授权信息
  getUserProfile() {
    wx.getUserProfile({
      desc: '需要您的授权才能获取头像和昵称',
      success: (res) => {
        this.setData({
          userInfo: {
            avatarUrl: res.userInfo.avatarUrl,
            nickName: res.userInfo.nickName
          },
          hasUserInfo: true
        })
        wx.setStorageSync('userInfo', this.data.userInfo)
      },
      fail: (err) => {
        wx.showToast({
          title: '授权失败',
          icon: 'none'
        })
      }
    })
  },

  // 头像选择回调
  onChooseAvatar(e) {
    this.setData({
      'userInfo.avatarUrl': e.detail.avatarUrl
    })
    wx.setStorageSync('userInfo', this.data.userInfo)
  },

  // 昵称输入回调
  onNickNameInput(e) {
    this.setData({
      'userInfo.nickName': e.detail.value
    })
    wx.setStorageSync('userInfo', this.data.userInfo)
  },

  // 登录获取code
  login() {
    wx.login({
      success: res => {
        if (res.code) {
          console.log('登录成功，code:', res.code)
          // TODO: 发送code到后端换取openId等信息
          
          wx.showToast({
            title: '登录成功',
            icon: 'success'
          })
        }
      }
    })
  },

  // 上传简历
  uploadResume() {
    wx.chooseMessageFile({
      count: 1,
      type: 'file',
      extension: ['pdf', 'doc', 'docx'],
      success: (res) => {
        const tempFilePath = res.tempFiles[0].path
        wx.setStorageSync('resumeUrl', tempFilePath)
        
        this.setData({
          resumeUrl: tempFilePath
        })
        
        wx.showToast({
          title: '简历上传成功',
          icon: 'success'
        })
      }
    })
  },

  // 查看简历
  viewResume() {
    if (this.data.resumeUrl) {
      wx.openDocument({
        filePath: this.data.resumeUrl,
        showMenu: true
      })
    }
  },

  // 跳转到面试历史记录页面
  navigateToHistory() {
    wx.showToast({
      title: '功能开发中',
      icon: 'none'
    })
  }
})