#!/bin/bash
# HVAC AI Receptionist v5.0 - Setup Script
# Run: chmod +x setup.sh && ./setup.sh

set -e

echo "============================================"
echo "  HVAC AI Receptionist v5.0 Setup"
echo "============================================"
echo ""

# Check Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker not found. Install Docker first:"
    echo "   https://docs.docker.com/get-docker/"
    exit 1
fi
echo "✅ Docker found"

if ! command -v docker compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo "❌ Docker Compose not found."
    exit 1
fi
echo "✅ Docker Compose found"

# Create .env if not exists
if [ ! -f .env ]; then
    cp .env.example .env
    echo "✅ Created .env from template"
    echo ""
    echo "⚠️  IMPORTANT: Edit .env to add your API keys for production."
    echo "   For testing (mock mode), no keys needed - just run!"
    echo ""
fi

# Create directories
mkdir -p logs monitoring static

# Build and start
echo ""
echo "🚀 Building and starting containers..."
echo ""

docker compose up -d --build

echo ""
echo "============================================"
echo "  ✅ HVAC AI Receptionist is running!"
echo "============================================"
echo ""
echo "  🌐 Voice Demo:    http://localhost:8000/demo"
echo "  🔧 Onboarding:    http://localhost:8000/onboard"
echo "  📊 Health Check:   http://localhost:8000/health"
echo "  📝 API Docs:       http://localhost:8000/docs"
echo ""
echo "  Mode: $(grep MOCK_MODE .env | head -1 || echo 'MOCK (default)')"
echo ""
echo "  To stop:  docker compose down"
echo "  To logs:  docker compose logs -f hvac-api"
echo "  To test:  curl http://localhost:8000/api/mock/simulate-call -X POST -H 'Content-Type: application/json' -d '{}'"
echo ""
