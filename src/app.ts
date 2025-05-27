import { UserInfo } from './types/user';

export interface IAppOption {
  globalData: {
    userInfo?: UserInfo;
    hasUserInfo: boolean;
    token?: string;
    tokenExpire?: number;
    refreshToken?: string;
  };
  
  // JWT Token 管理
  setToken(token: string, expiresIn: number): void;
  getToken(): string | null;
  clearToken(): void;
  refreshToken(): Promise<void>;
  isTokenValid(): boolean;
  
  // 登录相关方法
  login(options?: {
    success?: (userInfo: UserInfo) => void;
    fail?: (err: any) => void;
  }): void;
  
  requireLogin(options: {
    url: string;
    success?: () => void;
    fail?: () => void;
  }): void;
}

App<IAppOption>({
  globalData: {
    userInfo: undefined,
    hasUserInfo: false,
    token: undefined,
    tokenExpire: undefined,
    refreshToken: undefined
  },

  // ========== JWT Token 管理 ==========
  setToken(token: string, expiresIn: number) {
    const expireTime = Date.now() + expiresIn * 1000;
    this.globalData.token = token;
    this.globalData.tokenExpire = expireTime;
    wx.setStorageSync('jwtToken', token);
    wx.setStorageSync('tokenExpire', expireTime);
  },

  getToken(): string | null {
    // 内存中存在且未过期则直接返回
    if (this.globalData.token && this.isTokenValid()) {
      return this.globalData.token;
    }
    
    // 从存储中读取
    const token = wx.getStorageSync('jwtToken');
    const expireTime = wx.getStorageSync('tokenExpire');
    
    if (token && expireTime > Date.now()) {
      this.globalData.token = token;
      this.globalData.tokenExpire = expireTime;
      return token;
    }
    
    return null;
  },

  clearToken() {
    this.globalData.token = undefined;
    this.globalData.tokenExpire = undefined;
    wx.removeStorageSync('jwtToken');
    wx.removeStorageSync('tokenExpire');
  },

  async refreshToken() {
    try {
      // 这里应该是调用后端刷新token的接口
      const response = await new Promise<any>((resolve) => {
        wx.request({
          url: 'https://your-api-domain.com/auth/refresh',
          method: 'POST',
          success: resolve,
          fail: (err) => {
            throw new Error(`刷新Token失败: ${err.errMsg}`);
          }
        });
      });
      
      if (response.data.code === 0) {
        this.setToken(response.data.token, response.data.expires_in);
        return;
      }
      throw new Error(response.data.message || '刷新Token失败');
    } catch (err) {
      console.error(err);
      this.clearToken();
      throw err;
    }
  },

  isTokenValid(): boolean {
    const token = this.globalData.token || wx.getStorageSync('jwtToken');
    const expireTime = this.globalData.tokenExpire || wx.getStorageSync('tokenExpire');
    
    if (!token || !expireTime) return false;
    
    // 提前5分钟判断为即将过期
    return expireTime > Date.now() + 300000;
  },

  // ========== 登录相关方法 ==========
  login(options?: {
    success?: (userInfo: UserInfo) => void;
    fail?: (err: any) => void;
  }) {
    // 显示加载提示
    wx.showLoading({ title: '登录中...' });

    wx.login({
      success: (res) => {
        if (res.code) {
          // 调用后端接口获取token
          wx.request({
            url: 'https://your-api-domain.com/auth/login',
            method: 'POST',
            data: {
              code: res.code
            },
            success: (response: any) => {
              if (response.data.code === 0 && response.data.data) {
                const { token, expires_in, userInfo } = response.data.data;
                
                // 设置全局token
                this.setToken(token, expires_in);
                
                // 设置用户信息
                this.globalData.userInfo = userInfo;
                this.globalData.hasUserInfo = true;
                
                // 保存用户信息到本地
                wx.setStorageSync('userInfo', userInfo);
                
                wx.hideLoading();
                options?.success?.(userInfo);
              } else {
                wx.hideLoading();
                wx.showToast({
                  title: response.data.message || '登录失败',
                  icon: 'none'
                });
                options?.fail?.(new Error(response.data.message));
              }
            },
            fail: (err) => {
              wx.hideLoading();
              wx.showToast({
                title: '网络请求失败',
                icon: 'none'
              });
              options?.fail?.(err);
            }
          });
        } else {
          wx.hideLoading();
          wx.showToast({
            title: '微信登录失败',
            icon: 'none'
          });
          options?.fail?.(new Error('微信登录失败'));
        }
      },
      fail: (err) => {
        wx.hideLoading();
        wx.showToast({
          title: '登录失败',
          icon: 'none'
        });
        options?.fail?.(err);
      }
    });
  },

  requireLogin(options: {
    url: string;
    success?: () => void;
    fail?: () => void;
  }) {
    if (this.isTokenValid()) {
      options.success?.();
      return;
    }

    // 未登录则直接调用微信登录接口
    wx.showModal({
      title: '需要登录',
      content: '请先登录以继续操作',
      confirmText: '登录',
      cancelText: '取消',
      success: (res) => {
        if (res.confirm) {
          wx.login({
            success: (loginRes) => {
              if (loginRes.code) {
                // 这里应该调用后端接口交换token
                // 模拟登录成功
                this.globalData.token = 'generated_token';
                options.success?.();
              } else {
                console.error('微信登录失败:', loginRes.errMsg);
                options.fail?.();
              }
            },
            fail: (err) => {
              console.error('调用登录接口失败:', err);
              options.fail?.();
            }
          });
        } else {
          options.fail?.();
        }
      },
      fail: (err) => {
        console.error('显示登录提示失败:', err);
        options.fail?.();
      }
    });
  }
});