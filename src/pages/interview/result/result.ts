// pages/interview/result/result.ts

interface Question {
  id: string;
  content: string;
  type: 'basic' | 'technical' | 'behavioral';
  duration: number;
  videoPath?: string;
  answer?: string;
}

interface Position {
  id: string;
  name: string;
  icon: string;
  description: string;
  tags: string[];
  questionCount: number;
  duration: number;
}

interface InterviewResult {
  position: Position;
  questions: Question[];
  totalTime: number;
  date: string;
  scores?: {
    professional: number;    // 专业能力
    communication: number;   // 沟通表达
    personality: number;     // 个人特质
    problemSolving: number; // 解决问题
    teamwork: number;       // 团队协作
  };
  suggestions?: string[];
  overallScore?: number;
}

Page({
  data: {
    loading: true,
    result: {} as InterviewResult,
    radarData: {
      categories: ['专业能力', '沟通表达', '个人特质', '解决问题', '团队协作'],
      scores: [0, 0, 0, 0, 0]
    },
    showShare: false
  },

  onLoad() {
    // 获取面试结果
    const result = wx.getStorageSync('interviewResults');
    if (!result) {
      wx.showToast({
        title: '未找到面试结果',
        icon: 'error'
      });
      setTimeout(() => {
        wx.switchTab({
          url: '/pages/index/index'
        });
      }, 1500);
      return;
    }

    // 模拟分析结果
    this.analyzeResult(result);
  },

  // 分析面试结果
  analyzeResult(result: InterviewResult) {
    // 模拟AI分析过程
    setTimeout(() => {
      // 生成模拟分数
      const scores = {
        professional: this.generateScore(),    // 专业能力
        communication: this.generateScore(),   // 沟通表达
        personality: this.generateScore(),     // 个人特质
        problemSolving: this.generateScore(),  // 解决问题
        teamwork: this.generateScore()         // 团队协作
      };

      // 生成总分
      const overallScore = Math.round(
        (scores.professional + 
         scores.communication + 
         scores.personality + 
         scores.problemSolving + 
         scores.teamwork) / 5
      );

      // 生成建议
      const suggestions = this.generateSuggestions(scores);

      // 更新结果
      result.scores = scores;
      result.suggestions = suggestions;
      result.overallScore = overallScore;

      this.setData({
        result,
        loading: false,
        radarData: {
          ...this.data.radarData,
          scores: [
            scores.professional,
            scores.communication,
            scores.personality,
            scores.problemSolving,
            scores.teamwork
          ]
        }
      });

      // 保存更新后的结果
      wx.setStorageSync('interviewResults', result);
    }, 2000);
  },

  // 生成模拟分数（60-100之间）
  generateScore() {
    return Math.floor(Math.random() * 41) + 60;
  },

  // 生成建议
  generateSuggestions(scores: InterviewResult['scores']) {
    const suggestions: string[] = [];
    
    if (scores) {
      if (scores.professional < 80) {
        suggestions.push('建议加强专业知识的学习，特别是新技术和行业动态的了解。');
      }
      if (scores.communication < 80) {
        suggestions.push('可以通过多参与技术分享和演讲来提升表达能力。');
      }
      if (scores.personality < 80) {
        suggestions.push('建议在回答问题时展现更多积极主动的态度。');
      }
      if (scores.problemSolving < 80) {
        suggestions.push('在描述问题解决过程时，可以更加条理清晰，突出关键步骤。');
      }
      if (scores.teamwork < 80) {
        suggestions.push('可以多分享团队协作的经验，展示团队合作精神。');
      }
    }

    // 如果分数都不错，添加一些鼓励性的建议
    if (suggestions.length === 0) {
      suggestions.push('整体表现不错，建议继续保持！');
      suggestions.push('可以尝试在回答中加入更多实际项目经验。');
    }

    return suggestions;
  },

  // 重新面试
  restartInterview() {
    wx.showModal({
      title: '确认重新面试',
      content: '是否要重新开始面试？',
      success: (res) => {
        if (res.confirm) {
          wx.navigateBack({
            delta: 2 // 返回到岗位选择页面
          });
        }
      }
    });
  },

  // 返回首页
  goHome() {
    wx.switchTab({
      url: '/pages/index/index'
    });
  },

  // 显示分享选项
  showShareOptions() {
    this.setData({
      showShare: true
    });
  },

  // 隐藏分享选项
  hideShareOptions() {
    this.setData({
      showShare: false
    });
  },

  // 分享到朋友圈（生成分享图片）
  async shareToMoments() {
    wx.showLoading({
      title: '生成图片中'
    });

    try {
      // 实际项目中这里应该调用后端API生成分享图片
      // 这里仅作演示
      setTimeout(() => {
        wx.hideLoading();
        wx.showToast({
          title: '生成图片成功',
          icon: 'success'
        });
        this.hideShareOptions();
      }, 1500);
    } catch (error) {
      wx.hideLoading();
      wx.showToast({
        title: '生成图片失败',
        icon: 'error'
      });
    }
  },

  // 导出PDF报告
  exportPDF() {
    wx.showLoading({
      title: '导出报告中'
    });

    try {
      // 实际项目中这里应该调用后端API生成PDF报告
      // 这里仅作演示
      setTimeout(() => {
        wx.hideLoading();
        wx.showToast({
          title: '导出报告成功',
          icon: 'success'
        });
        this.hideShareOptions();
      }, 1500);
    } catch (error) {
      wx.hideLoading();
      wx.showToast({
        title: '导出报告失败',
        icon: 'error'
      });
    }
  }
})