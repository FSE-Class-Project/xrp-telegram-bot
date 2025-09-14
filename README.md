# XRP Telegram Bot

A professional Telegram bot for XRP Ledger transactions, built with FastAPI, Python-Telegram-Bot, and deployed on Render.

## 🌐 Live Deployment

- **API**: [https://xrp-bot-api.onrender.com](https://xrp-bot-api.onrender.com)
- **Network**: XRP TestNet
- **Status**: Production-ready TestNet implementation

## ✨ Features

### Core Functionality

- 🏦 **Automatic Wallet Creation** - Each user gets a secure XRP TestNet wallet *(educational feature)*
- 💸 **Send XRP** - Send TestNet XRP to any address with confirmation flow
- 💰 **Balance Checking** - Real-time balance updates from XRP Ledger
- 📜 **Transaction History** - Complete transaction tracking and history
- 📊 **Live Price Data** - Real-time XRP price from CoinGecko
- ⚙️ **User Settings** - Customizable preferences and notifications

### Security & Production Features

- 🔐 **Encrypted Storage** - Private keys encrypted at rest
- 🛡️ **Rate Limiting** - Prevents abuse with configurable limits
- 🔄 **Idempotency** - Prevents duplicate transactions
- 📱 **Rich UI** - Inline keyboards and formatted messages
- 🎯 **Input Validation** - Comprehensive XRP address and amount validation
- 📈 **Monitoring** - Health checks and comprehensive logging
- 🗄️ **Database Persistence** - PostgreSQL with SQLAlchemy ORM

## 🏗️ Architecture

### Backend (FastAPI)

- **API Server**: RESTful API with OpenAPI documentation
- **Database**: PostgreSQL with Alembic migrations
- **XRP Integration**: Direct connection to XRP Ledger TestNet
- **Caching**: Redis for improved performance (optional)
- **Authentication**: API key-based security

### Frontend (Telegram Bot)

- **Framework**: python-telegram-bot v20+
- **Mode**: Webhook-based for production, polling for development
- **UI**: Rich inline keyboards and HTML-formatted messages
- **State Management**: Conversation handlers for multi-step flows

### Infrastructure (Render)

- **Web Service**: `xrp-bot-api.onrender.com`
- **Database**: PostgreSQL `dpg-d2tce07fte5s73a3ln40-a`
- **Background Worker**: `srv-d2tcfc3e5dus73dn50h0`
- **Blueprint**: `exs-d2tcgg15pdvs739e7vgg`

## 🚀 Quick Start

### Development Setup

1. **Clone the repository**

   ```bash
   git clone https://github.com/ces0491/xrp-telegram-bot.git
   cd xrp-telegram-bot
   git checkout dev/ces
   ```

2. **Set up Python environment**

   ```bash
   # Create virtual environment
   python -m venv venv
   
   # Activate virtual environment
   # Windows:
   venv\Scripts\activate
   # Mac/Linux:
   source venv/bin/activate
   
   # Install dependencies
   pip install -r requirements.txt

   ```

3. **Environment setup**

   ```bash

   cp .env.example .env
   # Edit .env with your configuration

   ```

4. **Required Environment Variables**

   ```env

   # Telegram
   TELEGRAM_BOT_TOKEN=your_bot_token_from_botfather
   
   # Database (development uses SQLite)
   DATABASE_URL=sqlite:///./xrp_bot.db
   
   # Security
   ENCRYPTION_KEY=generate_with_fernet
   BOT_API_KEY=change-in-production
   ADMIN_API_KEY=change-in-production
   ```

5. **Run development server**

   ```bash

   python run.py
   ```

### Generate Test Wallet

Create a funded TestNet wallet:

```bash
python generate_test_wallet.py
```

This will:

- Generate a new XRP TestNet wallet
- Fund it with 10 XRP from the faucet
- Save wallet details to JSON file

## 📱 Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Register and create wallet |
| `/balance` | Check XRP balance |
| `/send` | Send XRP to another address |
| `/cancel` | Cancel ongoing transaction |
| `/price` | View current XRP price |
| `/history` | View transaction history |
| `/profile` | View your profile |
| `/settings` | Manage preferences |
| `/help` | Show all commands |

### Example Usage

**Send XRP:**

```text
/send 10 rN7n7otQDd6FczFgLdSqDtD2XZzWjfrn96
```

Or use the interactive flow:

```text
/send
> Enter amount: 10
> Enter address: rN7n7otQDd6FczFgLdSqDtD2XZzWjfrn96
> Confirm: YES  (or NO to cancel)
```

**Cancel Transaction:**
```text
/cancel  (cancels any ongoing transaction setup)
```

## 🌐 API Endpoints

### Core API

- `GET /api/v1/health` - Health check
- `POST /api/v1/user/register` - Register user
- `GET /api/v1/wallet/balance/{telegram_id}` - Get balance
- `POST /api/v1/transaction/send` - Send transaction
- `GET /api/v1/transaction/history/{telegram_id}` - Get history
- `GET /api/v1/price/current` - Get XRP price

### Documentation

- **Interactive Docs**: [https://xrp-bot-api.onrender.com/docs](https://xrp-bot-api.onrender.com/docs)
- **OpenAPI Schema**: [https://xrp-bot-api.onrender.com/openapi.json](https://xrp-bot-api.onrender.com/openapi.json)

## 🔧 Render Deployment

### Infrastructure Components

**Web Service** (`xrp-bot-api.onrender.com`)

- Runs the FastAPI backend
- Handles Telegram webhook
- Serves API endpoints
- Auto-deploys from Git

**PostgreSQL Database** (`dpg-d2tce07fte5s73a3ln40-a`)

- Production database
- Automated backups
- Connection pooling

**Background Worker** (`srv-d2tcfc3e5dus73dn50h0`)

- Runs the Telegram bot
- Handles background tasks
- Processes webhook updates

### Environment Variables (Production)

```env
# Render provides these automatically
DATABASE_URL=postgresql://...
RENDER_EXTERNAL_URL=https://xrp-bot-api.onrender.com
PORT=10000

# You must set these in Render dashboard
TELEGRAM_BOT_TOKEN=your_bot_token
ENCRYPTION_KEY=your_fernet_key
BOT_API_KEY=secure_api_key
ADMIN_API_KEY=secure_admin_key

# Optional
REDIS_URL=redis://...
SENTRY_DSN=your_sentry_dsn
```

### Build Commands

**Web Service:**

```bash
pip install -r requirements.txt
```

**Start Command:**

```bash
uvicorn backend.main:app --host 0.0.0.0 --port $PORT
```

**Background Worker:**

```bash
python -m bot.main
```

## 🔧 Configuration

### Network Settings

The bot is configured for XRP TestNet:

```python
XRP_NETWORK = "testnet"
XRP_WEBSOCKET_URL = "wss://s.altnet.rippletest.net:51233"
XRP_JSON_RPC_URL = "https://s.altnet.rippletest.net:51234"
XRP_FAUCET_URL = "https://faucet.altnet.rippletest.net/accounts"
```

### Rate Limits

- **User Registration**: 5/hour
- **Transactions**: 10/minute
- **Price Checks**: 30/minute
- **General API**: 100/minute

### Security Features

- Private keys encrypted with Fernet
- API key authentication
- Input validation and sanitization
- SQL injection protection
- Rate limiting
- Comprehensive logging

## 📊 Database Schema

### Users

- `id` - Primary key
- `telegram_id` - Telegram user ID
- `telegram_username` - Username
- `created_at` - Registration timestamp

### Wallets

- `id` - Primary key
- `user_id` - Foreign key to users
- `xrp_address` - XRP Ledger address
- `encrypted_secret` - Encrypted private key
- `balance` - Cached balance

### Transactions

- `id` - Primary key
- `sender_id` - Foreign key to users
- `recipient_address` - Destination address
- `amount` - XRP amount
- `tx_hash` - Transaction hash
- `status` - Transaction status

### User Settings

- `user_id` - Foreign key to users
- `price_alerts` - Boolean
- `transaction_notifications` - Boolean
- `currency_display` - Display currency
- `language` - Preferred language

## 🧪 Testing

### Run Tests

```bash
python run.py test
```

### Generate Test Data

```bash
# Create funded test wallet
python generate_test_wallet.py

# Test bot locally
python run.py
```

### Manual Testing

1. Start the bot: `python run.py`
2. Message your Telegram bot
3. Use `/start` to create wallet
4. Test transactions between wallets

## 🔍 Monitoring

### Health Checks

- **API Health**: GET `/api/v1/health`
- **Database**: Connection test
- **XRP Ledger**: Network connectivity
- **Redis**: Cache availability

### Logs

- **Application**: Structured JSON logging
- **Database**: SQLAlchemy query logging
- **HTTP**: Request/response logging
- **Errors**: Full stack traces

### Metrics

Tracked automatically:

- Request counts and response times
- Transaction success rates
- User registration metrics
- Error rates by endpoint

## 🛡️ Security Considerations

### Production Checklist

- [ ] Change all default API keys
- [ ] Set strong encryption keys
- [ ] Enable HTTPS only
- [ ] Configure rate limiting
- [ ] Set up monitoring
- [ ] Enable database backups
- [ ] Review logs regularly

### Sensitive Data

- Private keys: Encrypted at rest
- User data: Minimal collection
- API keys: Environment variables only
- Database: PostgreSQL with SSL

## 🔄 Migration Guide

### From TestNet to MainNet

1. **Update Configuration**

   ```python
   XRP_NETWORK = "mainnet"
   XRP_WEBSOCKET_URL = "wss://s1.ripple.com:443"
   XRP_JSON_RPC_URL = "https://s1.ripple.com:51234"
   # Remove XRP_FAUCET_URL
   ```

2. **Update Rate Limits**
   - Reduce transaction limits
   - Add wallet funding checks
   - Implement minimum balance requirements

3. **Enhanced Security**
   - Add 2FA for large transactions
   - Implement withdrawal limits
   - Add KYC integration if required

## 📁 Project Structure

``` text
xrp-telegram-bot/
├── backend/                    # FastAPI backend
│   ├── api/                   # API routes and middleware
│   ├── database/              # Database models and migrations
│   ├── services/              # Business logic services
│   └── utils/                 # Utility functions
├── bot/                       # Telegram bot
│   ├── handlers/              # Command handlers
│   ├── keyboards/             # Inline keyboards
│   └── utils/                 # Bot utilities
├── tests/                     # Test files
├── requirements.txt           # Python dependencies
├── run.py                    # Development runner
├── generate_test_wallet.py   # Test wallet generator
└── README.md                 # This file
```

## 📚 Resources

- **XRP Ledger Docs**: [https://xrpl.org/](https://xrpl.org/)
- **Telegram Bot API**: [https://core.telegram.org/bots/api](https://core.telegram.org/bots/api)
- **FastAPI Docs**: [https://fastapi.tiangolo.com/](https://fastapi.tiangolo.com/)
- **Render Docs**: [https://render.com/docs](https://render.com/docs)

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

MIT License - See LICENSE file for details.

## 🆘 Support

For issues and questions:

1. **📚 Check the [FAQ](FAQ.md)** - Comprehensive answers to common questions
2. **📧 Email Support:** support@fse-group3.co.za
3. **🐛 Report Issues:** [GitHub Issues](https://github.com/FSE-Class-Project/xrp-telegram-bot/issues)
4. **📊 Project Progress:** [Project Board](https://github.com/orgs/FSE-Class-Project/projects/1/views/1)

When reporting issues, please include:
- Description of the problem
- Steps to reproduce
- Error messages or logs
- Your environment details

---

---

**⚠️ Educational Use Only**: This bot is designed for learning XRP Ledger concepts in a safe TestNet environment. 

**Key Points:**
- 🚫 **TestNet only** - No real XRP or monetary value
- 🎓 **Educational purpose** - Transaction mechanics mirror real XRPL behavior  
- 🏗️ **Simplified security model** - Real-world implementations require additional security measures
- 📚 **Production differences** - Wallet management, funding, and security differ significantly on MainNet

See [FAQ.md](FAQ.md) for detailed comparisons between this educational bot and real-world XRP usage.
