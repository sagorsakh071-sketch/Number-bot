#!/bin/bash

# Node dependencies install করো
npm install

# Baileys server start করো
node server.js &
NODE_PID=$!

echo "⏳ Waiting for Baileys to start..."
sleep 5

# Check করো node চলছে কিনা
if kill -0 $NODE_PID 2>/dev/null; then
    echo "✅ Baileys server started (PID: $NODE_PID)"
else
    echo "❌ Baileys failed to start, trying again..."
    node server.js &
    sleep 5
fi

echo "🚀 Starting Python bot..."
python bot.py
