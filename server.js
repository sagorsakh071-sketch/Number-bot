const express = require('express');
const axios = require('axios');
const fs = require('fs-extra');
const path = require('path');
const TelegramBot = require('node-telegram-bot-api');

const app = express();
const PORT = process.env.PORT || 8080;

// Telegram Bot Configuration
const TELEGRAM_TOKEN = '883125ZKeY0v4DV2k54dc';
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
    stats: path.join(DIR_30SEC, 'stats.json'),
    history: path.join(DIR_30SEC, 'history.json')
  },
  '1min': {
    results: path.join(DIR_1MIN, 'results.json'),
    aiModel: path.join(DIR_1MIN, 'ai_model.json'),
    stats: path.join(DIR_1MIN, 'stats.json'),
    history: path.join(DIR_1MIN, 'history.json')
  }
};

const SETTINGS_FILE = path.join(DATA_DIR, 'settings.json');

// Initialize files
function initializeFiles() {
  const defaultResults = { results: [], lastUpdate: null };
  const defaultModel = {
    numberFrequency: {},
    colorFrequency: {},
    bigSmallPatterns: [],
    timeBasedPatterns: {},
    sequencePatterns: [],
    numberSequencePatterns: [],
    streakPatterns: [],
    reversalPatterns: [],
    pairPatterns: {},
    triplePatterns: {},
    dayPerformance: {},
    lastUpdate: null,
    totalLearned: 0
  };
  const defaultStats = {
    wins: 0,
    losses: 0,
    totalPredictions: 0,
    accuracy: 0,
    winStreak: 0,
    lossStreak: 0,
    bestWinStreak: 0,
    worstLossStreak: 0,
    lastPeriod: null,
    totalBets: 0,
    totalWon: 0,
    totalLost: 0,
    profitLoss: 0,
    dailyWins: {},
    dailyLosses: {}
  };
  const defaultHistory = { predictions: [], results: [] };

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
    if (!fs.existsSync(FILES[market].history)) {
      fs.writeJsonSync(FILES[market].history, defaultHistory);
    }
  }

  if (!fs.existsSync(SETTINGS_FILE)) {
    fs.writeJsonSync(SETTINGS_FILE, { 
      activeMarket: '30sec',
      autoNotify: true,
      notifyPrediction: true,
      notifyResult: true,
      confidenceThreshold: 50
    });
  }
  
  console.log('✅ All files initialized');
}

initializeFiles();

// Powerful AI System Class
class PowerfulAI {
  constructor(marketType) {
    this.marketType = marketType;
    this.results = fs.readJsonSync(FILES[marketType].results);
    this.model = fs.readJsonSync(FILES[marketType].aiModel);
    this.stats = fs.readJsonSync(FILES[marketType].stats);
    this.history = fs.readJsonSync(FILES[marketType].history);
    this.currentPrediction = null;
    this.lastProcessedPeriod = null;
    this.lastNotifiedPeriod = null;
    this.isLearning = false;
    this.isFetching = false;
  }

  saveData() {
    try {
      fs.writeJsonSync(FILES[this.marketType].results, this.results);
      fs.writeJsonSync(FILES[this.marketType].aiModel, this.model);
      fs.writeJsonSync(FILES[this.marketType].stats, this.stats);
      fs.writeJsonSync(FILES[this.marketType].history, this.history);
    } catch (error) {
      console.error(`${this.marketType} save error:`, error);
    }
  }

  async fetchData(apiUrl) {
    if (this.isFetching) return null;
    this.isFetching = true;
    
    try {
      const response = await axios.get(`${apiUrl}?ts=${Date.now()}`, {
        timeout: 10000,
        headers: {
          'User-Agent': 'Mozilla/5.0 (Linux; Android 12) AppleWebKit/537.36',
          'Accept': 'application/json',
          'Origin': 'https://ar-lottery01.com',
          'Referer': 'https://ar-lottery01.com/'
        }
      });

      if (response.data && response.data.code === 0 && response.data.data) {
        const results = response.data.data.list;
        
        // Check for new period
        const latestResult = results[0];
        const latestPeriod = latestResult.issueNumber;
        
        // Only process if new period found
        if (latestPeriod !== this.lastProcessedPeriod) {
          console.log(`🆕 ${this.marketType}: New period found: ${latestPeriod}`);
          
          for (const result of results) {
            await this.processResult(result);
          }

          this.results.lastUpdate = new Date().toISOString();
          this.saveData();
          
          // Generate prediction from REAL data
          if (this.results.results.length > 0) {
            this.updatePredictionFromRealData();
          }
        }
        
        return results;
      }
    } catch (error) {
      // Silent error - will retry in 1 second
    } finally {
      this.isFetching = false;
    }
    
    return null;
  }

  async processResult(result) {
    try {
      const period = result.issueNumber;
      const number = parseInt(result.number);
      const color = result.color || 'unknown';
      const bigSmall = number >= 5 ? 'BIG' : 'SMALL';
      const evenOdd = number % 2 === 0 ? 'EVEN' : 'ODD';
      
      if (this.results.results.find(r => r.period === period)) {
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
        evenOdd: evenOdd,
        timestamp: new Date().toISOString(),
        prediction: this.currentPrediction ? this.currentPrediction.bigSmall : null,
        predictedNumber: this.currentPrediction ? this.currentPrediction.number : null,
        isWin: null
      };

      this.results.results.unshift(resultEntry);

      if (this.results.results.length > 10000) {
        this.results.results = this.results.results.slice(0, 10000);
      }

      await this.learn(period, number, color, bigSmall, evenOdd);

      this.lastProcessedPeriod = period;
      
      console.log(`📊 ${this.marketType}: Period ${period}, Number ${number}, ${bigSmall}`);
    } catch (error) {
      console.error(`${this.marketType} process error:`, error);
    }
  }

  async learn(period, number, color, bigSmall, evenOdd) {
    if (this.isLearning) return;
    this.isLearning = true;
    
    try {
      const model = this.model.model;
      
      // Number Frequency
      model.numberFrequency[number] = (model.numberFrequency[number] || 0) + 1;
      
      // Color Frequency
      const colors = color.split(',');
      colors.forEach(c => {
        if (c.trim()) {
          model.colorFrequency[c.trim()] = (model.colorFrequency[c.trim()] || 0) + 1;
        }
      });
      
      // BIG/SMALL Patterns
      model.bigSmallPatterns.push({
        period: period,
        result: bigSmall,
        number: number,
        evenOdd: evenOdd,
        timestamp: new Date().toISOString()
      });
      
      if (model.bigSmallPatterns.length > 2000) {
        model.bigSmallPatterns = model.bigSmallPatterns.slice(-2000);
      }
      
      // Time-based Patterns
      const hour = new Date().getHours();
      const timeKey = `${hour}:00`;
      
      if (!model.timeBasedPatterns[timeKey]) {
        model.timeBasedPatterns[timeKey] = { big: 0, small: 0, total: 0, numbers: {} };
      }
      
      if (bigSmall === 'BIG') {
        model.timeBasedPatterns[timeKey].big++;
      } else {
        model.timeBasedPatterns[timeKey].small++;
      }
      model.timeBasedPatterns[timeKey].total++;
      model.timeBasedPatterns[timeKey].numbers[number] = (model.timeBasedPatterns[timeKey].numbers[number] || 0) + 1;
      
      // Sequence Patterns (5-step)
      const recent5 = this.results.results.slice(0, 5);
      if (recent5.length === 5) {
        const sequence = recent5.map(r => r.bigSmall).join('-');
        model.sequencePatterns.push({
          sequence: sequence,
          nextResult: bigSmall,
          nextNumber: number
        });
        
        if (model.sequencePatterns.length > 1000) {
          model.sequencePatterns = model.sequencePatterns.slice(-1000);
        }
      }
      
      // Number Sequence Patterns
      if (recent5 && recent5.length === 5) {
        const numSequence = recent5.map(r => r.number).join('-');
        model.numberSequencePatterns.push({
          sequence: numSequence,
          nextNumber: number
        });
        
        if (model.numberSequencePatterns.length > 500) {
          model.numberSequencePatterns = model.numberSequencePatterns.slice(-500);
        }
      }
      
      // Streak Patterns
      let streak = 1;
      for (let i = 1; i < this.results.results.length; i++) {
        if (this.results.results[i].bigSmall === bigSmall) {
          streak++;
        } else {
          break;
        }
      }
      
      model.streakPatterns.push({
        streak: streak,
        result: bigSmall
      });
      
      if (model.streakPatterns.length > 500) {
        model.streakPatterns = model.streakPatterns.slice(-500);
      }
      
      // Reversal Patterns
      if (streak >= 3) {
        model.reversalPatterns.push({
          streak: streak,
          result: bigSmall,
          reversed: true
        });
      }
      
      // Pair Patterns
      if (this.results.results.length >= 2) {
        const prevResult = this.results.results[1];
        const pairKey = `${prevResult.bigSmall}-${bigSmall}`;
        model.pairPatterns[pairKey] = (model.pairPatterns[pairKey] || 0) + 1;
      }
      
      // Triple Patterns
      if (this.results.results.length >= 3) {
        const prev2 = this.results.results[1];
        const prev3 = this.results.results[2];
        const tripleKey = `${prev3.bigSmall}-${prev2.bigSmall}-${bigSmall}`;
        model.triplePatterns[tripleKey] = (model.triplePatterns[tripleKey] || 0) + 1;
      }
      
      // Day Performance
      const dayKey = new Date().toLocaleDateString();
      if (!model.dayPerformance[dayKey]) {
        model.dayPerformance[dayKey] = { big: 0, small: 0, total: 0 };
      }
      if (bigSmall === 'BIG') {
        model.dayPerformance[dayKey].big++;
      } else {
        model.dayPerformance[dayKey].small++;
      }
      model.dayPerformance[dayKey].total++;
      
      model.lastUpdate = new Date().toISOString();
      model.totalLearned++;
    } catch (error) {
      console.error(`${this.marketType} learn error:`, error);
    } finally {
      this.isLearning = false;
    }
  }

  async verifyPrediction(period, prediction, actualNumber, actualBigSmall) {
    try {
      const isCorrect = actualBigSmall === prediction.bigSmall;
      
      this.stats.totalPredictions++;
      this.stats.totalBets++;
      
      if (isCorrect) {
        this.stats.wins++;
        this.stats.winStreak++;
        this.stats.lossStreak = 0;
        this.stats.totalWon++;
        this.stats.profitLoss += 1;
        
        if (this.stats.winStreak > this.stats.bestWinStreak) {
          this.stats.bestWinStreak = this.stats.winStreak;
        }
      } else {
        this.stats.losses++;
        this.stats.lossStreak++;
        this.stats.winStreak = 0;
        this.stats.totalLost++;
        this.stats.profitLoss -= 1;
        
        if (this.stats.lossStreak > this.stats.worstLossStreak) {
          this.stats.worstLossStreak = this.stats.lossStreak;
        }
      }
      
      this.stats.accuracy = Math.round((this.stats.wins / this.stats.totalPredictions) * 100);
      this.stats.lastPeriod = period;
      
      const dayKey = new Date().toLocaleDateString();
      if (!this.stats.dailyWins[dayKey]) {
        this.stats.dailyWins[dayKey] = 0;
        this.stats.dailyLosses[dayKey] = 0;
      }
      if (isCorrect) {
        this.stats.dailyWins[dayKey]++;
      } else {
        this.stats.dailyLosses[dayKey]++;
      }
      
      this.history.predictions.push({
        period: period,
        predicted: prediction.bigSmall,
        actual: actualBigSmall,
        predictedNumber: prediction.number,
        actualNumber: actualNumber,
        isCorrect: isCorrect,
        confidence: prediction.confidence,
        reasoning: prediction.reasoning,
        timestamp: new Date().toISOString()
      });
      
      if (this.history.predictions.length > 1000) {
        this.history.predictions = this.history.predictions.slice(-1000);
      }
      
      this.history.results.push({
        period: period,
        number: actualNumber,
        bigSmall: actualBigSmall,
        isWin: isCorrect,
        timestamp: new Date().toISOString()
      });
      
      if (this.history.results.length > 1000) {
        this.history.results = this.history.results.slice(-1000);
      }
      
      const resultEntry = this.results.results.find(r => r.period === period);
      if (resultEntry) {
        resultEntry.isWin = isCorrect;
        resultEntry.prediction = prediction.bigSmall;
        resultEntry.predictedNumber = prediction.number;
      }
      
      const settings = fs.readJsonSync(SETTINGS_FILE);
      if (settings.activeMarket === this.marketType && settings.notifyResult) {
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
      
      const message = `📊 *Result Update*\n━━━━━━━━━━━━━━━━\n${marketLabel}\n📌 Period: \`${period}\`\n🎯 Number: \`${actualNumber}\`\n📈 Result: ${actualBigSmall === 'BIG' ? '🔴 BIG' : '🟢 SMALL'}\n\n🎯 Predicted: ${prediction.bigSmall === 'BIG' ? '🔴 BIG' : '🟢 SMALL'}\n🔢 Predicted Number: \`${prediction.number}\`\n\n${statusEmoji} *${statusText}*\n━━━━━━━━━━━━━━━━\n📊 Accuracy: ${this.stats.accuracy}%\n🏆 Wins: ${this.stats.wins}\n💔 Losses: ${this.stats.losses}\n🔥 Win Streak: ${this.stats.winStreak}`;
      
      await bot.sendMessage(ADMIN_USER_ID, message, { parse_mode: 'Markdown' });
    } catch (error) {
      console.error(`${this.marketType} notify error:`, error);
    }
  }

  generatePrediction() {
    try {
      const model = this.model.model;
      const results = this.results.results;
      
      if (results.length < 15) {
        return {
          bigSmall: 'BIG',
          confidence: 50,
          number: 5,
          risk: 'HIGH',
          reasoning: 'Insufficient data - learning...'
        };
      }
      
      const recentResults = results.slice(0, 50);
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
      let reasons = [];
      
      // Recent trend (25%)
      const bigRatio = bigCount / recentResults.length;
      bigProbability += (bigRatio - 0.5) * 25;
      smallProbability -= (bigRatio - 0.5) * 25;
      reasons.push(`Trend: ${bigCount}B/${smallCount}S`);
      
      // Streak reversal (20%)
      if (currentStreak >= 4) {
        if (currentResult.bigSmall === 'BIG') {
          smallProbability += 20;
          bigProbability -= 20;
          reasons.push(`Streak ${currentStreak}→Rev`);
        } else {
          bigProbability += 20;
          smallProbability -= 20;
          reasons.push(`Streak ${currentStreak}→Rev`);
        }
      }
      
      // Number frequency (15%)
      const recentNumbers = recentResults.map(r => r.number);
      const bigNumbers = recentNumbers.filter(n => n >= 5).length;
      const numberBigRatio = bigNumbers / recentNumbers.length;
      bigProbability += (numberBigRatio - 0.5) * 15;
      smallProbability -= (numberBigRatio - 0.5) * 15;
      
      // Time pattern (15%)
      const hour = new Date().getHours();
      const timeKey = `${hour}:00`;
      const timePattern = model.timeBasedPatterns[timeKey];
      
      if (timePattern && timePattern.total > 10) {
        const timeBigRatio = timePattern.big / timePattern.total;
        bigProbability += (timeBigRatio - 0.5) * 15;
        smallProbability -= (timeBigRatio - 0.5) * 15;
        reasons.push(`Time ${timeKey}`);
      }
      
      // Sequence matching (15%)
      const lastSequence = recentResults.slice(0, 5).map(r => r.bigSmall).join('-');
      const matchingSequences = model.sequencePatterns.filter(s => s.sequence === lastSequence);
      
      if (matchingSequences.length > 3) {
        const nextBigCount = matchingSequences.filter(s => s.nextResult === 'BIG').length;
        const nextBigRatio = nextBigCount / matchingSequences.length;
        bigProbability += (nextBigRatio - 0.5) * 15;
        smallProbability -= (nextBigRatio - 0.5) * 15;
        reasons.push(`Seq:${matchingSequences.length}`);
      }
      
      // Pair pattern (10%)
      if (results.length >= 2) {
        const prevResult = results[1];
        const pairKey = `${prevResult.bigSmall}-BIG`;
        const pairCount = model.pairPatterns[pairKey] || 0;
        if (pairCount > 0) {
          bigProbability += 5;
          smallProbability -= 5;
          reasons.push(`Pair:${pairCount}`);
        }
      }
      
      const totalProb = bigProbability + smallProbability;
      bigProbability = Math.max(5, Math.min(95, (bigProbability / totalProb) * 100));
      smallProbability = 100 - bigProbability;
      
      const predictedBigSmall = bigProbability >= smallProbability ? 'BIG' : 'SMALL';
      const confidence = Math.round(Math.max(bigProbability, smallProbability));
      
      const predictedNumber = this.predictNumber(predictedBigSmall, recentResults);
      
      let risk = 'MEDIUM';
      if (confidence >= 85) risk = 'VERY LOW';
      else if (confidence >= 75) risk = 'LOW';
      else if (confidence < 55) risk = 'HIGH';
      else if (confidence < 45) risk = 'VERY HIGH';
      
      return {
        bigSmall: predictedBigSmall,
        confidence: confidence,
        number: predictedNumber,
        risk: risk,
        reasoning: reasons.join(' | ')
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
      const recentNumbers = results.slice(0, 100).map(r => r.number);
      
      const numberCount = {};
      recentNumbers.forEach(n => {
        numberCount[n] = (numberCount[n] || 0) + 1;
      });
      
      const range = bigSmall === 'BIG' ? [5, 6, 7, 8, 9] : [0, 1, 2, 3, 4];
      
      const weights = range.map(num => ({
        number: num,
        weight: 1 / ((numberCount[num] || 0) + 1)
      }));
      
      weights.sort((a, b) => b.weight - a.weight);
      
      return weights[0].number;
    } catch (error) {
      return bigSmall === 'BIG' ? 7 : 2;
    }
  }

  // Prediction from REAL data only
  updatePredictionFromRealData() {
    try {
      const prediction = this.generatePrediction();
      
      const lastResult = this.results.results[0];
      
      if (!lastResult || !lastResult.period) {
        return null;
      }
      
      let nextPeriod;
      try {
        nextPeriod = (BigInt(lastResult.period) + 1n).toString();
      } catch {
        return null;
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
      
      const settings = fs.readJsonSync(SETTINGS_FILE);
      if (settings.activeMarket === this.marketType && 
          settings.notifyPrediction && 
          this.lastNotifiedPeriod !== nextPeriod) {
        this.lastNotifiedPeriod = nextPeriod;
        this.sendPredictionNotification();
      }
      
      console.log(`🎯 ${this.marketType} Prediction: Period ${nextPeriod}, ${prediction.bigSmall} (${prediction.confidence}%)`);
      
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
      const riskEmoji = pred.risk === 'VERY LOW' ? '💚' : pred.risk === 'LOW' ? '✅' : pred.risk === 'MEDIUM' ? '⚠️' : pred.risk === 'HIGH' ? '❌' : '⛔';
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

  getAnalysis() {
    try {
      const results = this.results.results;
      const model = this.model.model;
      
      const bigCount = results.filter(r => r.bigSmall === 'BIG').length;
      const smallCount = results.filter(r => r.bigSmall === 'SMALL').length;
      const total = bigCount + smallCount;
      
      const hotNumbers = Object.entries(model.numberFrequency)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 5)
        .map(([num, count]) => ({ number: parseInt(num), count }));
      
      const coldNumbers = Object.entries(model.numberFrequency)
        .sort((a, b) => a[1] - b[1])
        .slice(0, 5)
        .map(([num, count]) => ({ number: parseInt(num), count }));
      
      let currentStreak = 0;
      const currentResult = results[0];
      if (currentResult) {
        for (let i = 0; i < results.length; i++) {
          if (results[i].bigSmall === currentResult.bigSmall) {
            currentStreak++;
          } else {
            break;
          }
        }
      }
      
      return {
        bigSmallRatio: {
          big: bigCount,
          small: smallCount,
          bigPercentage: total > 0 ? Math.round((bigCount / total) * 100) : 0,
          smallPercentage: total > 0 ? Math.round((smallCount / total) * 100) : 0
        },
        hotNumbers: hotNumbers,
        coldNumbers: coldNumbers,
        currentStreak: currentStreak,
        currentStreakType: currentResult ? currentResult.bigSmall : 'N/A',
        totalResults: results.length,
        totalLearned: model.totalLearned,
        lastUpdate: this.results.lastUpdate
      };
    } catch (error) {
      return null;
    }
  }
}

// Initialize both AI systems
const AI30Sec = new PowerfulAI('30sec');
const AI1Min = new PowerfulAI('1min');

// Bot Commands
bot.onText(/\/start/, async (msg) => {
  const chatId = msg.chat.id;
  if (msg.from.id !== ADMIN_USER_ID) return;
  
  const settings = fs.readJsonSync(SETTINGS_FILE);
  const activeMarket = settings.activeMarket === '30sec' ? '⚡ 30 Second' : '⏱️ 1 Minute';
  
  const message = `🎯 *WinGo AI Prediction Bot*\n\n━━━━━━━━━━━━━━━━\n*Active Market:* ${activeMarket}\n\n*Commands:*\n\n⚡ /mode_30sec - Switch to 30 Second\n⏱️ /mode_1min - Switch to 1 Minute\n\n🎯 /prediction - Active market prediction\n📜 /history - Active market history\n📈 /stats - Active market stats\n📊 /analysis - Active market analysis\n\n━━━━━━━━━━━━━━━━`;
  
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
        { text: '📈 Stats', callback_data: 'stats' },
        { text: '📊 Analysis', callback_data: 'analysis' }
      ]
    ]
  };
  
  await bot.sendMessage(chatId, message, {
    parse_mode: 'Markdown',
    reply_markup: keyboard
  });
});

bot.onText(/\/mode_30sec/, async (msg) => {
  const chatId = msg.chat.id;
  if (msg.from.id !== ADMIN_USER_ID) return;
  
  const settings = fs.readJsonSync(SETTINGS_FILE);
  settings.activeMarket = '30sec';
  fs.writeJsonSync(SETTINGS_FILE, settings);
  
  await bot.sendMessage(chatId, '✅ *Active Market:* ⚡ 30 Second', { parse_mode: 'Markdown' });
});

bot.onText(/\/mode_1min/, async (msg) => {
  const chatId = msg.chat.id;
  if (msg.from.id !== ADMIN_USER_ID) return;
  
  const settings = fs.readJsonSync(SETTINGS_FILE);
  settings.activeMarket = '1min';
  fs.writeJsonSync(SETTINGS_FILE, settings);
  
  await bot.sendMessage(chatId, '✅ *Active Market:* ⏱️ 1 Minute', { parse_mode: 'Markdown' });
});

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
  
  await bot.sendMessage(chatId, message, { parse_mode: 'Markdown' });
});

bot.onText(/\/stats/, async (msg) => {
  const chatId = msg.chat.id;
  if (msg.from.id !== ADMIN_USER_ID) return;
  
  const settings = fs.readJsonSync(SETTINGS_FILE);
  const activeAI = settings.activeMarket === '30sec' ? AI30Sec : AI1Min;
  const marketLabel = settings.activeMarket === '30sec' ? '⚡ 30 Second' : '⏱️ 1 Minute';
  
  const stats = activeAI.stats;
  
  const message = `📊 *${marketLabel} Statistics*\n━━━━━━━━━━━━━━━━\n🏆 Wins: ${stats.wins}\n💔 Losses: ${stats.losses}\n📈 Total: ${stats.totalPredictions}\n🎯 Accuracy: ${stats.accuracy}%\n🔥 Win Streak: ${stats.winStreak}\n💔 Loss Streak: ${stats.lossStreak}\n🏆 Best Win Streak: ${stats.bestWinStreak}\n📚 Total Results: ${activeAI.results.results.length}\n💰 Profit/Loss: ${stats.profitLoss > 0 ? '+' : ''}${stats.profitLoss} units\n━━━━━━━━━━━━━━━━`;
  
  await bot.sendMessage(chatId, message, { parse_mode: 'Markdown' });
});

bot.onText(/\/analysis/, async (msg) => {
  const chatId = msg.chat.id;
  if (msg.from.id !== ADMIN_USER_ID) return;
  
  const settings = fs.readJsonSync(SETTINGS_FILE);
  const activeAI = settings.activeMarket === '30sec' ? AI30Sec : AI1Min;
  const marketLabel = settings.activeMarket === '30sec' ? '⚡ 30 Second' : '⏱️ 1 Minute';
  
  const analysis = activeAI.getAnalysis();
  
  if (!analysis) {
    await bot.sendMessage(chatId, '📊 No analysis yet');
    return;
  }
  
  const hotNumbers = analysis.hotNumbers.map(h => `${h.number} (${h.count}x)`).join(', ');
  const coldNumbers = analysis.coldNumbers.map(c => `${c.number} (${c.count}x)`).join(', ');
  
  const message = `📊 *${marketLabel} Analysis*\n━━━━━━━━━━━━━━━━\n📈 Total Results: ${analysis.totalResults}\n🧠 Total Learned: ${analysis.totalLearned}\n\n🔴 BIG: ${analysis.bigSmallRatio.bigPercentage}%\n🟢 SMALL: ${analysis.bigSmallRatio.smallPercentage}%\n\n🔥 Hot Numbers:\n${hotNumbers}\n\n❄️ Cold Numbers:\n${coldNumbers}\n\n📊 Current Streak: ${analysis.currentStreak} ${analysis.currentStreakType}\n━━━━━━━━━━━━━━━━`;
  
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
    
    const history = activeAI.getHistory(1, 10);
    
    let message = '📜 *History*\n━━━━━━━━━━━━━━━━\n\n';
    
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
  } else if (data === 'analysis') {
    await bot.answerCallbackQuery(query.id);
    const activeAI = settings.activeMarket === '30sec' ? AI30Sec : AI1Min;
    
    const analysis = activeAI.getAnalysis();
    
    if (analysis) {
      const message = `📊 *Analysis*\n━━━━━━━━━━━━━━━━\n🔴 BIG: ${analysis.bigSmallRatio.bigPercentage}%\n🟢 SMALL: ${analysis.bigSmallRatio.smallPercentage}%\n📈 Total: ${analysis.totalResults}\n━━━━━━━━━━━━━━━━`;
      
      await bot.sendMessage(chatId, message, { parse_mode: 'Markdown' });
    }
  }
});

// Start server
app.listen(PORT, () => {
  console.log(`🚀 Server running on port ${PORT}`);
  console.log(`⚡ Real-time period check every 1 second`);
  
  startRealTimeMonitoring();
});

// Real-time monitoring - every 1 second
async function startRealTimeMonitoring() {
  console.log('📡 Starting real-time monitoring (1 second interval)...');
  
  // Check 30Sec API every 1 second
  setInterval(async () => {
    await AI30Sec.fetchData(API_30SEC);
  }, 1000);
  
  // Check 1Min API every 1 second
  setInterval(async () => {
    await AI1Min.fetchData(API_1MIN);
  }, 1000);
  
  console.log('✅ Real-time monitoring started');
}

console.log('✅ System ready!');