// 用户信息接口定义
export interface UserInfo {
  avatarUrl: string;
  nickName: string;
  gender: number;
  country: string;
  province: string;
  city: string;
  language: string;
}

// 用户简历信息接口定义
export interface ResumeInfo {
  url: string;
  name: string;
  uploadTime: string;
}

// 用户完整信息接口定义
export interface UserProfile extends UserInfo {
  userName?: string;
  resume?: ResumeInfo;
  lastLoginTime?: string;
  createTime?: string;
  updateTime?: string;
}