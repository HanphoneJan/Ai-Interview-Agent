// pages/interview/question/question.ts

// 面试问题类型定义
interface Question {
  id: string;
  content: string;
  type: 'basic' | 'technical' | 'behavioral';
  duration: number; // 回答时间（秒）
}

// 岗位类型定义
interface Position {
  id: string;
  name: string;
  icon: string;
  description: string;
  tags: string[];
  questionCount: number;
  duration: number; // 面试时长（分钟）
}

Page({
  data: {
    position: {} as Position,
    questions: [] as Question[],
    currentQuestionIndex: 0,
    totalQuestions: 0,
    loading: true,
    
    // 面试状态
    interviewStatus: 'ready', // ready, countdown, ongoing, paused, completed
    countdownSeconds: 3, // 开始前倒计时
    
    // 计时器
    timer: 0,
    remainingTime: 0, // 当前问题剩余时间（秒）
    totalTime: 0, // 总面试时间（秒）
    elapsedTime: 0, // 已用时间（秒）
    
    // 音视频相关
    isRecording: false,
    hasCamera: false,
    hasMicrophone: false,
    cameraContext: null as WechatMiniprogram.CameraContext | null,
    recordingPath: '',
    
    // 语音识别
    recognitionResult: '',
    isRecognizing: false,
    
    // 界面控制
    showTips: true,
    showNextButton: false
  },

  onLoad() {
    // 获取选中的岗位信息
    const position = wx.getStorageSync('selectedPosition');
    if (!position) {
      wx.showToast({
        title: '未选择岗位',
        icon: 'error'
      });
      setTimeout(() => {
        wx.navigateBack();
      }, 1500);
      return;
    }
    
    this.setData({
      position,
      totalQuestions: position.questionCount
    });
    
    // 检查设备权限
    this.checkDevicePermissions();
    
    // 加载面试问题
    this.loadQuestions();
  },
  
  onUnload() {
    // 清理定时器
    if (this.data.timer) {
      clearInterval(this.data.timer);
    }
    
    // 停止录制
    if (this.data.isRecording && this.data.cameraContext) {
      this.data.cameraContext.stopRecord();
    }
  },
  
  // 检查设备权限
  checkDevicePermissions() {
    wx.getSetting({
      success: (res) => {
        // 检查摄像头权限
        if (res.authSetting['scope.camera']) {
          this.setData({ hasCamera: true });
        } else {
          wx.authorize({
            scope: 'scope.camera',
            success: () => {
              this.setData({ hasCamera: true });
            },
            fail: () => {
              wx.showModal({
                title: '提示',
                content: '需要摄像头权限才能进行面试',
                showCancel: false
              });
            }
          });
        }
        
        // 检查麦克风权限
        if (res.authSetting['scope.record']) {
          this.setData({ hasMicrophone: true });
        } else {
          wx.authorize({
            scope: 'scope.record',
            success: () => {
              this.setData({ hasMicrophone: true });
            },
            fail: () => {
              wx.showModal({
                title: '提示',
                content: '需要麦克风权限才能进行面试',
                showCancel: false
              });
            }
          });
        }
      }
    });
  },
  
  // 加载面试问题
  loadQuestions() {
    // 模拟从服务器获取数据
    // 实际项目中应该从API获取
    setTimeout(() => {
      const questions: Question[] = [
        {
          id: 'q1',
          content: '请简要介绍一下你自己和你的专业背景。',
          type: 'basic',
          duration: 60
        },
        {
          id: 'q2',
          content: '你为什么对我们公司的这个岗位感兴趣？',
          type: 'basic',
          duration: 60
        },
        {
          id: 'q3',
          content: '请描述一个你在学习或工作中遇到的挑战，以及你是如何解决的？',
          type: 'behavioral',
          duration: 90
        },
        {
          id: 'q4',
          content: '在这个岗位中，你认为最重要的技能是什么？为什么？',
          type: 'behavioral',
          duration: 60
        },
        {
          id: 'q5',
          content: '你如何看待团队合作？请举例说明你在团队中的角色和贡献。',
          type: 'behavioral',
          duration: 90
        }
      ];
      
      // 根据岗位ID添加特定的技术问题
      if (this.data.position.id === 'ai_engineer') {
        questions.push(
          {
            id: 'q6',
            content: '请解释一下深度学习和机器学习的区别，以及它们各自的应用场景。',
            type: 'technical',
            duration: 90
          },
          {
            id: 'q7',
            content: '你使用过哪些机器学习框架？请分享一个你使用这些框架解决实际问题的经验。',
            type: 'technical',
            duration: 90
          }
        );
      } else if (this.data.position.id === 'data_analyst') {
        questions.push(
          {
            id: 'q6',
            content: '请描述你使用过的数据可视化工具和技术，以及如何选择合适的可视化方式。',
            type: 'technical',
            duration: 90
          },
          {
            id: 'q7',
            content: '在处理大数据时，你会采取哪些策略来提高数据处理的效率？',
            type: 'technical',
            duration: 90
          }
        );
      } else if (this.data.position.id === 'frontend') {
        questions.push(
          {
            id: 'q6',
            content: '请解释一下响应式设计的原理和实现方法。',
            type: 'technical',
            duration: 90
          },
          {
            id: 'q7',
            content: '你如何优化前端应用的性能？请分享一些具体的技术和方法。',
            type: 'technical',
            duration: 90
          }
        );
      } else if (this.data.position.id === 'backend') {
        questions.push(
          {
            id: 'q6',
            content: '请解释RESTful API的设计原则，以及你如何实现一个安全的API。',
            type: 'technical',
            duration: 90
          },
          {
            id: 'q7',
            content: '在设计数据库时，你会考虑哪些因素？如何优化数据库性能？',
            type: 'technical',
            duration: 90
          }
        );
      } else if (this.data.position.id === 'product') {
        questions.push(
          {
            id: 'q6',
            content: '请描述你的产品设计流程，从需求收集到最终交付。',
            type: 'technical',
            duration: 90
          },
          {
            id: 'q7',
            content: '你如何平衡用户需求、技术可行性和业务目标？',
            type: 'technical',
            duration: 90
          }
        );
      }
      
      // 随机打乱问题顺序
      const shuffledQuestions = this.shuffleArray(questions);
      
      // 限制问题数量
      const limitedQuestions = shuffledQuestions.slice(0, this.data.position.questionCount);
      
      this.setData({
        questions: limitedQuestions,
        totalQuestions: limitedQuestions.length,
        loading: false,
        remainingTime: limitedQuestions[0].duration
      });
    }, 1500); // 模拟网络延迟
  },
  
  // 打乱数组顺序（Fisher-Yates洗牌算法）
  shuffleArray(array: any[]) {
    const newArray = [...array];
    for (let i = newArray.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [newArray[i], newArray[j]] = [newArray[j], newArray[i]];
    }
    return newArray;
  },
  
  // 开始面试
  startInterview() {
    // 开始倒计时
    this.setData({
      interviewStatus: 'countdown',
      showTips: false
    });
    
    // 倒计时
    const countdownInterval = setInterval(() => {
      const seconds = this.data.countdownSeconds - 1;
      if (seconds <= 0) {
        clearInterval(countdownInterval);
        this.startQuestion();
      } else {
        this.setData({ countdownSeconds: seconds });
      }
    }, 1000);
  },
  
  // 开始当前问题
  startQuestion() {
    // 初始化摄像头
    const cameraContext = wx.createCameraContext();
    
    // 开始录制
    cameraContext.startRecord({
      success: () => {
        console.log('开始录制');
        this.setData({
          isRecording: true,
          interviewStatus: 'ongoing',
          cameraContext
        });
        
        // 开始语音识别
        this.startSpeechRecognition();
        
        // 开始计时
        const currentQuestion = this.data.questions[this.data.currentQuestionIndex];
        this.setData({
          remainingTime: currentQuestion.duration,
          timer: setInterval(() => {
            const remainingTime = this.data.remainingTime - 1;
            const elapsedTime = this.data.elapsedTime + 1;
            
            if (remainingTime <= 0) {
              // 时间到，自动进入下一题
              this.finishCurrentQuestion();
            } else {
              this.setData({
                remainingTime,
                elapsedTime
              });
            }
          }, 1000) as unknown as number
        });
      },
      fail: (err) => {
        console.error('录制失败', err);
        wx.showToast({
          title: '录制失败',
          icon: 'error'
        });
      }
    });
  },
  
  // 暂停面试
  pauseInterview() {
    if (this.data.timer) {
      clearInterval(this.data.timer);
    }
    
    if (this.data.isRecording && this.data.cameraContext) {
      this.data.cameraContext.stopRecord({
        success: (res) => {
          this.setData({
            recordingPath: res.tempVideoPath,
            isRecording: false,
            interviewStatus: 'paused'
          });
        }
      });
    }
    
    // 停止语音识别
    this.stopSpeechRecognition();
  },
  
  // 继续面试
  resumeInterview() {
    this.startQuestion();
  },
  
  // 完成当前问题
  finishCurrentQuestion() {
    // 清理定时器
    if (this.data.timer) {
      clearInterval(this.data.timer);
    }
    
    // 停止录制
    if (this.data.isRecording && this.data.cameraContext) {
      this.data.cameraContext.stopRecord({
        success: (res) => {
          console.log('录制完成', res.tempVideoPath);
          
          // 保存录制结果
          const questions = this.data.questions;
          questions[this.data.currentQuestionIndex].videoPath = res.tempVideoPath;
          
          this.setData({
            questions,
            isRecording: false,
            showNextButton: true
          });
        }
      });
    }
    
    // 停止语音识别
    this.stopSpeechRecognition();
    
    // 保存语音识别结果
    const questions = this.data.questions;
    questions[this.data.currentQuestionIndex].answer = this.data.recognitionResult;
    
    this.setData({
      questions,
      interviewStatus: this.data.currentQuestionIndex >= this.data.totalQuestions - 1 ? 'completed' : 'paused'
    });
  },
  
  // 下一个问题
  nextQuestion() {
    const nextIndex = this.data.currentQuestionIndex + 1;
    
    if (nextIndex >= this.data.questions.length) {
      // 面试完成，跳转到结果页面
      this.completeInterview();
      return;
    }
    
    this.setData({
      currentQuestionIndex: nextIndex,
      recognitionResult: '',
      showNextButton: false,
      countdownSeconds: 3,
      interviewStatus: 'countdown'
    });
    
    // 开始倒计时
    const countdownInterval = setInterval(() => {
      const seconds = this.data.countdownSeconds - 1;
      if (seconds <= 0) {
        clearInterval(countdownInterval);
        this.startQuestion();
      } else {
        this.setData({ countdownSeconds: seconds });
      }
    }, 1000);
  },
  
  // 完成面试
  completeInterview() {
    // 保存面试结果
    wx.setStorageSync('interviewResults', {
      position: this.data.position,
      questions: this.data.questions,
      totalTime: this.data.elapsedTime,
      date: new Date().toISOString()
    });
    
    // 跳转到结果页面
    wx.showToast({
      title: '面试完成',
      icon: 'success'
    });
    
    setTimeout(() => {
      wx.redirectTo({
        url: '/pages/interview/result/result'
      });
    }, 1500);
  },
  
  // 开始语音识别
  startSpeechRecognition() {
    // 实际项目中应该调用语音识别API
    // 这里只是模拟效果
    this.setData({
      isRecognizing: true
    });
    
    // 模拟实时语音识别结果
    const recognitionInterval = setInterval(() => {
      if (this.data.interviewStatus !== 'ongoing') {
        clearInterval(recognitionInterval);
        return;
      }
      
      // 模拟语音识别结果
      const currentQuestion = this.data.questions[this.data.currentQuestionIndex];
      const responses = [
        '我认为这个问题很重要...',
        '根据我的经验，我会...',
        '这个问题涉及到多个方面...',
        '我曾经处理过类似的情况...',
        '从技术角度来看，我认为...'
      ];
      
      const randomResponse = responses[Math.floor(Math.random() * responses.length)];
      
      this.setData({
        recognitionResult: this.data.recognitionResult 
          ? this.data.recognitionResult + ' ' + randomResponse
          : randomResponse
      });
    }, 5000); // 每5秒更新一次，模拟实时识别
  },
  
  // 停止语音识别
  stopSpeechRecognition() {
    this.setData({
      isRecognizing: false
    });
  },
  
  // 返回上一页
  goBack() {
    if (this.data.interviewStatus === 'ongoing' || this.data.interviewStatus === 'paused') {
      wx.showModal({
        title: '提示',
        content: '面试尚未完成，确定要退出吗？',
        success: (res) => {
          if (res.confirm) {
            // 清理资源
            if (this.data.timer) {
              clearInterval(this.data.timer);
            }
            
            if (this.data.isRecording && this.data.cameraContext) {
              this.data.cameraContext.stopRecord();
            }
            
            wx.navigateBack();
          }
        }
      });
    } else {
      wx.navigateBack();
    }
  },
  
  // 切换提示显示
  toggleTips() {
    this.setData({
      showTips: !this.data.showTips
    });
  }
})