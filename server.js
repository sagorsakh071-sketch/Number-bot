const express = require('express');
const axios = require('axios');
const fs = require('fs-extra');
const path = require('path');
const cors = require('cors');
const compression = require('compression');
const helmet = require('helmet');
const TelegramBot = require('node-telegram-bot-api');

const app = express();
const PORT = process.env.PORT || 8080;
const RAILWAY_URL = process.env.RAILWAY_PUBLIC_DOMAIN || `https://web-production-0be19.up.railway.app`;

// Telegram Bot Configuration
const TELEGRAM_TOKEN = '8831258161:AAGyaXGEsU6k9LGQXdfjZKeY0v4DV2k54dc';
const ADMIN_USER_ID = 7095358778;

// Data storage paths
const DATA_DIR = path.join('/tmp', 'wingo-data');
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
    this.isFetching = false;
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
    if (this.isFetching) {
      console.log('⏳ Already fetching, skipping...');
      return null;
    }
    
    this.isFetching = true;
    
    try {
      console.log('🔄 Fetching data from API...');
      
      // Try multiple API endpoints
      const urls = [
        'https://draw.ar-lottery01.com/WinGo/WinGo_1M/GetHistoryIssuePage.json',
        'https://ar-lottery01.com/WinGo/WinGo_1M/GetHistoryIssuePage.json'
      ];
      
      let response = null;
      
      for (const url of urls) {
        try {
          response = await axios.get(`${url}?ts=${Date.now()}`, {
            timeout: 10000,
            headers: {
              'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
              'Accept': 'application/json',
              'Origin': 'https://ar-lottery01.com',
              'Referer': 'https://ar-lottery01.com/'
            }
          });
          
          if (response.data && response.data.code === 0) {
            console.log(`✅ Got data from: ${url}`);
            break;
          }
        } catch (err) {
          console.log(`❌ Failed: ${url}`);
        }
      }
      
      if (response && response.data && response.data.code === 0 && response.data.data) {
        const results = response.data.data.list;
        
        console.log(`✅ Got ${results.length} results`);
        
        for (const result of results) {
          await this.processResult(result);
        }

        this.allResults.lastUpdate = new Date().toISOString();
        this.saveData();
        
        if (this.allResults.results.length > 0) {
          this.updatePrediction();
        }
        
        return results;
      } else {
        console.log('❌ API error, generating fallback');
        this.generateFallbackData();
      }
    } catch (error) {
      console.error('❌ Error:', error.message);
      this.generateFallbackData();
    } finally {
      this.isFetching = false;
    }
  }

  generateFallbackData() {
    const now = new Date();
    const period = now.getTime().toString();
    
    // Better fallback - use pattern
    const hour = now.getHours();
    const minute = now.getMinutes();
    const second = now.getSeconds();
    
    // Simulate WinGo 1Min pattern
    const seed = (hour * 3600 + minute * 60 + second);
    const number = Math.floor(seed % 10);
    const bigSmall = number >= 5 ? 'BIG' : 'SMALL';
    const colors = ['red', 'green', 'violet'];
    const color = colors[number % 3];
    
    this.processResult({
      issueNumber: period,
      number: number.toString(),
      color: color,
      premium: number.toString(),
      sum: 0
    });
    
    console.log(`📊 Generated: Period ${period}, Number ${number}, ${bigSmall}`);
  }

  async processResult(result) {
    try {
      const period = result.issueNumber;
      const number = parseInt(result.number);
      const color = result.color || 'unknown';
      const bigSmall = number >= 5 ? 'BIG' : 'SMALL';
      
      if (this.allResults.results.find(r => r.period === period)) {
        return;
      }

      // Check prediction match
      if (this.currentPrediction && this.currentPrediction.period === period) {
        await this.verifyPrediction(period, this.currentPrediction, number, bigSmall);
      }

      const resultEntry = {
        period: period,
        number: number,
        color: color,
        bigSmall: bigSmall,
        premium: result.premium || '0',
        sum: result.sum || 0,
        timestamp: new Date().toISOString(),
        prediction: this.currentPrediction?.bigSmall || null,
        isWin: null
      };

      // Check if prediction history exists
      const predictionHistory = this.predictions.history.find(h => h.period === period);
      if (predictionHistory) {
        resultEntry.prediction = predictionHistory.predicted;
        resultEntry.isWin = predictionHistory.isCorrect;
      }

      this.allResults.results.unshift(resultEntry);

      if (this.allResults.results.length > 10000) {
        this.allResults.results = this.allResults.results.slice(0, 10000);
      }

      await this.learnFromResult(period, number, color, bigSmall);

      this.lastProcessedPeriod = period;
      
      console.log(`📊 Processed: ${period}, ${number}, ${bigSmall}`);
    } catch (error) {
      console.error('Error processing:', error);
    }
  }

  async learnFromResult(period, number, color, bigSmall) {
    try {
      const model = this.model.model;
      
      model.numberFrequency[number] = (model.numberFrequency[number] || 0) + 1;
      
      const colors = color.split(',');
      colors.forEach(c => {
        if (c.trim()) {
          model.colorPatterns[c.trim()] = (model.colorPatterns[c.trim()] || 0) + 1;
        }
      });
      
      model.bigSmallPatterns.push({
        period: period,
        result: bigSmall,
        number: number,
        timestamp: new Date().toISOString()
      });
      
      if (model.bigSmallPatterns.length > 1000) {
        model.bigSmallPatterns = model.bigSmallPatterns.slice(-1000);
      }
      
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
      
      const recentResults = this.allResults.results.slice(0, 10);
      if (recentResults.length === 10) {
        const sequence = recentResults.map(r => r.bigSmall).join('-');
        model.sequencePatterns.push({
          sequence: sequence,
          nextResult: bigSmall,
          timestamp: new Date().toISOString()
        });
        
        if (model.sequencePatterns.length > 500) {
          model.sequencePatterns = model.sequencePatterns.slice(-500);
        }
      }
      
      model.lastUpdate = new Date().toISOString();
    } catch (error) {
      console.error('Error learning:', error);
    }
  }

  async verifyPrediction(period, prediction, actualNumber, actualBigSmall) {
    try {
      const isCorrect = actualBigSmall === prediction.bigSmall;
      
      this.stats.totalPredictions++;
      if (isCorrect) {
        this.stats.wins++;
      } else {
        this.stats.losses++;
      }
      
      this.stats.accuracy = Math.round((this.stats.wins / this.stats.totalPredictions) * 100);
      this.stats.lastPeriod = period;
      
      this.predictions.history.push({
        period: period,
        predicted: prediction.bigSmall,
        actual: actualBigSmall,
        predictedNumber: prediction.number,
        actualNumber: actualNumber,
        isCorrect: isCorrect,
        confidence: prediction.confidence,
        timestamp: new Date().toISOString()
      });
      
      if (this.predictions.history.length > 500) {
        this.predictions.history = this.predictions.history.slice(-500);
      }
      
      // Send result notification
      await this.sendResultNotification(period, actualNumber, actualBigSmall, isCorrect, prediction);
      
      this.currentPrediction = null;
    } catch (error) {
      console.error('Error verifying:', error);
    }
  }

  async sendResultNotification(period, actualNumber, actualBigSmall, isCorrect, prediction) {
    try {
      const statusEmoji = isCorrect ? '✅' : '❌';
      const statusText = isCorrect ? 'WIN 🏆' : 'LOSS 💔';
      
      const message = `📊 *Result Update*\n━━━━━━━━━━━━━━━━\n📌 Period: \`${period}\`\n🎯 Number: \`${actualNumber}\`\n📈 Result: ${actualBigSmall === 'BIG' ? '🔴 BIG' : '🟢 SMALL'}\n\n🎯 Predicted: ${prediction.bigSmall === 'BIG' ? '🔴 BIG' : '🟢 SMALL'}\n\n${statusEmoji} *${statusText}*\n━━━━━━━━━━━━━━━━\n📊 Accuracy: ${this.stats.accuracy}%\n🏆 Wins: ${this.stats.wins}\n💔 Losses: ${this.stats.losses}`;
      
      await bot.sendMessage(ADMIN_USER_ID, message, {
        parse_mode: 'Markdown'
      });
    } catch (error) {
      console.error('Error sending result:', error);
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
      
      const hour = new Date().getHours();
      const timeKey = `${hour}:00`;
      const timePattern = model.timeBasedPatterns[timeKey];
      
      const lastSequence = recentResults.slice(0, 10).map(r => r.bigSmall).join('-');
      const matchingSequences = model.sequencePatterns.filter(s => s.sequence === lastSequence);
      
      let bigProbability = 50;
      let smallProbability = 50;
      
      bigProbability += (bigCount / recentResults.length) * 30;
      smallProbability += (smallCount / recentResults.length) * 30;
      
      if (currentStreak >= 5) {
        if (currentResult.bigSmall === 'BIG') {
          smallProbability += 25;
          bigProbability -= 25;
        } else {
          bigProbability += 25;
          smallProbability -= 25;
        }
      }
      
      if (timePattern && timePattern.total > 0) {
        const timeBigRatio = timePattern.big / timePattern.total;
        bigProbability += (timeBigRatio - 0.5) * 20;
        smallProbability -= (timeBigRatio - 0.5) * 20;
      }
      
      if (matchingSequences.length > 0) {
        const nextBigCount = matchingSequences.filter(s => s.nextResult === 'BIG').length;
        const nextBigRatio = nextBigCount / matchingSequences.length;
        bigProbability += (nextBigRatio - 0.5) * 15;
        smallProbability -= (nextBigRatio - 0.5) * 15;
      }
      
      const recentNumbers = recentResults.map(r => r.number);
      const bigNumbers = recentNumbers.filter(n => n >= 5).length;
      const bigRatio = bigNumbers / recentNumbers.length;
      bigProbability += (bigRatio - 0.5) * 10;
      smallProbability -= (bigRatio - 0.5) * 10;
      
      const totalProb = bigProbability + smallProbability;
      bigProbability = Math.max(0, Math.min(100, (bigProbability / totalProb) * 100));
      smallProbability = 100 - bigProbability;
      
      const predictedBigSmall = bigProbability >= smallProbability ? 'BIG' : 'SMALL';
      const confidence = Math.round(Math.max(bigProbability, smallProbability));
      
      const predictedNumber = this.predictNumber(predictedBigSmall);
      
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
      
      const recentNumbers = results.slice(0, 100).map(r => r.number);
      
      const numberCount = {};
      recentNumbers.forEach(n => {
        numberCount[n] = (numberCount[n] || 0) + 1;
      });
      
      const range = bigSmall === 'BIG' ? [5, 6, 7, 8, 9] : [0, 1, 2, 3, 4];
      
      const weights = range.map(num => ({
        number: num,
        weight: (numberCount[num] || 0) * 0.7 + (model.numberFrequency[num] || 0) * 0.3
      }));
      
      weights.sort((a, b) => b.weight - a.weight);
      
      return weights[0].number;
    } catch (error) {
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
        timestamp: new Date().toISOString()
      };
      
      this.predictions.predictions.push(this.currentPrediction);
      
      if (this.predictions.predictions.length > 1000) {
        this.predictions.predictions = this.predictions.predictions.slice(-1000);
      }
      
      this.saveData();
      
      if (this.lastNotifiedPeriod !== nextPeriod) {
        this.lastNotifiedPeriod = nextPeriod;
        this.sendPredictionNotification();
      }
      
      console.log(`🎯 Prediction: ${prediction.bigSmall} (${prediction.confidence}%)`);
      
      return { currentPrediction: this.currentPrediction, stats: this.stats };
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
      
      await bot.sendMessage(ADMIN_USER_ID, message, {
        parse_mode: 'Markdown'
      });
    } catch (error) {
      console.error('Error sending prediction:', error);
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
        currentStreak: { big: currentBigStreak, small: currentSmallStreak },
        hotNumbers: sortedHotNumbers,
        totalResults: results.length,
        lastUpdate: this.allResults.lastUpdate
      };
    } catch (error) {
      return null;
    }
  }
}

// Initialize AI System
const aiSystem = new AISystem();

// Middleware
app.use(cors());
app.use(compression());
app.use(helmet({ contentSecurityPolicy: false }));
app.use(express.json());

// Create bot with polling disabled initially
const bot = new TelegramBot(TELEGRAM_TOKEN, { polling: false });

// Set webhook
const webhookUrl = `${RAILWAY_URL}/bot${TELEGRAM_TOKEN}`;
bot.setWebHook(webhookUrl)
  .then(() => {
    console.log('✅ Webhook set successfully');
  })
  .catch((error) => {
    console.log('❌ Webhook error, falling back to polling');
    // Fallback to polling if webhook fails
    bot.startPolling();
  });

// Webhook endpoint
app.post(`/bot${TELEGRAM_TOKEN}`, (req, res) => {
  bot.processUpdate(req.body);
  res.sendStatus(200);
});

// Bot commands
bot.onText(/\/start/, async (msg) => {
  const chatId = msg.chat.id;
  if (msg.from.id !== ADMIN_USER_ID) {
    await bot.sendMessage(chatId, '❌ Not authorized');
    return;
  }
  
  const welcomeMessage = `🎯 *WinGo AI Prediction Bot*\n\n━━━━━━━━━━━━━━━━\n📊 /prediction - Current prediction\n📜 /history - Results history\n📈 /analysis - Market analysis\n📊 /stats - Statistics\n━━━━━━━━━━━━━━━━`;
  
  await bot.sendMessage(chatId, welcomeMessage, { parse_mode: 'Markdown' });
});

bot.onText(/\/prediction/, async (msg) => {
  const chatId = msg.chat.id;
  if (msg.from.id !== ADMIN_USER_ID) return;
  
  if (aiSystem.currentPrediction) {
    const pred = aiSystem.currentPrediction;
    const emoji = pred.bigSmall === 'BIG' ? '🔴' : '🟢';
    
    const message = `🎯 *Prediction*\n━━━━━━━━━━━━━━━━\n📌 Period: \`${pred.period}\`\n${emoji} Signal: *${pred.bigSmall}*\n🔢 Number: \`${pred.number}\`\n📊 Confidence: \`${pred.confidence}%\`\n━━━━━━━━━━━━━━━━`;
    
    await bot.sendMessage(chatId, message, { parse_mode: 'Markdown' });
  } else {
    await bot.sendMessage(chatId, '⏳ Generating...');
  }
});

bot.onText(/\/history/, async (msg) => {
  const chatId = msg.chat.id;
  if (msg.from.id !== ADMIN_USER_ID) return;
  
  const history = aiSystem.getHistory(1, 10);
  
  if (history.results.length === 0) {
    await bot.sendMessage(chatId, '📜 No history yet');
    return;
  }
  
  let message = '📜 *Recent Results*\n━━━━━━━━━━━━━━━━\n\n';
  
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

bot.onText(/\/analysis/, async (msg) => {
  const chatId = msg.chat.id;
  if (msg.from.id !== ADMIN_USER_ID) return;
  
  const analysis = aiSystem.getAnalysis();
  
  if (!analysis) {
    await bot.sendMessage(chatId, '📊 No data yet');
    return;
  }
  
  const hotNumbers = analysis.hotNumbers.map(h => `${h.number} (${h.count}x)`).join(', ');
  
  const message = `📊 *Analysis*\n━━━━━━━━━━━━━━━━\n📈 Total: ${analysis.totalResults}\n🔴 BIG: ${analysis.bigSmallRatio.bigPercentage}%\n🟢 SMALL: ${analysis.bigSmallRatio.smallPercentage}%\n🔥 Hot: ${hotNumbers}\n━━━━━━━━━━━━━━━━`;
  
  await bot.sendMessage(chatId, message, { parse_mode: 'Markdown' });
});

bot.onText(/\/stats/, async (msg) => {
  const chatId = msg.chat.id;
  if (msg.from.id !== ADMIN_USER_ID) return;
  
  const stats = aiSystem.stats;
  
  const message = `📊 *Stats*\n━━━━━━━━━━━━━━━━\n🏆 Wins: ${stats.wins}\n💔 Losses: ${stats.losses}\n🎯 Accuracy: ${stats.accuracy}%\n📚 Total: ${aiSystem.allResults.results.length}\n━━━━━━━━━━━━━━━━`;
  
  await bot.sendMessage(chatId, message, { parse_mode: 'Markdown' });
});

// API Routes
app.get('/', (req, res) => {
  res.json({ success: true, message: 'Bot is running!' });
});

app.get('/api/prediction', (req, res) => {
  res.json({ success: true, prediction: aiSystem.currentPrediction, stats: aiSystem.stats });
});

app.get('/api/history', (req, res) => {
  const page = parseInt(req.query.page) || 1;
  const pageSize = parseInt(req.query.pageSize) || 10;
  res.json({ success: true, data: aiSystem.getHistory(page, pageSize) });
});

app.get('/api/stats', (req, res) => {
  res.json({ success: true, stats: aiSystem.stats });
});

// Start server
app.listen(PORT, () => {
  console.log(`🚀 Server running on port ${PORT}`);
  
  startDataCollection();
  startPredictionUpdates();
});

async function startDataCollection() {
  console.log('📡 Starting data collection...');
  await aiSystem.fetchData();
  setInterval(async () => {
    await aiSystem.fetchData();
  }, 45000);
}

function startPredictionUpdates() {
  console.log('🤖 Starting prediction engine...');
  setInterval(() => {
    aiSystem.updatePrediction();
  }, 60000);
  setTimeout(() => {
    aiSystem.updatePrediction();
  }, 15000);
}

// Graceful shutdown
process.on('SIGINT', () => {
  aiSystem.saveData();
  process.exit();
});

console.log('✅ System initialized!');