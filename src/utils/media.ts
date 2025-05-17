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
/**
 * 初始化相机上下文
 * @returns 相机上下文实例
 */
export function getCameraContext(): WechatMiniprogram.CameraContext {
  if (!cameraContext) {
    cameraContext = wx.createCameraContext();
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
export function startAudioRecording(options: Partial<WechatMiniprogram.RecorderManagerStartOption> = {}): Promise<void> {
  return new Promise((resolve, reject) => {
    const recorder = getRecorderManager();
    
    const defaultOptions: WechatMiniprogram.RecorderManagerStartOption = {
      duration: 60000,
      sampleRate: 16000,
      numberOfChannels: 1,
      encodeBitRate: 48000,
      format: 'mp3',
      frameSize: 50
    };
    
    const mergedOptions = { ...defaultOptions, ...options };
    
    recorder.start(mergedOptions);
    
    recorder.onStart(() => resolve());
    recorder.onError((error: WechatMiniprogram.GeneralCallbackResult) => reject(error));
  });
}

/**
 * 停止录音
 * @returns Promise<{tempFilePath: string}>
 */
export function stopAudioRecording(): Promise<{tempFilePath: string}> {
  return new Promise((resolve, reject) => {
    const recorder = getRecorderManager();
    
    recorder.onStop((res) => {
      if (res.tempFilePath) {
        resolve(res);
      } else {
        reject(new Error('录音文件创建失败'));
      }
    });
    
    recorder.onError((error: WechatMiniprogram.GeneralCallbackResult) => reject(error));
    recorder.stop();
  });
}

/**
 * 开始视频录制
 * @param cameraId 相机组件ID
 * @param options 录制选项
 * @returns Promise<void>
 */
export function startVideoRecording(cameraId: string, options: {timeoutCallback?: () => void} = {}): Promise<void> {
  return new Promise((resolve, reject) => {
    const camera = getCameraContext();
    
    camera.startRecord({
      ...options,
      success: () => resolve(),
      fail: (error: WechatMiniprogram.GeneralCallbackResult) => reject(error)
    });
  });
}

/**
 * 停止视频录制
 * @param cameraId 相机组件ID
 * @returns Promise<{tempVideoPath: string}>
 */
export function stopVideoRecording(cameraId: string): Promise<{tempVideoPath: string}> {
  return new Promise((resolve, reject) => {
    const camera = getCameraContext();
    
    camera.stopRecord({
      success: (res) => {
        if (res.tempVideoPath) {
          resolve(res);
        } else {
          reject(new Error('视频文件创建失败'));
        }
      },
      fail: (error: WechatMiniprogram.GeneralCallbackResult) => reject(error)
    });
  });
}

// 正确的小程序类型扩展声明
declare global {
  namespace WechatMiniprogram {
    interface Wx {
      getPluginAsync?(options: { plugin: string }): Promise<void>;
    }
  }
}

interface SpeechRecognitionManager {
  onStart: () => void;
  onRecognize: (res: any) => void;
  onStop: (res: {result: string}) => void;
  onError: (error: any) => void;
  start: (options: SpeechRecognitionOptions) => void;
  stop: () => void;
}

interface SpeechRecognitionOptions {
  lang?: string;
  duration?: number;
  [key: string]: any;
}

/**
 * 初始化语音识别插件
 * @returns Promise<boolean> 是否初始化成功
 */
export function initSpeechRecognition(): Promise<boolean> {
  return new Promise((resolve) => {
    if (!wx.getPluginAsync) {
      console.error('当前微信版本不支持插件');
      resolve(false);
      return;
    }

    wx.getPluginAsync({
      plugin: 'WechatSI'
    }).then(() => {
      console.log('语音识别插件加载成功');
      resolve(true);
    }).catch((error: any) => {
      console.error('语音识别插件加载失败', error);
      resolve(false);
    });
  });
}

/**
 * 开始语音识别
 * @param options 识别选项
 * @returns 识别管理器或null
 */
export function startSpeechRecognition(options: {
  lang?: string;
  duration?: number;
  onStart?: () => void;
  onRecognize?: (res: any) => void;
  onStop?: (res: {result: string}) => void;
  onError?: (error: any) => void;
} = {}): SpeechRecognitionManager | null {
  try {
    const plugin = requirePlugin('WechatSI') as {getRecognitionManager: () => SpeechRecognitionManager};
    const manager = plugin.getRecognitionManager();
    
    manager.onStart = options.onStart || (() => {});
    manager.onRecognize = options.onRecognize || (() => {});
    manager.onStop = options.onStop || (() => {});
    manager.onError = options.onError || (() => {});
    
    manager.start({
      lang: options.lang || 'zh_CN',
      duration: options.duration || 60000
    });
    
    return manager;
  } catch (error: any) {
    console.error('语音识别初始化失败', error);
    return null;
  }
}

/**
 * 停止语音识别
 * @param manager 识别管理器
 */
export function stopSpeechRecognition(manager: SpeechRecognitionManager | null): void {
  manager?.stop();
}