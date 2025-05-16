// pages/user/profile/profile.ts
import { UserInfo } from '../../../types/user'

// 获取应用实例
const app = getApp<IAppOption>()

Page({
  data: {
    userInfo: {} as UserInfo,
    hasUserInfo: false,
    canIUseGetUserProfile: false,
    resumeUrl: '',
    userName: '',
    isEditing: false
  },

  onLoad() {
    // 检查是否支持getUserProfile API
    if (wx.getUserProfile) {
      this.setData({
        canIUseGetUserProfile: true
      })
    }

    // 尝试从本地存储获取用户信息
    const userInfo = wx.getStorageSync('userInfo')
    const resumeUrl = wx.getStorageSync('resumeUrl')
    const userName = wx.getStorageSync('userName')
    
    if (userInfo) {
      this.setData({
        userInfo,
        hasUserInfo: true,
        resumeUrl,
        userName: userName || userInfo.nickName
      })
    }
  },

  // 获取用户信息
  getUserProfile() {
    wx.getUserProfile({
      desc: '用于完善个人资料',
      success: (res) => {
        const userInfo = res.userInfo
        
        // 保存到本地存储
        wx.setStorageSync('userInfo', userInfo)
        
        this.setData({
          userInfo,
          hasUserInfo: true,
          userName: this.data.userName || userInfo.nickName
        })
        
        // 调用登录接口，获取登录凭证
        this.login()
      },
      fail: () => {
        wx.showToast({
          title: '授权失败',
          icon: 'error'
        })
      }
    })
  },

  // 登录获取code
  login() {
    wx.login({
      success: res => {
        if (res.code) {
          console.log('登录成功，code:', res.code)
          // TODO: 发送code到后端换取openId等信息
          // 这里可以调用后端API，但目前我们只在本地存储用户信息
          
          wx.showToast({
            title: '登录成功',
            icon: 'success'
          })
        } else {
          console.log('登录失败', res)
          wx.showToast({
            title: '登录失败',
            icon: 'error'
          })
        }
      }
    })
  },

  // 切换编辑模式
  toggleEdit() {
    this.setData({
      isEditing: !this.data.isEditing
    })
  },

  // 保存用户名
  saveUserName(e: WechatMiniprogram.Input) {
    const userName = e.detail.value.trim()
    if (userName) {
      wx.setStorageSync('userName', userName)
      this.setData({
        userName,
        isEditing: false
      })
      wx.showToast({
        title: '保存成功',
        icon: 'success'
      })
    } else {
      wx.showToast({
        title: '姓名不能为空',
        icon: 'error'
      })
    }
  },

  // 上传简历
  uploadResume() {
    wx.chooseMessageFile({
      count: 1,
      type: 'file',
      extension: ['pdf', 'doc', 'docx'],
      success: (res) => {
        const tempFilePath = res.tempFiles[0].path
        const fileName = res.tempFiles[0].name
        
        // 在实际应用中，这里应该上传文件到服务器
        // 目前我们只在本地存储文件路径
        wx.setStorageSync('resumeUrl', tempFilePath)
        wx.setStorageSync('resumeName', fileName)
        
        this.setData({
          resumeUrl: tempFilePath
        })
        
        wx.showToast({
          title: '简历上传成功',
          icon: 'success'
        })
      },
      fail: () => {
        wx.showToast({
          title: '简历上传失败',
          icon: 'error'
        })
      }
    })
  },

  // 查看简历
  viewResume() {
    if (this.data.resumeUrl) {
      wx.openDocument({
        filePath: this.data.resumeUrl,
        showMenu: true,
        success: () => {
          console.log('打开文档成功')
        },
        fail: (err) => {
          console.error('打开文档失败', err)
          wx.showToast({
            title: '打开文档失败',
            icon: 'error'
          })
        }
      })
    }
  },

  // 跳转到面试历史记录页面
  navigateToHistory() {
    wx.showToast({
      title: '功能开发中',
      icon: 'none'
    })
    // 后续实现时取消注释下面的代码
    // wx.navigateTo({
    //   url: '../history/history'
    // })
  }
})