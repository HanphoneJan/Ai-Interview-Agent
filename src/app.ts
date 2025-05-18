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
    // 实现登录逻辑
  },

  requireLogin(options: {
    url: string;
    success?: () => void;
    fail?: () => void;
  }) {
    // 实现需要登录的逻辑
  }
});