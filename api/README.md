# Story Generation API

A comprehensive, production-ready API for generating children's bedtime stories from images using AI. This API integrates with ElevenLabs for text-to-speech and offers a wide range of features for story generation, management, and playback.

## Features

- **AI-powered Story Generation**: Analyze images and create coherent, engaging stories
- **Multi-language Support**: Generate stories in English, French, Japanese, and Indonesian
- **Text-to-Speech**: Convert stories to lifelike speech using ElevenLabs API
- **Background Music**: Add ambient music to enhance the storytelling experience
- **Real-time Status Updates**: WebSocket support for live generation progress
- **Asynchronous Processing**: Webhook notifications for long-running tasks
- **User Management**: Subscription tiers with different feature sets
- **Robust Error Handling**: Comprehensive error handling and logging
- **Rate Limiting**: Protect API resources based on subscription tier
- **Admin Interface**: Tools for monitoring and managing users and stories

## Project Architecture

The API follows a clean, modular architecture:

```
api/
  ├── main.py              # FastAPI app and endpoints
  ├── admin.py             # Admin endpoints
  ├── config.py            # Configuration and environment variables
  ├── models/              # Pydantic models for request/response
  │   └── story.py         # Story-related data models
  ├── services/            # Core business logic
  │   ├── image_service.py # Image analysis
  │   ├── story_service.py # Story generation
  │   ├── speech_service.py # Text-to-speech using ElevenLabs
  │   ├── music_service.py  # Background music mixing
  │   ├── auth_service.py   # Authentication
  │   ├── webhook_service.py # Webhook management
  │   └── websocket_service.py # WebSocket for real-time updates
  ├── db/                  # Database interactions
  │   ├── supabase.py      # Supabase client
  │   └── repositories/    # Data access repositories
  │       ├── story_repository.py
  │       └── user_repository.py
  ├── middleware/          # Request middleware
  │   ├── rate_limiter.py  # Rate limiting
  │   └── error_handler.py # Error handling
  └── utils/               # Helper functions
      ├── logger.py        # Logging setup
      └── env_validator.py # Environment validation
```

## Key Technology Stack

- **FastAPI**: High-performance API framework
- **Supabase**: Backend as a Service for database and storage
- **ElevenLabs**: Text-to-speech API
- **Hugging Face**: Image analysis models
- **OpenAI**: Story generation
- **Redis**: Rate limiting and caching
- **Docker**: Containerization for deployment
- **GitHub Actions**: CI/CD pipeline

## API Endpoints

### Story Endpoints

- `POST /api/stories/generate`: Generate a story (synchronous)
- `POST /api/stories/generate/webhook`: Generate a story asynchronously
- `GET /api/stories/status/{request_id}`: Get status of async generation
- `GET /api/stories/{story_id}`: Get a story by ID
- `GET /api/stories`: List stories with filtering and pagination
- `POST /api/stories/{story_id}/favorite`: Toggle story favorite status
- `POST /api/stories/{story_id}/played`: Record story playback
- `DELETE /api/stories/{story_id}`: Delete a story

### User Endpoints

- `GET /api/user/subscription`: Get user subscription features
- `GET /api/user/credits`: Get user credit balance
- `POST /api/user/credits/add`: Add credits to user account

### Admin Endpoints

- `GET /api/admin/stats`: Get system statistics
- `GET /api/admin/users`: List users with filtering
- `GET /api/admin/users/{user_id}`: Get detailed user information
- `POST /api/admin/users/{user_id}/update-subscription`: Update user subscription
- `POST /api/admin/users/{user_id}/update-credits`: Update user credits
- `GET /api/admin/stories/analytics`: Get story generation analytics
- `GET /api/admin/logs`: Get application logs

### WebSocket Endpoint

- `WebSocket /ws`: Real-time updates for story generation

## Environment Variables

Required environment variables:

```
SUPABASE_URL=<Supabase project URL>
SUPABASE_KEY=<Supabase anon key>
SUPABASE_SERVICE_ROLE_KEY=<Supabase service role key>
ELEVENLABS_API_KEY=<ElevenLabs API key>
HUGGINGFACE_API_TOKEN=<Hugging Face API token>
OPENAI_API_KEY=<OpenAI API key>
SECRET_KEY=<Secret key for JWT encryption>
```

Optional environment variables:

```
PORT=8000
ENVIRONMENT=development  # development, staging, production
LOG_LEVEL=INFO
CORS_ORIGINS=*
REDIS_URL=redis://localhost:6379/0  # Required in production
SENTRY_DSN=<Sentry DSN>  # Required in production
```

## Setup and Installation

### Prerequisites

- Python 3.9+
- Docker and Docker Compose (for deployment)
- Supabase account and project
- ElevenLabs API key
- Hugging Face API token
- OpenAI API key

### Local Development

1. Clone the repository
   ```bash
   git clone https://github.com/yourusername/story-generation-api.git
   cd story-generation-api
   ```

2. Create a virtual environment
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies
   ```bash
   pip install -r requirements.txt
   ```

4. Create a `.env` file based on `.env.example`
   ```bash
   cp .env.example .env
   # Edit the .env file with your API keys and configuration
   ```

5. Run the API server
   ```bash
   python -m api.main
   ```

The API will be available at `http://localhost:8000`.

### Running Tests

```bash
pytest tests/
```

### Docker Deployment

For development:
```bash
docker-compose up -d
```

For production:
```bash
docker-compose -f docker-compose.prod.yml up -d
```

## Frontend Integration

The API is designed to work with the Next.js frontend. See the frontend repository for details on how to integrate with this API.

## CI/CD Pipeline

The GitHub Actions workflow automates:
- Running tests
- Linting code
- Building Docker image
- Deploying to staging (develop branch)
- Deploying to production (main branch)

## License

This project is licensed under the MIT License.