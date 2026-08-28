#!/bin/bash

# Project ATLAS Setup Script

echo "Setting up ATLAS environment..."

# Backend setup
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env 2>/dev/null || echo "DATABASE_URL=sqlite+aiosqlite:///./atlas.db" > .env

# Android setup
cd ../android
chmod +x gradlew
./gradlew assembleDebug

echo "Setup complete!"
