const express = require('express');
const axios = require('axios');
const fs = require('fs-extra');
const path = require('path');
const cors = require('cors');
const compression = require('compression');
const helmet = require('helmet');
const TelegramBot = require('node-telegram-bot-api');

const app = express();
const PORT = process.env.PORT || 3000;

// Telegram Bot Configuration
const TELEGRAM_TOKEN = '8831258161:AAGyaXGEsU6k9LGQXdfjZKeY0v4DV2k54dc';
const ADMIN_USER_ID = 7095358778;

// Initialize Telegram Bot
const bot = new TelegramBot(TELEGRAM_TOKEN, { polling: true });

// Middleware
app.use(cors());
app.use(compression());
app.use(helmet({
  contentSecurityPolicy: false,
  crossOriginEmbedderPolicy: false
}));
app.use(express.json());
app.use(express.static('public'));

// API Configuration
const API_URL = "https://draw.ar-lottery01.com/WinGo/WinGo_1M/GetHistoryIssuePage.json";

// Data storage paths
const DATA_DIR = path.join(__dirname, 'data');
const RESULTS_FILE = path.join(DATA_DIR, 'results.json');
const PREDICTIONS_FILE = path.join(DATA_DIR, 'predictions.json');
const AI_MODEL_FILE = path.join(DATA_DIR, 'ai_model.json');
const STATS_FILE = path.join(DATA_DIR, 'stats.json');

// Ensure data directory exists
fs.ensureDirSync(DATA_DIR);

// Initialize data files
function initializeFiles() {
  const files = {
    [RESULTS_FILE]: { results: [], lastUpdate: null },
    [PREDICTIONS_FILE]: { predictions: [], history: [] },
    [AI_MODEL_FILE]: {
      model: {
        bigSmallPatterns: [],
        numberFrequency: {},
        colorPatterns: {},
        timeBasedPatterns: {},
        sequencePatterns: [],
        weightMatrix: {},
        learningRate: 0.01,
        totalPredictions: 0,
        correctPredictions: 0,
        lastUpdate: null
      }
    },
    [STATS_FILE]: {
      wins: 0,
      losses: 0,
      totalPredictions: 0,
      accuracy: 0,
      lastPeriod: null
    }
  };

  for (const [file, data] of Object.entries(files)) {
    if (!fs.existsSync(file)) {
      fs.writeJsonSync(file, data);
      console.log(`✅ Created file: ${file}`);
    }
  }
}

initializeFiles();

// AI System Class
class AISystem {
  constructor() {
    this.model = fs.readJsonSync(AI_MODEL_FILE);
    this.stats = fs.readJsonSync(STATS_FILE);
    this.allResults = fs.readJsonSync(RESULTS_FILE);
    this.predictions = fs.readJsonSync(PREDICTIONS_FILE);
    this.currentPrediction = null;
    this.lastProcessedPeriod = null;
    this.lastNotifiedPeriod = null;
  }

  saveData() {
    try {
      fs.writeJsonSync(AI_MODEL_FILE, this.model);
      fs.writeJsonSync(STATS_FILE, this.stats);
      fs.writeJsonSync(RESULTS_FILE, this.allResults);
      fs.writeJsonSync(PREDICTIONS_FILE, this.predictions);
    } catch (error) {
      console.error('Error saving data:', error);
    }
  }

  async fetchData() {
    try {
      console.log('🔄 Fetching data from API...');
      
      const response = await axios.get(`${API_URL}?ts=${Date.now()}`, {
        timeout: 15000,
        headers: {
          'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
          'Accept': 'application/json'
        }
      });

      if (response.data && response.data.code === 0 && response.data.data) {
        const results = response.data.data.list;
        
        console.log(`✅ Got ${results.length} results from API`);
        
        for (const result of results) {
          await this.processResult(result);
        }

        this.allResults.lastUpdate = new Date().toISOString();
        this.saveData();
        
        // Generate prediction only after data is loaded
        if (this.allResults.results.length > 0) {
          this.updatePrediction();
        } else {
          console.log('⚠️ No results to process yet');
        }
        
        return results;
      } else {
        console.log('❌ API returned error:', response.data?.msg || 'Unknown error');
      }
    } catch (error) {
      console.error('❌ Error fetching data:', error.message);
      return null;
    }
  }

  async processResult(result) {
    try {
      const period = result.issueNumber;
      const number = parseInt(result.number);
      const color = result.color || 'unknown';
      const bigSmall = number >= 5 ? 'BIG' : 'SMALL';
      
      // Check if this period already processed
      if (this.allResults.results.find(r => r.period === period)) {
        return;
      }

      // Add to results
      this.allResults.results.unshift({
        period: period,
        number: number,
        color: color,
        bigSmall: bigSmall,
        premium: result.premium || '0',
        sum: result.sum || 0,
        timestamp: new Date().toISOString()
      });

      // Limit results to 10000
      if (this.allResults.results.length > 10000) {
        this.allResults.results = this.allResults.results.slice(0, 10000);
      }

      // Update AI Model
      await this.learnFromResult(period, number, color, bigSmall);

      // Check if prediction was correct
      if (this.currentPrediction && this.currentPrediction.period === period) {
        await this.verifyPrediction(period, this.currentPrediction);
      }

      this.lastProcessedPeriod = period;
      
      console.log(`📊 Processed: Period ${period}, Number ${number}, ${bigSmall}`);
    } catch (error) {
      console.error('Error processing result:', error);
    }
  }

  async learnFromResult(period, number, color, bigSmall) {
    try {
      const model = this.model.model;
      
      // Number frequency
      model.numberFrequency[number] = (model.numberFrequency[number] || 0) + 1;
      
      // Color patterns
      const colors = color.split(',');
      colors.forEach(c => {
        if (c.trim()) {
          model.colorPatterns[c.trim()] = (model.colorPatterns[c.trim()] || 0) + 1;
        }
      });
      
      // Big/Small patterns
      model.bigSmallPatterns.push({
        period: period,
        result: bigSmall,
        number: number,
        timestamp: new Date().toISOString()
      });
      
      // Keep last 1000 patterns
      if (model.bigSmallPatterns.length > 1000) {
        model.bigSmallPatterns = model.bigSmallPatterns.slice(-1000);
      }
      
      // Time-based patterns
      const hour = new Date().getHours();
      const timeKey = `${hour}:00`;
      
      if (!model.timeBasedPatterns[timeKey]) {
        model.timeBasedPatterns[timeKey] = {
          big: 0,
          small: 0,
          total: 0
        };
      }
      
      if (bigSmall === 'BIG') {
        model.timeBasedPatterns[timeKey].big++;
      } else {
        model.timeBasedPatterns[timeKey].small++;
      }
      model.timeBasedPatterns[timeKey].total++;
      
      // Sequence patterns (last 10 results)
      const recentResults = this.allResults.results.slice(0, 10);
      if (recentResults.length === 10) {
        const sequence = recentResults.map(r => r.bigSmall).join('-');
        model.sequencePatterns.push({
          sequence: sequence,
          nextResult: bigSmall,
          timestamp: new Date().toISOString()
        });
        
        // Keep last 500 sequences
        if (model.sequencePatterns.length > 500) {
          model.sequencePatterns = model.sequencePatterns.slice(-500);
        }
      }
      
      model.lastUpdate = new Date().toISOString();
    } catch (error) {
      console.error('Error learning from result:', error);
    }
  }

  async verifyPrediction(period, prediction) {
    try {
      const result = this.allResults.results.find(r => r.period === period);
      
      if (!result) return;
      
      const isCorrect = result.bigSmall === prediction.bigSmall;
      
      this.stats.totalPredictions++;
      if (isCorrect) {
        this.stats.wins++;
      } else {
        this.stats.losses++;
      }
      
      this.stats.accuracy = Math.round((this.stats.wins / this.stats.totalPredictions) * 100);
      this.stats.lastPeriod = period;
      
      // Save prediction history
      this.predictions.history.push({
        period: period,
        predicted: prediction.bigSmall,
        actual: result.bigSmall,
        predictedNumber: prediction.number,
        actualNumber: result.number,
        isCorrect: isCorrect,
        confidence: prediction.confidence,
        timestamp: new Date().toISOString()
      });
      
      // Keep last 500 predictions
      if (this.predictions.history.length > 500) {
        this.predictions.history = this.predictions.history.slice(-500);
      }
      
      // Send notification to admin
      await this.sendResultNotification(period, result, isCorrect);
      
      this.currentPrediction = null;
    } catch (error) {
      console.error('Error verifying prediction:', error);
    }
  }

  async sendResultNotification(period, result, isCorrect) {
    try {
      const message = `📊 *Result Update*\n━━━━━━━━━━━━━━━━\n📌 Period: \`${period}\`\n🎯 Number: \`${result.number}\`\n📈 Result: ${result.bigSmall === 'BIG' ? '🔴 BIG' : '🟢 SMALL'}\n✅ Prediction: ${isCorrect ? 'Correct! 🎉' : 'Wrong! ❌'}\n━━━━━━━━━━━━━━━━\n📊 Accuracy: ${this.stats.accuracy}%\n🏆 Wins: ${this.stats.wins}\n💔 Losses: ${this.stats.losses}`;
      
      await bot.sendMessage(ADMIN_USER_ID, message, {
        parse_mode: 'Markdown'
      });
    } catch (error) {
      console.error('Error sending notification:', error);
    }
  }

  generatePrediction() {
    try {
      const model = this.model.model;
      const results = this.allResults.results;
      
      if (results.length < 10) {
        return {
          bigSmall: 'BIG',
          confidence: 50,
          number: 5,
          risk: 'HIGH'
        };
      }
      
      // Analyze recent results
      const recentResults = results.slice(0, 30);
      const bigCount = recentResults.filter(r => r.bigSmall === 'BIG').length;
      const smallCount = recentResults.filter(r => r.bigSmall === 'SMALL').length;
      
      // Current streak
      let currentStreak = 0;
      const currentResult = recentResults[0];
      if (currentResult) {
        for (let i = 0; i < recentResults.length; i++) {
          if (recentResults[i].bigSmall === currentResult.bigSmall) {
            currentStreak++;
          } else {
            break;
          }
        }
      }
      
      // Time-based analysis
      const hour = new Date().getHours();
      const timeKey = `${hour}:00`;
      const timePattern = model.timeBasedPatterns[timeKey];
      
      // Sequence matching
      const lastSequence = recentResults.slice(0, 10).map(r => r.bigSmall).join('-');
      const matchingSequences = model.sequencePatterns.filter(s => s.sequence === lastSequence);
      
      // Calculate probabilities
      let bigProbability = 50;
      let smallProbability = 50;
      
      // Recent trend weight
      bigProbability += (bigCount / recentResults.length) * 30;
      smallProbability += (smallCount / recentResults.length) * 30;
      
      // Streak reversal logic
      if (currentStreak >= 5) {
        if (currentResult.bigSmall === 'BIG') {
          smallProbability += 25;
          bigProbability -= 25;
        } else {
          bigProbability += 25;
          smallProbability -= 25;
        }
      }
      
      // Time pattern weight
      if (timePattern && timePattern.total > 0) {
        const timeBigRatio = timePattern.big / timePattern.total;
        bigProbability += (timeBigRatio - 0.5) * 20;
        smallProbability -= (timeBigRatio - 0.5) * 20;
      }
      
      // Sequence pattern weight
      if (matchingSequences.length > 0) {
        const nextBigCount = matchingSequences.filter(s => s.nextResult === 'BIG').length;
        const nextBigRatio = nextBigCount / matchingSequences.length;
        bigProbability += (nextBigRatio - 0.5) * 15;
        smallProbability -= (nextBigRatio - 0.5) * 15;
      }
      
      // Number frequency weight
      const recentNumbers = recentResults.map(r => r.number);
      const bigNumbers = recentNumbers.filter(n => n >= 5).length;
      const bigRatio = bigNumbers / recentNumbers.length;
      bigProbability += (bigRatio - 0.5) * 10;
      smallProbability -= (bigRatio - 0.5) * 10;
      
      // Normalize probabilities
      const totalProb = bigProbability + smallProbability;
      bigProbability = Math.max(0, Math.min(100, (bigProbability / totalProb) * 100));
      smallProbability = 100 - bigProbability;
      
      // Determine prediction
      const predictedBigSmall = bigProbability >= smallProbability ? 'BIG' : 'SMALL';
      const confidence = Math.round(Math.max(bigProbability, smallProbability));
      
      // Predict specific number
      const predictedNumber = this.predictNumber(predictedBigSmall);
      
      // Determine risk level
      let risk = 'MEDIUM';
      if (confidence >= 85) risk = 'LOW';
      else if (confidence < 65) risk = 'HIGH';
      
      return {
        bigSmall: predictedBigSmall,
        confidence: confidence,
        number: predictedNumber,
        risk: risk,
        timestamp: new Date().toISOString()
      };
    } catch (error) {
      console.error('Error generating prediction:', error);
      return {
        bigSmall: 'BIG',
        confidence: 50,
        number: 5,
        risk: 'HIGH'
      };
    }
  }

  predictNumber(bigSmall) {
    try {
      const model = this.model.model;
      const results = this.allResults.results;
      
      // Get recent numbers
      const recentNumbers = results.slice(0, 100).map(r => r.number);
      
      // Count frequency of each number
      const numberCount = {};
      recentNumbers.forEach(n => {
        numberCount[n] = (numberCount[n] || 0) + 1;
      });
      
      // Get numbers in range
      const range = bigSmall === 'BIG' ? [5, 6, 7, 8, 9] : [0, 1, 2, 3, 4];
      
      // Calculate weights
      const weights = range.map(num => ({
        number: num,
        weight: (numberCount[num] || 0) * 0.7 + (model.numberFrequency[num] || 0) * 0.3
      }));
      
      // Sort by weight
      weights.sort((a, b) => b.weight - a.weight);
      
      return weights[0].number;
    } catch (error) {
      console.error('Error predicting number:', error);
      return bigSmall === 'BIG' ? 7 : 2;
    }
  }

  updatePrediction() {
    try {
      const prediction = this.generatePrediction();
      
      const lastResult = this.allResults.results[0];
      let nextPeriod;
      
      if (lastResult && lastResult.period) {
        try {
          nextPeriod = (BigInt(lastResult.period) + 1n).toString();
        } catch (error) {
          // Fallback to timestamp-based period
          const now = new Date();
          const year = now.getFullYear();
          const month = String(now.getMonth() + 1).padStart(2, '0');
          const day = String(now.getDate()).padStart(2, '0');
          const hour = String(now.getHours()).padStart(2, '0');
          const minute = String(now.getMinutes()).padStart(2, '0');
          const second = String(now.getSeconds()).padStart(2, '0');
          const millisecond = String(now.getMilliseconds()).padStart(3, '0');
          
          nextPeriod = `${year}${month}${day}${hour}${minute}${second}${millisecond}`;
        }
      } else {
        // Generate period from current time
        const now = new Date();
        const year = now.getFullYear();
        const month = String(now.getMonth() + 1).padStart(2, '0');
        const day = String(now.getDate()).padStart(2, '0');
        const hour = String(now.getHours()).padStart(2, '0');
        const minute = String(now.getMinutes()).padStart(2, '0');
        const second = String(now.getSeconds()).padStart(2, '0');
        const millisecond = String(now.getMilliseconds()).padStart(3, '0');
        
        nextPeriod = `${year}${month}${day}${hour}${minute}${second}${millisecond}`;
      }
      
      this.currentPrediction = {
        period: nextPeriod,
        bigSmall: prediction.bigSmall,
        confidence: prediction.confidence,
        number: prediction.number,
        risk: prediction.risk,
        timestamp: new Date().toISOString()
      };
      
      this.predictions.predictions.push(this.currentPrediction);
      
      // Keep last 1000 predictions
      if (this.predictions.predictions.length > 1000) {
        this.predictions.predictions = this.predictions.predictions.slice(-1000);
      }
      
      this.saveData();
      
      // Send notification if new period
      if (this.lastNotifiedPeriod !== nextPeriod) {
        this.lastNotifiedPeriod = nextPeriod;
        this.sendPredictionNotification();
      }
      
      console.log(`🎯 New prediction generated for period ${nextPeriod}: ${prediction.bigSmall} (${prediction.confidence}%)`);
      
      return {
        currentPrediction: this.currentPrediction,
        stats: this.stats,
        modelInfo: {
          totalResults: this.allResults.results.length,
          totalPredictions: this.stats.totalPredictions,
          accuracy: this.stats.accuracy,
          lastUpdate: this.model.model.lastUpdate
        }
      };
    } catch (error) {
      console.error('Error updating prediction:', error);
      return null;
    }
  }

  async sendPredictionNotification() {
    try {
      if (!this.currentPrediction) return;
      
      const pred = this.currentPrediction;
      const emoji = pred.bigSmall === 'BIG' ? '🔴' : '🟢';
      const riskEmoji = pred.risk === 'LOW' ? '✅' : pred.risk === 'MEDIUM' ? '⚠️' : '❌';
      
      const message = `🎯 *New Prediction*\n━━━━━━━━━━━━━━━━\n📌 Period: \`${pred.period}\`\n${emoji} Signal: *${pred.bigSmall}*\n🔢 Number: \`${pred.number}\`\n📊 Confidence: \`${pred.confidence}%\`\n${riskEmoji} Risk: \`${pred.risk}\`\n━━━━━━━━━━━━━━━━\n🕐 ${new Date().toLocaleTimeString()}`;
      
      const keyboard = {
        inline_keyboard: [
          [
            { text: '📜 History', callback_data: 'history' },
            { text: '📊 Analysis', callback_data: 'analysis' }
          ],
          [
            { text: '📈 Stats', callback_data: 'stats' }
          ]
        ]
      };
      
      await bot.sendMessage(ADMIN_USER_ID, message, {
        parse_mode: 'Markdown',
        reply_markup: keyboard
      });
      
      console.log('✅ Prediction notification sent to Telegram');
    } catch (error) {
      console.error('Error sending prediction notification:', error);
    }
  }

  getHistory(page = 1, pageSize = 10) {
    const results = this.allResults.results;
    const totalPages = Math.ceil(results.length / pageSize);
    
    page = Math.max(1, Math.min(page, totalPages || 1));
    
    const startIndex = (page - 1) * pageSize;
    const endIndex = startIndex + pageSize;
    
    const pageResults = results.slice(startIndex, endIndex);
    
    return {
      results: pageResults,
      pagination: {
        currentPage: page,
        pageSize: pageSize,
        totalResults: results.length,
        totalPages: totalPages,
        hasNext: page < totalPages,
        hasPrev: page > 1
      }
    };
  }

  getAnalysis() {
    try {
      const results = this.allResults.results;
      
      const bigCount = results.filter(r => r.bigSmall === 'BIG').length;
      const smallCount = results.filter(r => r.bigSmall === 'SMALL').length;
      const total = bigCount + smallCount;
      
      const numberFreq = {};
      results.forEach(r => {
        numberFreq[r.number] = (numberFreq[r.number] || 0) + 1;
      });
      
      const colorFreq = {};
      results.forEach(r => {
        const colors = r.color.split(',');
        colors.forEach(c => {
          if (c.trim()) {
            colorFreq[c.trim()] = (colorFreq[c.trim()] || 0) + 1;
          }
        });
      });
      
      let currentBigStreak = 0;
      let currentSmallStreak = 0;
      
      for (let i = 0; i < results.length; i++) {
        if (results[i].bigSmall === 'BIG' && currentSmallStreak === 0) {
          currentBigStreak++;
        } else if (results[i].bigSmall === 'SMALL' && currentBigStreak === 0) {
          currentSmallStreak++;
        } else {
          break;
        }
      }
      
      // Hot numbers (most frequent in last 100)
      const recentNumbers = results.slice(0, 100);
      const hotNumbers = {};
      recentNumbers.forEach(r => {
        hotNumbers[r.number] = (hotNumbers[r.number] || 0) + 1;
      });
      
      const sortedHotNumbers = Object.entries(hotNumbers)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 5)
        .map(([num, count]) => ({ number: parseInt(num), count }));
      
      return {
        bigSmallRatio: {
          big: bigCount,
          small: smallCount,
          bigPercentage: total > 0 ? Math.round((bigCount / total) * 100) : 0,
          smallPercentage: total > 0 ? Math.round((smallCount / total) * 100) : 0
        },
        numberFrequency: numberFreq,
        colorFrequency: colorFreq,
        currentStreak: {
          big: currentBigStreak,
          small: currentSmallStreak
        },
        hotNumbers: sortedHotNumbers,
        totalResults: results.length,
        lastUpdate: this.allResults.lastUpdate
      };
    } catch (error) {
      console.error('Error getting analysis:', error);
      return null;
    }
  }
}

// Initialize AI System
const aiSystem = new AISystem();

// Telegram Bot Commands
bot.onText(/\/start/, async (msg) => {
  const chatId = msg.chat.id;
  const userId = msg.from.id;
  
  if (userId !== ADMIN_USER_ID) {
    await bot.sendMessage(chatId, '❌ You are not authorized to use this bot.');
    return;
  }
  
  const welcomeMessage = `🎯 *Welcome to WinGo AI Prediction Bot*\n\n━━━━━━━━━━━━━━━━\n*Available Commands:*\n\n📊 /prediction - Get current prediction\n📜 /history - View results history\n📈 /analysis - Market analysis\n📊 /stats - Win/Loss statistics\n🔄 /refresh - Refresh data\n❓ /help - Show all commands\n\n━━━━━━━━━━━━━━━━\n*AI System Status:*\n✅ Active\n🧠 Learning continuously\n📡 Auto-updating every minute`;
  
  const keyboard = {
    inline_keyboard: [
      [
        { text: '🎯 Prediction', callback_data: 'prediction' },
        { text: '📜 History', callback_data: 'history' }
      ],
      [
        { text: '📈 Analysis', callback_data: 'analysis' },
        { text: '📊 Stats', callback_data: 'stats' }
      ]
    ]
  };
  
  await bot.sendMessage(chatId, welcomeMessage, {
    parse_mode: 'Markdown',
    reply_markup: keyboard
  });
});

bot.onText(/\/prediction/, async (msg) => {
  const chatId = msg.chat.id;
  const userId = msg.from.id;
  
  if (userId !== ADMIN_USER_ID) {
    await bot.sendMessage(chatId, '❌ You are not authorized.');
    return;
  }
  
  if (aiSystem.currentPrediction) {
    const pred = aiSystem.currentPrediction;
    const emoji = pred.bigSmall === 'BIG' ? '🔴' : '🟢';
    const riskEmoji = pred.risk === 'LOW' ? '✅' : pred.risk === 'MEDIUM' ? '⚠️' : '❌';
    
    const message = `🎯 *Current Prediction*\n━━━━━━━━━━━━━━━━\n📌 Period: \`${pred.period}\`\n${emoji} Signal: *${pred.bigSmall}*\n🔢 Number: \`${pred.number}\`\n📊 Confidence: \`${pred.confidence}%\`\n${riskEmoji} Risk: \`${pred.risk}\`\n━━━━━━━━━━━━━━━━\n🕐 ${new Date().toLocaleTimeString()}`;
    
    await bot.sendMessage(chatId, message, { parse_mode: 'Markdown' });
  } else {
    await bot.sendMessage(chatId, '⏳ Prediction is being generated... Please wait.');
  }
});

bot.onText(/\/history/, async (msg) => {
  const chatId = msg.chat.id;
  const userId = msg.from.id;
  
  if (userId !== ADMIN_USER_ID) {
    await bot.sendMessage(chatId, '❌ You are not authorized.');
    return;
  }
  
  const history = aiSystem.getHistory(1, 10);
  
  if (history.results.length === 0) {
    await bot.sendMessage(chatId, '📜 No history available yet. Data is being collected...');
    return;
  }
  
  let message = '📜 *Recent Results*\n━━━━━━━━━━━━━━━━\n\n';
  
  history.results.forEach((result, index) => {
    const emoji = result.bigSmall === 'BIG' ? '🔴' : '🟢';
    message += `${index + 1}. \`${result.period}\`\n   ${emoji} ${result.bigSmall} | Number: ${result.number}\n\n`;
  });
  
  message += `━━━━━━━━━━━━━━━━\n📄 Page 1 of ${history.pagination.totalPages}`;
  
  await bot.sendMessage(chatId, message, { parse_mode: 'Markdown' });
});

bot.onText(/\/analysis/, async (msg) => {
  const chatId = msg.chat.id;
  const userId = msg.from.id;
  
  if (userId !== ADMIN_USER_ID) {
    await bot.sendMessage(chatId, '❌ You are not authorized.');
    return;
  }
  
  const analysis = aiSystem.getAnalysis();
  
  if (!analysis) {
    await bot.sendMessage(chatId, '📊 No analysis available yet. Data is being collected...');
    return;
  }
  
  const hotNumbers = analysis.hotNumbers.map(h => `${h.number} (${h.count}x)`).join(', ');
  
  const message = `📊 *Market Analysis*\n━━━━━━━━━━━━━━━━\n📈 Total Results: \`${analysis.totalResults}\`\n\n🔴 BIG: \`${analysis.bigSmallRatio.big}\` (${analysis.bigSmallRatio.bigPercentage}%)\n🟢 SMALL: \`${analysis.bigSmallRatio.small}\` (${analysis.bigSmallRatio.smallPercentage}%)\n\n🔥 Hot Numbers:\n${hotNumbers}\n\n📊 Current Streak:\n🔴 BIG: \`${analysis.currentStreak.big}\`\n🟢 SMALL: \`${analysis.currentStreak.small}\`\n━━━━━━━━━━━━━━━━\n🕐 ${new Date().toLocaleTimeString()}`;
  
  await bot.sendMessage(chatId, message, { parse_mode: 'Markdown' });
});

bot.onText(/\/stats/, async (msg) => {
  const chatId = msg.chat.id;
  const userId = msg.from.id;
  
  if (userId !== ADMIN_USER_ID) {
    await bot.sendMessage(chatId, '❌ You are not authorized.');
    return;
  }
  
  const stats = aiSystem.stats;
  
  const message = `📊 *Statistics*\n━━━━━━━━━━━━━━━━\n🏆 Total Wins: \`${stats.wins}\`\n💔 Total Losses: \`${stats.losses}\`\n📈 Total Predictions: \`${stats.totalPredictions}\`\n🎯 Accuracy: \`${stats.accuracy}%\`\n\n📚 Total Results: \`${aiSystem.allResults.results.length}\`\n🕐 Last Update: \`${aiSystem.allResults.lastUpdate || 'N/A'}\`\n━━━━━━━━━━━━━━━━`;
  
  await bot.sendMessage(chatId, message, { parse_mode: 'Markdown' });
});

bot.onText(/\/help/, async (msg) => {
  const chatId = msg.chat.id;
  const userId = msg.from.id;
  
  if (userId !== ADMIN_USER_ID) {
    await bot.sendMessage(chatId, '❌ You are not authorized.');
    return;
  }
  
  const message = `❓ *Help - Available Commands*\n━━━━━━━━━━━━━━━━\n🎯 /prediction - Get current prediction\n📜 /history - View results history (10 per page)\n📈 /analysis - Market analysis with hot numbers\n📊 /stats - Win/Loss statistics\n🔄 /refresh - Manually refresh data\n❓ /help - Show this help message\n\n*Auto Features:*\n🔔 Auto notification every minute\n📊 Auto result updates\n🧠 AI learning from every result\n━━━━━━━━━━━━━━━━`;
  
  await bot.sendMessage(chatId, message, { parse_mode: 'Markdown' });
});

bot.onText(/\/refresh/, async (msg) => {
  const chatId = msg.chat.id;
  const userId = msg.from.id;
  
  if (userId !== ADMIN_USER_ID) {
    await bot.sendMessage(chatId, '❌ You are not authorized.');
    return;
  }
  
  await bot.sendMessage(chatId, '🔄 Refreshing data...');
  await aiSystem.fetchData();
  await bot.sendMessage(chatId, '✅ Data refreshed successfully!');
});

// Handle callback queries
bot.on('callback_query', async (query) => {
  const chatId = query.message.chat.id;
  const userId = query.from.id;
  const data = query.data;
  
  if (userId !== ADMIN_USER_ID) {
    await bot.answerCallbackQuery(query.id, { text: '❌ Not authorized!' });
    return;
  }
  
  if (data === 'prediction') {
    await bot.answerCallbackQuery(query.id);
    if (aiSystem.currentPrediction) {
      const pred = aiSystem.currentPrediction;
      const emoji = pred.bigSmall === 'BIG' ? '🔴' : '🟢';
      
      const message = `🎯 *Current Prediction*\n━━━━━━━━━━━━━━━━\n📌 Period: \`${pred.period}\`\n${emoji} Signal: *${pred.bigSmall}*\n🔢 Number: \`${pred.number}\`\n📊 Confidence: \`${pred.confidence}%\`\n━━━━━━━━━━━━━━━━`;
      
      await bot.sendMessage(chatId, message, { parse_mode: 'Markdown' });
    }
  } else if (data === 'history') {
    await bot.answerCallbackQuery(query.id);
    const history = aiSystem.getHistory(1, 10);
    
    let message = '📜 *Recent Results*\n━━━━━━━━━━━━━━━━\n\n';
    
    history.results.forEach((result, index) => {
      const emoji = result.bigSmall === 'BIG' ? '🔴' : '🟢';
      message += `${index + 1}. \`${result.period}\`\n   ${emoji} ${result.bigSmall} | Number: ${result.number}\n\n`;
    });
    
    await bot.sendMessage(chatId, message, { parse_mode: 'Markdown' });
  } else if (data === 'analysis') {
    await bot.answerCallbackQuery(query.id);
    const analysis = aiSystem.getAnalysis();
    
    if (analysis) {
      const message = `📊 *Market Analysis*\n━━━━━━━━━━━━━━━━\n🔴 BIG: ${analysis.bigSmallRatio.bigPercentage}%\n🟢 SMALL: ${analysis.bigSmallRatio.smallPercentage}%\n📈 Total Results: ${analysis.totalResults}\n━━━━━━━━━━━━━━━━`;
      
      await bot.sendMessage(chatId, message, { parse_mode: 'Markdown' });
    }
  } else if (data === 'stats') {
    await bot.answerCallbackQuery(query.id);
    const stats = aiSystem.stats;
    
    const message = `📊 *Statistics*\n━━━━━━━━━━━━━━━━\n🏆 Wins: ${stats.wins}\n💔 Losses: ${stats.losses}\n🎯 Accuracy: ${stats.accuracy}%\n━━━━━━━━━━━━━━━━`;
    
    await bot.sendMessage(chatId, message, { parse_mode: 'Markdown' });
  }
});

// API Routes
app.get('/', (req, res) => {
  res.json({
    success: true,
    message: 'WinGo AI Prediction Bot is running!',
    status: 'active'
  });
});

app.get('/api/prediction', (req, res) => {
  try {
    res.json({
      success: true,
      prediction: aiSystem.currentPrediction,
      stats: aiSystem.stats
    });
  } catch (error) {
    res.status(500).json({
      success: false,
      error: error.message
    });
  }
});

app.get('/api/history', (req, res) => {
  try {
    const page = parseInt(req.query.page) || 1;
    const pageSize = parseInt(req.query.pageSize) || 10;
    
    const history = aiSystem.getHistory(page, pageSize);
    
    res.json({
      success: true,
      data: history
    });
  } catch (error) {
    res.status(500).json({
      success: false,
      error: error.message
    });
  }
});

app.get('/api/analysis', (req, res) => {
  try {
    const analysis = aiSystem.getAnalysis();
    
    res.json({
      success: true,
      data: analysis
    });
  } catch (error) {
    res.status(500).json({
      success: false,
      error: error.message
    });
  }
});

app.get('/api/stats', (req, res) => {
  try {
    res.json({
      success: true,
      stats: aiSystem.stats,
      modelInfo: {
        totalResults: aiSystem.allResults.results.length,
        totalPredictions: aiSystem.stats.totalPredictions,
        accuracy: aiSystem.stats.accuracy,
        lastUpdate: aiSystem.model.model.lastUpdate
      }
    });
  } catch (error) {
    res.status(500).json({
      success: false,
      error: error.message
    });
  }
});

// Start server
app.listen(PORT, () => {
  console.log(`🚀 WinGo AI Prediction Server running on port ${PORT}`);
  console.log(`🤖 Telegram Bot started!`);
  console.log(`📡 API: http://localhost:${PORT}`);
  
  // Start data collection
  startDataCollection();
  
  // Start prediction updates
  startPredictionUpdates();
});

// Data collection function
async function startDataCollection() {
  console.log('📡 Starting data collection...');
  
  // Initial fetch
  await aiSystem.fetchData();
  
  // Fetch every 30 seconds
  setInterval(async () => {
    await aiSystem.fetchData();
  }, 30000);
  
  console.log('✅ Data collection started (every 30 seconds)');
}

// Prediction updates
function startPredictionUpdates() {
  console.log('🤖 Starting AI prediction engine...');
  
  // Update prediction every 60 seconds
  setInterval(() => {
    aiSystem.updatePrediction();
  }, 60000);
  
  // Initial prediction (after 10 seconds to allow data fetch)
  setTimeout(() => {
    aiSystem.updatePrediction();
  }, 10000);
  
  console.log('✅ Prediction engine started (every 60 seconds)');
}

// Graceful shutdown
process.on('SIGINT', () => {
  console.log('👋 Shutting down gracefully...');
  aiSystem.saveData();
  bot.stopPolling();
  process.exit();
});

// Error handling
process.on('unhandledRejection', (error) => {
  console.error('❌ Unhandled rejection:', error);
});

process.on('uncaughtException', (error) => {
  console.error('❌ Uncaught exception:', error);
});

console.log('✅ System initialized successfully!');
console.log('📊 AI will start learning from market data...');