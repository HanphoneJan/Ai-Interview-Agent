// app.ts
import { UserInfo } from './types/user'

// 扩展IAppOption接口，添加全局用户状态
interface IAppOption {
  globalData: {
    userInfo?: UserInfo;
    hasUserInfo: boolean;
  }
  // 用户信息相关方法
  getUserInfo(): UserInfo | null;
  setUserInfo(userInfo: UserInfo): void;
  clearUserInfo(): void;
}

App<IAppOption>({
  globalData: {
    hasUserInfo: false
  },
  
  onLaunch() {
    // 展示本地存储能力
    const logs = wx.getStorageSync('logs') || []
    logs.unshift(Date.now())
    wx.setStorageSync('logs', logs)

    // 尝试从本地存储获取用户信息
    const userInfo = wx.getStorageSync('userInfo')
    if (userInfo) {
      this.globalData.userInfo = userInfo
      this.globalData.hasUserInfo = true
    }

    // 登录
    wx.login({
      success: res => {
        console.log(res.code)
        // 发送 res.code 到后台换取 openId, sessionKey, unionId
        // 实际项目中，这里应该调用后端API进行登录验证
      },
    })
  },
  
  // 获取用户信息
  getUserInfo() {
    return this.globalData.userInfo || null
  },
  
  // 设置用户信息
  setUserInfo(userInfo: UserInfo) {
    this.globalData.userInfo = userInfo
    this.globalData.hasUserInfo = true
    // 保存到本地存储
    wx.setStorageSync('userInfo', userInfo)
  },
  
  // 清除用户信息
  clearUserInfo() {
    this.globalData.userInfo = undefined
    this.globalData.hasUserInfo = false
    // 从本地存储中移除
    wx.removeStorageSync('userInfo')
  }
})