.PHONY: help setup env up down build rebuild logs status api-key

# Default target
help:
	@echo "Vexa Retailer Service - Available commands:"
	@echo "  setup     - Complete setup (copy env, get API key, build and start)"
	@echo "  env       - Copy env.example to .env if .env doesn't exist"
	@echo "  api-key   - Get and store Vexa API key in .env file"
	@echo "  build     - Build Docker Compose services"
	@echo "  up        - Start services (docker compose up -d)"
	@echo "  down      - Stop services (docker compose down)"
	@echo "  rebuild   - Rebuild and restart services"
	@echo "  logs      - Show service logs"
	@echo "  status    - Show running containers"

# Complete setup process
setup: env api-key build up
	@echo "✅ Vexa Retailer setup complete!"
	@echo "🌐 API Gateway: http://localhost:$$(grep API_GATEWAY_HOST_PORT .env | cut -d= -f2)"
	@echo "🔧 Admin API: http://localhost:$$(grep ADMIN_API_HOST_PORT .env | cut -d= -f2)"

# Copy env.example to .env if .env doesn't exist
env:
	@if [ -f .env ]; then \
		echo "⚠️  .env file already exists, skipping copy"; \
	else \
		echo "📋 Copying env.example to .env..."; \
		cp env.example .env; \
		echo "✅ .env file created. Please edit VEXA_INFRA_API_KEY if needed."; \
	fi

# Get Vexa API key and store in .env
api-key:
	@echo "🔑 Getting Vexa API key..."
	@if [ ! -f .env ]; then \
		echo "❌ .env file not found. Run 'make env' first."; \
		exit 1; \
	fi
	@echo "📡 Testing connection to Vexa API..."
	@if curl -s https://gateway.dev.vexa.ai/ | grep -q "Welcome to the Vexa API Gateway"; then \
		echo "✅ Vexa API is accessible"; \
		CURRENT_KEY=$$(grep VEXA_INFRA_API_KEY .env | cut -d= -f2); \
		if [ "$$CURRENT_KEY" = "your-infra-api-key-here" ]; then \
			echo "⚠️  Please set your VEXA_INFRA_API_KEY in .env file manually"; \
			echo "   Contact your Vexa provider for the API key"; \
		else \
			echo "✅ VEXA_INFRA_API_KEY appears to be configured"; \
		fi; \
	else \
		echo "❌ Cannot reach Vexa API. Check your internet connection."; \
		exit 1; \
	fi

# Build services
build:
	@echo "🔨 Building services..."
	@docker compose build

# Start services
up:
	@echo "🚀 Starting services..."
	@docker compose up -d
	@echo "✅ Services started!"

# Stop services  
down:
	@echo "🛑 Stopping services..."
	@docker compose down --remove-orphans

# Rebuild and restart
rebuild: down build up

# Show logs
logs:
	@docker compose logs -f

# Show status
status:
	@echo "📊 Service status:"
	@docker compose ps
