const express = require('express');
const axios = require('axios');
const fs = require('fs-extra');
const path = require('path');
const TelegramBot = require('node-telegram-bot-api');

const app = express();
const PORT = process.env.PORT || 8080;

// Telegram Bot Configuration
const TELEGRAM_TOKEN = '8831258161:AAGyaXGEsU6k9LGQXdfjZKeY0v4DV2k54dc';
const ADMIN_USER_ID = 7095358778;

// Initialize Telegram Bot
const bot = new TelegramBot(TELEGRAM_TOKEN, { 
  polling: true,
  onlyFirstMatch: true
});

// API Configuration
const API_1MIN = 'https://draw.ar-lottery01.com/WinGo/WinGo_1M/GetHistoryIssuePage.json';
const API_30SEC = 'https://draw.ar-lottery01.com/WinGo/WinGo_30S/GetHistoryIssuePage.json';

// Data Directory
const DATA_DIR = path.join(__dirname, 'data');
const DIR_30SEC = path.join(DATA_DIR, '30sec');
const DIR_1MIN = path.join(DATA_DIR, '1min');

fs.ensureDirSync(DIR_30SEC);
fs.ensureDirSync(DIR_1MIN);

// File paths
const FILES = {
  '30sec': {
    results: path.join(DIR_30SEC, 'results.json'),
    aiModel: path.join(DIR_30SEC, 'ai_model.json'),
    stats: path.join(DIR_30SEC, 'stats.json')
  },
  '1min': {
    results: path.join(DIR_1MIN, 'results.json'),
    aiModel: path.join(DIR_1MIN, 'ai_model.json'),
    stats: path.join(DIR_1MIN, 'stats.json')
  }
};

// Settings
const SETTINGS_FILE = path.join(DATA_DIR, 'settings.json');

// Initialize files
function initializeFiles() {
  const defaultResults = { results: [], lastUpdate: null };
  const defaultModel = {
    numberFrequency: {},
    bigSmallPatterns: [],
    timeBasedPatterns: {},
    sequencePatterns: [],
    lastUpdate: null
  };
  const defaultStats = {
    wins: 0,
    losses: 0,
    totalPredictions: 0,
    accuracy: 0,
    winStreak: 0,
    lossStreak: 0,
    lastPeriod: null
  };

  for (const market of ['30sec', '1min']) {
    if (!fs.existsSync(FILES[market].results)) {
      fs.writeJsonSync(FILES[market].results, defaultResults);
    }
    if (!fs.existsSync(FILES[market].aiModel)) {
      fs.writeJsonSync(FILES[market].aiModel, { model: defaultModel });
    }
    if (!fs.existsSync(FILES[market].stats)) {
      fs.writeJsonSync(FILES[market].stats, defaultStats);
    }
  }

  if (!fs.existsSync(SETTINGS_FILE)) {
    fs.writeJsonSync(SETTINGS_FILE, { activeMarket: '30sec' });
  }
  
  console.log('✅ All files initialized');
}

initializeFiles();

// Individual AI System Class
class MarketAI {
  constructor(marketType) {
    this.marketType = marketType; // '30sec' or '1min'
    this.results = fs.readJsonSync(FILES[marketType].results);
    this.model = fs.readJsonSync(FILES[marketType].aiModel);
    this.stats = fs.readJsonSync(FILES[marketType].stats);
    this.currentPrediction = null;
    this.lastProcessedPeriod = null;
    this.lastNotifiedPeriod = null;
  }

  saveData() {
    try {
      fs.writeJsonSync(FILES[this.marketType].results, this.results);
      fs.writeJsonSync(FILES[this.marketType].aiModel, this.model);
      fs.writeJsonSync(FILES[this.marketType].stats, this.stats);
    } catch (error) {
      console.error(`${this.marketType} save error:`, error);
    }
  }

  async fetchData(apiUrl) {
    try {
      const response = await axios.get(`${apiUrl}?ts=${Date.now()}`, {
        timeout: 15000,
        headers: {
          'User-Agent': 'Mozilla/5.0 (Linux; Android 12) AppleWebKit/537.36',
          'Accept': 'application/json',
          'Origin': 'https://ar-lottery01.com',
          'Referer': 'https://ar-lottery01.com/'
        }
      });

      if (response.data && response.data.code === 0 && response.data.data) {
        const results = response.data.data.list;
        
        for (const result of results) {
          await this.processResult(result);
        }

        this.results.lastUpdate = new Date().toISOString();
        this.saveData();
        
        console.log(`✅ ${this.marketType}: Got ${results.length} results`);
        return results;
      }
    } catch (error) {
      console.error(`❌ ${this.marketType} API error:`, error.message);
    }
    return null;
  }

  async processResult(result) {
    try {
      const period = result.issueNumber;
      const number = parseInt(result.number);
      const color = result.color || 'unknown';
      const bigSmall = number >= 5 ? 'BIG' : 'SMALL';
      
      if (this.results.results.find(r => r.period === period)) {
        return;
      }

      // Check prediction match
      if (this.currentPrediction && this.currentPrediction.period === period) {
        await this.verifyPrediction(period, this.currentPrediction, number, bigSmall);
      }

      this.results.results.unshift({
        period: period,
        number: number,
        color: color,
        bigSmall: bigSmall,
        timestamp: new Date().toISOString(),
        prediction: this.currentPrediction ? this.currentPrediction.bigSmall : null,
        predictedNumber: this.currentPrediction ? this.currentPrediction.number : null,
        isWin: null
      });

      if (this.results.results.length > 5000) {
        this.results.results = this.results.results.slice(0, 5000);
      }

      await this.learn(period, number, color, bigSmall);

      this.lastProcessedPeriod = period;
    } catch (error) {
      console.error(`${this.marketType} process error:`, error);
    }
  }

  async learn(period, number, color, bigSmall) {
    try {
      const model = this.model.model;
      
      // Number frequency
      model.numberFrequency[number] = (model.numberFrequency[number] || 0) + 1;
      
      // Big/Small patterns
      model.bigSmallPatterns.push({
        period: period,
        result: bigSmall,
        number: number,
        timestamp: new Date().toISOString()
      });
      
      if (model.bigSmallPatterns.length > 1000) {
        model.bigSmallPatterns = model.bigSmallPatterns.slice(-1000);
      }
      
      // Time-based patterns
      const hour = new Date().getHours();
      const timeKey = `${hour}:00`;
      
      if (!model.timeBasedPatterns[timeKey]) {
        model.timeBasedPatterns[timeKey] = { big: 0, small: 0, total: 0 };
      }
      
      if (bigSmall === 'BIG') {
        model.timeBasedPatterns[timeKey].big++;
      } else {
        model.timeBasedPatterns[timeKey].small++;
      }
      model.timeBasedPatterns[timeKey].total++;
      
      // Sequence patterns
      const recentResults = this.results.results.slice(0, 10);
      if (recentResults.length === 10) {
        const sequence = recentResults.map(r => r.bigSmall).join('-');
        model.sequencePatterns.push({
          sequence: sequence,
          nextResult: bigSmall
        });
        
        if (model.sequencePatterns.length > 500) {
          model.sequencePatterns = model.sequencePatterns.slice(-500);
        }
      }
      
      model.lastUpdate = new Date().toISOString();
    } catch (error) {
      console.error(`${this.marketType} learn error:`, error);
    }
  }

  async verifyPrediction(period, prediction, actualNumber, actualBigSmall) {
    try {
      const isCorrect = actualBigSmall === prediction.bigSmall;
      
      this.stats.totalPredictions++;
      
      if (isCorrect) {
        this.stats.wins++;
        this.stats.winStreak++;
        this.stats.lossStreak = 0;
      } else {
        this.stats.losses++;
        this.stats.lossStreak++;
        this.stats.winStreak = 0;
      }
      
      this.stats.accuracy = Math.round((this.stats.wins / this.stats.totalPredictions) * 100);
      this.stats.lastPeriod = period;
      
      // Update result with win/loss
      const resultEntry = this.results.results.find(r => r.period === period);
      if (resultEntry) {
        resultEntry.isWin = isCorrect;
        resultEntry.prediction = prediction.bigSmall;
        resultEntry.predictedNumber = prediction.number;
      }
      
      // Send notification if this market is active
      const settings = fs.readJsonSync(SETTINGS_FILE);
      if (settings.activeMarket === this.marketType) {
        await this.sendResultNotification(period, actualNumber, actualBigSmall, isCorrect, prediction);
      }
      
      this.currentPrediction = null;
      this.saveData();
    } catch (error) {
      console.error(`${this.marketType} verify error:`, error);
    }
  }

  async sendResultNotification(period, actualNumber, actualBigSmall, isCorrect, prediction) {
    try {
      const statusEmoji = isCorrect ? '✅' : '❌';
      const statusText = isCorrect ? 'WIN 🏆' : 'LOSS 💔';
      const marketLabel = this.marketType === '30sec' ? '⚡ 30 Second' : '⏱️ 1 Minute';
      
      const message = `📊 *Result Update*\n━━━━━━━━━━━━━━━━\n${marketLabel}\n📌 Period: \`${period}\`\n🎯 Number: \`${actualNumber}\`\n📈 Result: ${actualBigSmall === 'BIG' ? '🔴 BIG' : '🟢 SMALL'}\n\n🎯 Predicted: ${prediction.bigSmall === 'BIG' ? '🔴 BIG' : '🟢 SMALL'}\n🔢 Predicted Number: \`${prediction.number}\`\n\n${statusEmoji} *${statusText}*\n━━━━━━━━━━━━━━━━\n📊 Accuracy: ${this.stats.accuracy}%\n🏆 Wins: ${this.stats.wins}\n💔 Losses: ${this.stats.losses}`;
      
      await bot.sendMessage(ADMIN_USER_ID, message, { parse_mode: 'Markdown' });
    } catch (error) {
      console.error(`${this.marketType} notify error:`, error);
    }
  }

  generatePrediction() {
    try {
      const model = this.model.model;
      const results = this.results.results;
      
      if (results.length < 10) {
        return {
          bigSmall: Math.random() < 0.5 ? 'BIG' : 'SMALL',
          confidence: 50,
          number: Math.floor(Math.random() * 10),
          risk: 'HIGH',
          reasoning: 'Collecting data...'
        };
      }
      
      const recentResults = results.slice(0, 30);
      const bigCount = recentResults.filter(r => r.bigSmall === 'BIG').length;
      const smallCount = recentResults.filter(r => r.bigSmall === 'SMALL').length;
      
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
      
      let bigProbability = 50;
      let smallProbability = 50;
      
      // Recent trend (40%)
      const bigRatio = bigCount / recentResults.length;
      bigProbability += (bigRatio - 0.5) * 40;
      smallProbability -= (bigRatio - 0.5) * 40;
      
      // Streak reversal (30%)
      if (currentStreak >= 4) {
        if (currentResult.bigSmall === 'BIG') {
          smallProbability += 30;
          bigProbability -= 30;
        } else {
          bigProbability += 30;
          smallProbability -= 30;
        }
      }
      
      // Number frequency (20%)
      const recentNumbers = recentResults.map(r => r.number);
      const bigNumbers = recentNumbers.filter(n => n >= 5).length;
      const numberBigRatio = bigNumbers / recentNumbers.length;
      bigProbability += (numberBigRatio - 0.5) * 20;
      smallProbability -= (numberBigRatio - 0.5) * 20;
      
      // Time pattern (10%)
      const hour = new Date().getHours();
      const timeKey = `${hour}:00`;
      const timePattern = model.timeBasedPatterns[timeKey];
      
      if (timePattern && timePattern.total > 0) {
        const timeBigRatio = timePattern.big / timePattern.total;
        bigProbability += (timeBigRatio - 0.5) * 10;
        smallProbability -= (timeBigRatio - 0.5) * 10;
      }
      
      const totalProb = bigProbability + smallProbability;
      bigProbability = Math.max(0, Math.min(100, (bigProbability / totalProb) * 100));
      smallProbability = 100 - bigProbability;
      
      const predictedBigSmall = bigProbability >= smallProbability ? 'BIG' : 'SMALL';
      const confidence = Math.round(Math.max(bigProbability, smallProbability));
      
      const predictedNumber = this.predictNumber(predictedBigSmall, recentResults);
      
      let risk = 'MEDIUM';
      if (confidence >= 80) risk = 'LOW';
      else if (confidence < 60) risk = 'HIGH';
      
      return {
        bigSmall: predictedBigSmall,
        confidence: confidence,
        number: predictedNumber,
        risk: risk,
        reasoning: `Trend: ${bigCount}B/${smallCount}S, Streak: ${currentStreak}`
      };
    } catch (error) {
      return {
        bigSmall: 'BIG',
        confidence: 50,
        number: 5,
        risk: 'HIGH',
        reasoning: 'Error'
      };
    }
  }

  predictNumber(bigSmall, results) {
    try {
      const recentNumbers = results.slice(0, 50).map(r => r.number);
      
      const numberCount = {};
      recentNumbers.forEach(n => {
        numberCount[n] = (numberCount[n] || 0) + 1;
      });
      
      const range = bigSmall === 'BIG' ? [5, 6, 7, 8, 9] : [0, 1, 2, 3, 4];
      
      let minCount = Infinity;
      let predictedNumber = range[0];
      
      range.forEach(num => {
        const count = numberCount[num] || 0;
        if (count < minCount) {
          minCount = count;
          predictedNumber = num;
        }
      });
      
      return predictedNumber;
    } catch (error) {
      return bigSmall === 'BIG' ? 7 : 2;
    }
  }

  updatePrediction() {
    try {
      const prediction = this.generatePrediction();
      
      const lastResult = this.results.results[0];
      let nextPeriod;
      
      if (lastResult && lastResult.period) {
        try {
          nextPeriod = (BigInt(lastResult.period) + 1n).toString();
        } catch {
          nextPeriod = new Date().getTime().toString();
        }
      } else {
        nextPeriod = new Date().getTime().toString();
      }
      
      this.currentPrediction = {
        period: nextPeriod,
        bigSmall: prediction.bigSmall,
        confidence: prediction.confidence,
        number: prediction.number,
        risk: prediction.risk,
        reasoning: prediction.reasoning,
        timestamp: new Date().toISOString()
      };
      
      this.saveData();
      
      // Send notification if active
      const settings = fs.readJsonSync(SETTINGS_FILE);
      if (settings.activeMarket === this.marketType && this.lastNotifiedPeriod !== nextPeriod) {
        this.lastNotifiedPeriod = nextPeriod;
        this.sendPredictionNotification();
      }
      
      return this.currentPrediction;
    } catch (error) {
      console.error(`${this.marketType} update error:`, error);
      return null;
    }
  }

  async sendPredictionNotification() {
    try {
      if (!this.currentPrediction) return;
      
      const pred = this.currentPrediction;
      const emoji = pred.bigSmall === 'BIG' ? '🔴' : '🟢';
      const riskEmoji = pred.risk === 'LOW' ? '✅' : pred.risk === 'MEDIUM' ? '⚠️' : '❌';
      const marketLabel = this.marketType === '30sec' ? '⚡ 30 Second' : '⏱️ 1 Minute';
      
      const message = `🎯 *New Prediction*\n━━━━━━━━━━━━━━━━\n${marketLabel}\n📌 Period: \`${pred.period}\`\n${emoji} Signal: *${pred.bigSmall}*\n🔢 Number: \`${pred.number}\`\n📊 Confidence: \`${pred.confidence}%\`\n${riskEmoji} Risk: \`${pred.risk}\`\n\n📝 ${pred.reasoning}\n━━━━━━━━━━━━━━━━\n🕐 ${new Date().toLocaleTimeString()}`;
      
      await bot.sendMessage(ADMIN_USER_ID, message, { parse_mode: 'Markdown' });
    } catch (error) {
      console.error(`${this.marketType} notify error:`, error);
    }
  }

  getHistory(page = 1, pageSize = 10) {
    const results = this.results.results;
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
}

// Initialize both AI systems
const AI30Sec = new MarketAI('30sec');
const AI1Min = new MarketAI('1min');

// Bot Commands
bot.onText(/\/start/, async (msg) => {
  const chatId = msg.chat.id;
  if (msg.from.id !== ADMIN_USER_ID) return;
  
  const settings = fs.readJsonSync(SETTINGS_FILE);
  const activeMarket = settings.activeMarket;
  
  const message = `🎯 *WinGo AI Prediction Bot*\n\n━━━━━━━━━━━━━━━━\n*Active Market:* ${activeMarket === '30sec' ? '⚡ 30 Second' : '⏱️ 1 Minute'}\n\n*Commands:*\n\n⚡ /mode_30sec - Switch to 30 Second\n⏱️ /mode_1min - Switch to 1 Minute\n\n🎯 /prediction - Active market prediction\n📜 /history - Active market history\n📈 /stats - Active market stats\n\n━━━━━━━━━━━━━━━━`;
  
  const keyboard = {
    inline_keyboard: [
      [
        { text: '⚡ 30 Second', callback_data: 'mode_30sec' },
        { text: '⏱️ 1 Minute', callback_data: 'mode_1min' }
      ],
      [
        { text: '🎯 Prediction', callback_data: 'prediction' },
        { text: '📜 History', callback_data: 'history' }
      ],
      [
        { text: '📈 Stats', callback_data: 'stats' }
      ]
    ]
  };
  
  await bot.sendMessage(chatId, message, {
    parse_mode: 'Markdown',
    reply_markup: keyboard
  });
});

// Mode switching
bot.onText(/\/mode_30sec/, async (msg) => {
  const chatId = msg.chat.id;
  if (msg.from.id !== ADMIN_USER_ID) return;
  
  const settings = fs.readJsonSync(SETTINGS_FILE);
  settings.activeMarket = '30sec';
  fs.writeJsonSync(SETTINGS_FILE, settings);
  
  await bot.sendMessage(chatId, '✅ *Active Market:* ⚡ 30 Second\n\nএখন থেকে শুধু 30 Second এর prediction আর result আসবে।', { parse_mode: 'Markdown' });
});

bot.onText(/\/mode_1min/, async (msg) => {
  const chatId = msg.chat.id;
  if (msg.from.id !== ADMIN_USER_ID) return;
  
  const settings = fs.readJsonSync(SETTINGS_FILE);
  settings.activeMarket = '1min';
  fs.writeJsonSync(SETTINGS_FILE, settings);
  
  await bot.sendMessage(chatId, '✅ *Active Market:* ⏱️ 1 Minute\n\nএখন থেকে শুধু 1 Minute এর prediction আর result আসবে।', { parse_mode: 'Markdown' });
});

// Get active market prediction
bot.onText(/\/prediction/, async (msg) => {
  const chatId = msg.chat.id;
  if (msg.from.id !== ADMIN_USER_ID) return;
  
  const settings = fs.readJsonSync(SETTINGS_FILE);
  const activeAI = settings.activeMarket === '30sec' ? AI30Sec : AI1Min;
  const marketLabel = settings.activeMarket === '30sec' ? '⚡ 30 Second' : '⏱️ 1 Minute';
  
  if (activeAI.currentPrediction) {
    const pred = activeAI.currentPrediction;
    const emoji = pred.bigSmall === 'BIG' ? '🔴' : '🟢';
    
    const message = `🎯 *Prediction*\n━━━━━━━━━━━━━━━━\n${marketLabel}\n📌 Period: \`${pred.period}\`\n${emoji} Signal: *${pred.bigSmall}*\n🔢 Number: \`${pred.number}\`\n📊 Confidence: \`${pred.confidence}%\`\n\n📝 ${pred.reasoning}\n━━━━━━━━━━━━━━━━`;
    
    await bot.sendMessage(chatId, message, { parse_mode: 'Markdown' });
  } else {
    await bot.sendMessage(chatId, `⏳ ${marketLabel} prediction generating...`);
  }
});

// Get active market history
bot.onText(/\/history/, async (msg) => {
  const chatId = msg.chat.id;
  if (msg.from.id !== ADMIN_USER_ID) return;
  
  const settings = fs.readJsonSync(SETTINGS_FILE);
  const activeAI = settings.activeMarket === '30sec' ? AI30Sec : AI1Min;
  const marketLabel = settings.activeMarket === '30sec' ? '⚡ 30 Second' : '⏱️ 1 Minute';
  
  const history = activeAI.getHistory(1, 10);
  
  if (history.results.length === 0) {
    await bot.sendMessage(chatId, `📜 No ${marketLabel} history yet`);
    return;
  }
  
  let message = `📜 *${marketLabel} History*\n━━━━━━━━━━━━━━━━\n\n`;
  
  history.results.forEach((result, index) => {
    const emoji = result.bigSmall === 'BIG' ? '🔴' : '🟢';
    let winLossText = '';
    
    if (result.isWin === true) winLossText = ' ✅ WIN';
    else if (result.isWin === false) winLossText = ' ❌ LOSS';
    
    message += `${index + 1}. \`${result.period}\`\n   ${emoji} ${result.bigSmall} | ${result.number}${winLossText}\n\n`;
  });
  
  message += `━━━━━━━━━━━━━━━━\n📄 Page 1 of ${history.pagination.totalPages}`;
  
  await bot.sendMessage(chatId, message, { parse_mode: 'Markdown' });
});

// Get active market stats
bot.onText(/\/stats/, async (msg) => {
  const chatId = msg.chat.id;
  if (msg.from.id !== ADMIN_USER_ID) return;
  
  const settings = fs.readJsonSync(SETTINGS_FILE);
  const activeAI = settings.activeMarket === '30sec' ? AI30Sec : AI1Min;
  const marketLabel = settings.activeMarket === '30sec' ? '⚡ 30 Second' : '⏱️ 1 Minute';
  
  const stats = activeAI.stats;
  
  const message = `📊 *${marketLabel} Statistics*\n━━━━━━━━━━━━━━━━\n🏆 Wins: ${stats.wins}\n💔 Losses: ${stats.losses}\n📈 Total: ${stats.totalPredictions}\n🎯 Accuracy: ${stats.accuracy}%\n🔥 Win Streak: ${stats.winStreak}\n📚 Total Results: ${activeAI.results.results.length}\n━━━━━━━━━━━━━━━━`;
  
  await bot.sendMessage(chatId, message, { parse_mode: 'Markdown' });
});

// Callback queries
bot.on('callback_query', async (query) => {
  const chatId = query.message.chat.id;
  const userId = query.from.id;
  const data = query.data;
  
  if (userId !== ADMIN_USER_ID) return;
  
  const settings = fs.readJsonSync(SETTINGS_FILE);
  
  if (data === 'mode_30sec') {
    settings.activeMarket = '30sec';
    fs.writeJsonSync(SETTINGS_FILE, settings);
    await bot.answerCallbackQuery(query.id, { text: '✅ 30 Second mode active' });
    await bot.sendMessage(chatId, '✅ *Active Market:* ⚡ 30 Second', { parse_mode: 'Markdown' });
  } else if (data === 'mode_1min') {
    settings.activeMarket = '1min';
    fs.writeJsonSync(SETTINGS_FILE, settings);
    await bot.answerCallbackQuery(query.id, { text: '✅ 1 Minute mode active' });
    await bot.sendMessage(chatId, '✅ *Active Market:* ⏱️ 1 Minute', { parse_mode: 'Markdown' });
  } else if (data === 'prediction') {
    await bot.answerCallbackQuery(query.id);
    const activeAI = settings.activeMarket === '30sec' ? AI30Sec : AI1Min;
    const marketLabel = settings.activeMarket === '30sec' ? '⚡ 30 Second' : '⏱️ 1 Minute';
    
    if (activeAI.currentPrediction) {
      const pred = activeAI.currentPrediction;
      const emoji = pred.bigSmall === 'BIG' ? '🔴' : '🟢';
      
      const message = `🎯 *Prediction*\n━━━━━━━━━━━━━━━━\n${marketLabel}\n📌 Period: \`${pred.period}\`\n${emoji} Signal: *${pred.bigSmall}*\n🔢 Number: \`${pred.number}\`\n📊 Confidence: \`${pred.confidence}%\`\n━━━━━━━━━━━━━━━━`;
      
      await bot.sendMessage(chatId, message, { parse_mode: 'Markdown' });
    }
  } else if (data === 'history') {
    await bot.answerCallbackQuery(query.id);
    const activeAI = settings.activeMarket === '30sec' ? AI30Sec : AI1Min;
    const marketLabel = settings.activeMarket === '30sec' ? '⚡ 30 Second' : '⏱️ 1 Minute';
    
    const history = activeAI.getHistory(1, 10);
    
    let message = `📜 *${marketLabel} History*\n━━━━━━━━━━━━━━━━\n\n`;
    
    history.results.forEach((result, index) => {
      const emoji = result.bigSmall === 'BIG' ? '🔴' : '🟢';
      message += `${index + 1}. ${emoji} ${result.bigSmall} | ${result.number}\n`;
    });
    
    await bot.sendMessage(chatId, message, { parse_mode: 'Markdown' });
  } else if (data === 'stats') {
    await bot.answerCallbackQuery(query.id);
    const activeAI = settings.activeMarket === '30sec' ? AI30Sec : AI1Min;
    
    const stats = activeAI.stats;
    
    const message = `📊 *Statistics*\n━━━━━━━━━━━━━━━━\n🏆 Wins: ${stats.wins}\n💔 Losses: ${stats.losses}\n🎯 Accuracy: ${stats.accuracy}%\n━━━━━━━━━━━━━━━━`;
    
    await bot.sendMessage(chatId, message, { parse_mode: 'Markdown' });
  }
});

// Start server
app.listen(PORT, () => {
  console.log(`🚀 Server running on port ${PORT}`);
  console.log(`📡 Fetching WinGo 30Sec + 1Min data...`);
  
  startDataCollection();
  startPredictionUpdates();
});

async function startDataCollection() {
  console.log('📡 Starting data collection...');
  
  // Initial fetch
  await AI30Sec.fetchData(API_30SEC);
  await AI1Min.fetchData(API_1MIN);
  
  // Fetch 30Sec every 30 seconds
  setInterval(async () => {
    await AI30Sec.fetchData(API_30SEC);
  }, 30000);
  
  // Fetch 1Min every 60 seconds
  setInterval(async () => {
    await AI1Min.fetchData(API_1MIN);
  }, 60000);
  
  console.log('✅ Data collection started');
}

function startPredictionUpdates() {
  console.log('🤖 Starting prediction engine...');
  
  // Update 30Sec prediction every 30 seconds
  setInterval(() => {
    AI30Sec.updatePrediction();
  }, 30000);
  
  // Update 1Min prediction every 60 seconds
  setInterval(() => {
    AI1Min.updatePrediction();
  }, 60000);
  
  // Initial predictions
  setTimeout(() => {
    AI30Sec.updatePrediction();
    AI1Min.updatePrediction();
  }, 10000);
  
  console.log('✅ Prediction engine started');
}

console.log('✅ System ready!');