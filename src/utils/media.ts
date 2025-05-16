/**
 * 媒体工具函数
 * 处理音视频录制和语音识别相关功能
 */

// 录制管理器实例
let recorderManager: WechatMiniprogram.RecorderManager | null = null;
// 相机上下文实例
let cameraContext: WechatMiniprogram.CameraContext | null = null;

/**
 * 初始化录音管理器
 * @returns 录音管理器实例
 */
export function getRecorderManager(): WechatMiniprogram.RecorderManager {
  if (!recorderManager) {
    recorderManager = wx.getRecorderManager();
  }
  return recorderManager;
}

/**
 * 初始化相机上下文
 * @param cameraId 相机组件ID
 * @returns 相机上下文实例
 */
export function getCameraContext(cameraId: string): WechatMiniprogram.CameraContext {
  if (!cameraContext) {
    cameraContext = wx.createCameraContext(cameraId);
  }
  return cameraContext;
}

/**
 * 检查设备权限
 * @param scope 权限类型
 * @returns Promise<boolean> 是否有权限
 */
export function checkPermission(scope: 'scope.camera' | 'scope.record'): Promise<boolean> {
  return new Promise((resolve) => {
    wx.getSetting({
      success: (res) => {
        if (res.authSetting[scope]) {
          resolve(true);
        } else {
          wx.authorize({
            scope: scope,
            success: () => resolve(true),
            fail: () => resolve(false)
          });
        }
      },
      fail: () => resolve(false)
    });
  });
}

/**
 * 开始录音
 * @param options 录音选项
 * @returns Promise<void>
 */
export function startAudioRecording(options: WechatMiniprogram.RecorderManagerStartOption = {}): Promise<void> {
  return new Promise((resolve, reject) => {
    const recorder = getRecorderManager();
    
    // 设置默认选项
    const defaultOptions: WechatMiniprogram.RecorderManagerStartOption = {
      duration: 60000, // 最长录音时间，单位ms
      sampleRate: 16000, // 采样率
      numberOfChannels: 1, // 录音通道数
      encodeBitRate: 48000, // 编码码率
      format: 'mp3', // 音频格式
      frameSize: 50 // 指定帧大小，单位KB
    };
    
    // 合并选项
    const mergedOptions = { ...defaultOptions, ...options };
    
    recorder.start(mergedOptions);
    
    recorder.onStart(() => {
      resolve();
    });
    
    recorder.onError((error) => {
      reject(error);
    });
  });
}

/**
 * 停止录音
 * @returns Promise<WechatMiniprogram.RecorderManagerOnStopCallbackResult> 录音结果
 */
export function stopAudioRecording(): Promise<WechatMiniprogram.RecorderManagerOnStopCallbackResult> {
  return new Promise((resolve, reject) => {
    const recorder = getRecorderManager();
    
    recorder.onStop((res) => {
      resolve(res);
    });
    
    recorder.onError((error) => {
      reject(error);
    });
    
    recorder.stop();
  });
}

/**
 * 开始视频录制
 * @param cameraId 相机组件ID
 * @param options 录制选项
 * @returns Promise<void>
 */
export function startVideoRecording(cameraId: string, options: WechatMiniprogram.CameraContextStartRecordTimeoutOption = {}): Promise<void> {
  return new Promise((resolve, reject) => {
    const camera = getCameraContext(cameraId);
    
    // 设置默认选项
    const defaultOptions: WechatMiniprogram.CameraContextStartRecordTimeoutOption = {
      timeout: 60000, // 最长录制时间，单位ms
      success: () => resolve(),
      fail: (error) => reject(error)
    };
    
    // 合并选项
    const mergedOptions = { ...defaultOptions, ...options };
    
    camera.startRecord(mergedOptions);
  });
}

/**
 * 停止视频录制
 * @param cameraId 相机组件ID
 * @returns Promise<WechatMiniprogram.CameraContextStopRecordSuccessCallbackResult> 录制结果
 */
export function stopVideoRecording(cameraId: string): Promise<WechatMiniprogram.CameraContextStopRecordSuccessCallbackResult> {
  return new Promise((resolve, reject) => {
    const camera = getCameraContext(cameraId);
    
    camera.stopRecord({
      success: (res) => resolve(res),
      fail: (error) => reject(error)
    });
  });
}

/**
 * 初始化语音识别插件
 * @returns Promise<boolean> 是否初始化成功
 */
export function initSpeechRecognition(): Promise<boolean> {
  return new Promise((resolve) => {
    // 检查插件是否可用
    if (!wx.getPluginAsync) {
      console.error('当前微信版本不支持语音识别插件');
      resolve(false);
      return;
    }
    
    // 加载插件
    wx.getPluginAsync({
      plugin: 'WechatSI',
      success: () => {
        console.log('语音识别插件加载成功');
        resolve(true);
      },
      fail: (error) => {
        console.error('语音识别插件加载失败', error);
        resolve(false);
      }
    });
  });
}

/**
 * 开始语音识别
 * @param options 识别选项
 * @returns 识别管理器
 */
export function startSpeechRecognition(options: any = {}): any {
  // 获取插件
  const plugin = requirePlugin('WechatSI');
  if (!plugin) {
    console.error('未找到语音识别插件');
    return null;
  }
  
  // 获取全局唯一的语音识别管理器
  const manager = plugin.getRecognitionManager();
  
  // 设置事件处理
  manager.onStart = options.onStart || function() {};
  manager.onRecognize = options.onRecognize || function() {};
  manager.onStop = options.onStop || function() {};
  manager.onError = options.onError || function() {};
  
  // 开始识别
  manager.start({
    lang: options.lang || 'zh_CN',
    duration: options.duration || 60000,
    ...options
  });
  
  return manager;
}

/**
 * 停止语音识别
 * @param manager 识别管理器
 */
export function stopSpeechRecognition(manager: any): void {
  if (manager) {
    manager.stop();
  }
}