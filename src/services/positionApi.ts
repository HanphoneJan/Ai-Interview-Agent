/**
 * 岗位相关API服务
 */

const BASE_URL = 'https://api.yourdomain.com/v1';

/**
 * 获取岗位列表
 * @param params 查询参数
 * @returns Promise<Position[]>
 */
export const getPositions = async (params: {
  page?: number;
  size?: number;
  keyword?: string;
} = {}): Promise<Position[]> => {
  try {
    const response = await new Promise<WechatMiniprogram.RequestSuccessCallbackResult>((resolve, reject) => {
      const requestTask = wx.request({
        url: `${BASE_URL}/positions`,
        method: 'GET',
        data: {
          page: params.page || 1,
          size: params.size || 10,
          keyword: params.keyword || ''
        },
        success: resolve,
        fail: reject
      });
    });
    
    if (response.statusCode === 200) {
      return (response.data as any).data as Position[];
    }
    throw new Error((response.data as any).message || '获取岗位列表失败');
  } catch (error) {
    console.error('获取岗位列表失败:', error);
    throw error;
  }
};

/**
 * 获取岗位详情
 * @param positionId 岗位ID
 * @returns Promise<Position>
 */
export const getPositionDetail = async (positionId: string): Promise<Position> => {
  try {
    const response = await new Promise<WechatMiniprogram.RequestSuccessCallbackResult>((resolve, reject) => {
      const requestTask = wx.request({
        url: `${BASE_URL}/positions/${positionId}`,
        method: 'GET',
        success: resolve,
        fail: reject
      });
    });
    
    if (response.statusCode === 200) {
      return (response.data as any).data as Position;
    }
    throw new Error((response.data as any).message || '获取岗位详情失败');
  } catch (error) {
    console.error('获取岗位详情失败:', error);
    throw error;
  }
};

/**
 * 搜索岗位
 * @param keyword 搜索关键词
 * @returns Promise<Position[]>
 */
export const searchPositions = async (keyword: string): Promise<Position[]> => {
  try {
    const response = await new Promise<WechatMiniprogram.RequestSuccessCallbackResult>((resolve, reject) => {
      const requestTask = wx.request({
        url: `${BASE_URL}/positions/search`,
        method: 'GET',
        data: { keyword },
        success: resolve,
        fail: reject
      });
    });
    
    if (response.statusCode === 200) {
      return (response.data as any).data as Position[];
    }
    throw new Error((response.data as any).message || '搜索岗位失败');
  } catch (error) {
    console.error('搜索岗位失败:', error);
    throw error;
  }
};

// 岗位类型定义
interface Position {
  id: string;
  name: string;
  icon: string;
  description: string;
  tags: string[];
  questionCount: number;
  duration: number;
  salaryRange?: string;
  location?: string;
}