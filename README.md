# XRP Telegram Bot

A Telegram bot for XRP Ledger transactions, built with FastAPI,
Python-Telegram-Bot, and deployed on Render.

## 🌐 Live Deployment

- **API**: [https://xrp-bot-api.onrender.com](https://xrp-bot-api.onrender.com)
- **Network**: XRP TestNet
- **Status**: Production-ready POC
- **Test Coverage**:

## ✨ Features

### 🏦 Wallet Management (Hybrid Model)

- **Auto-Create Wallets** - Bot generates secure TestNet wallets for new users
- **Import Existing Wallets** - Advanced users can import their own TestNet
  wallets
- **MainNet Protection** - Multi-layer safety checks prevent accidental
  MainNet wallet imports
- **Balance Validation** - Automatic rejection of wallets with MainNet funds
  (>0.1 XRP)
- **Encrypted Storage** - All private keys encrypted with AES-256 before
  database storage

### 💸 Transaction Features

- **Send XRP** - Send TestNet XRP with multi-step confirmation flow
- **Beneficiary Management** - Save frequently used addresses with aliases
- **Amount Validation** - Smart validation preventing insufficient balance
  errors
- **Transaction Confirmation** - Review transaction details before sending
- **Real-time Updates** - Live balance updates after transactions

### 📊 Information & Monitoring

- **Live Balance Checking** - Real-time balance from XRP Ledger TestNet
- **Transaction History** - Complete paginated transaction tracking
- **Price Data** - Live XRP price from CoinGecko API
- **Account Details** - View wallet address, QR codes, and account info

### ⚙️ User Management

- **Profile Management** - Update user information and preferences
- **Settings Configuration** - Customize notifications and display
  preferences
- **Account Security** - View security settings and wallet status
- **Telegram Integration** - Seamless sync with Telegram user data

### 🛡️ Security & Production Features

- **Rate Limiting** - SlowAPI-based abuse prevention with configurable
  limits
- **Idempotency Protection** - Prevents duplicate transactions with request
  deduplication
- **Input Validation** - XRP address and amount validation
- **Error Handling** - Error recovery with user-friendly messages
- **Audit Logging** - Transaction and security event logging
- **Health Monitoring** - health checks and metrics

## 🏗️ Architecture

### Backend (FastAPI)

- **API Framework**: FastAPI with automatic OpenAPI documentation
- **Database**: PostgreSQL with SQLAlchemy ORM and Alembic migrations
- **XRP Integration**: Direct connection to XRP Ledger TestNet via xrpl-py
- **Caching**: Redis-based caching for user data and API responses
- **Security**: API key authentication, AES-256 encryption, rate limiting
- **Services Architecture**: Modular services (XRP, User, Cache, Telegram)
- **Monitoring**: Sentry integration, health checks, audit logging

### Frontend (Telegram Bot)

- **Framework**: python-telegram-bot v20.7+ with asyncio
- **Deployment**: Webhook-based for production, polling for development
- **UI Components**: Inline keyboards, HTML-formatted messages,
  conversation flows
- **State Management**: Context-based conversation handlers for complex
  workflows
- **Error Handling**: Error recovery with user-friendly feedback
- **Input Processing**: Multi-step forms, validation, and confirmation
  flows

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

| Command | Description | Features |
|---------|-------------|----------|
| `/start` | Registration and wallet setup | Auto-create or import wallet |
| `/balance` | Check XRP balance | Real-time balance from XRP Ledger |
| `/send` | Send XRP to another address | Multi-step confirmation flow |
| `/price` | View current XRP price | Live price from CoinGecko |
| `/history` | View transaction history | Paginated history, details |
| `/profile` | View and edit profile | Telegram sync, account management |
| `/settings` | Manage preferences | Notifications, display settings, security |
| `/help` | Show all commands | Interactive help system |

### 🎯 Interactive Features

- **Inline Keyboards** - Rich button-based navigation
- **Conversation Flows** - Multi-step transaction processes
- **Real-time Updates** - Live balance and price updates
- **Error Recovery** - Graceful handling with helpful messages
- **Beneficiary System** - Save and manage frequent recipients

### Example Usage

#### Send XRP

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

#### Cancel Transaction

```text
/cancel  (cancels any ongoing transaction setup)
```

## 🌐 API Endpoints

### Core API

- `GET /api/v1/health` - Health check and system status
- `POST /api/v1/user/register` - Register user with auto-created wallet
- `POST /api/v1/users/import-wallet` - Import TestNet wallet with safety checks
- `GET /api/v1/wallet/balance/{telegram_id}` - Get real-time balance
- `POST /api/v1/transaction/send` - Send XRP with validation
- `GET /api/v1/transaction/history/{telegram_id}` - Paginated transaction history
- `GET /api/v1/price/current` - Live XRP price data
- `PUT /api/v1/user/profile/{telegram_id}` - Update user profile
- `GET /api/v1/users/{telegram_id}/beneficiaries` - Manage saved addresses

### Documentation

- **Interactive Docs**: [https://xrp-bot-api.onrender.com/docs](https://xrp-bot-api.onrender.com/docs)
- **OpenAPI Schema**: [https://xrp-bot-api.onrender.com/openapi.json](https://xrp-bot-api.onrender.com/openapi.json)

## 🔐 Hybrid Wallet Model

### Wallet Options

#### Option 1: Auto-Created Wallets (Recommended)

- Bot automatically generates secure TestNet wallets
- Fully managed with encrypted storage
- Perfect for new users and testing

#### Option 2: Import Existing Wallets (Advanced)

- Import your own TestNet wallets via private key/seed phrase
- Advanced users who want to use existing wallets
- Full validation and safety checks

### MainNet Protection (Critical Safety Feature)

#### Multi-Layer Protection

1. **Balance Validation** - Checks both TestNet and MainNet balances
2. **Automatic Rejection** - Wallets with >0.1 XRP on MainNet are blocked
3. **User Warnings** - Multiple warning screens before import
4. **Audit Logging** - All import attempts logged for security

#### Safety Thresholds

- MainNet balance >0.1 XRP: **BLOCKED**
- MainNet balance >20 XRP: **BLOCKED** (high-value wallet protection)
- TestNet balance >10,000 XRP: **WARNING** (suspicious test balance)

#### Technical Implementation

```python
# Validate wallet safety before import
address, encrypted_secret, validation_info = await xrp_service.validate_testnet_wallet(private_key)

if not validation_info["is_testnet_safe"]:
    raise HTTPException(400, "Wallet blocked for safety")
```

### Security Features

- **AES-256 Encryption** - All private keys encrypted before storage
- **Network Validation** - Dual-network checks (TestNet + MainNet)
- **Input Validation** - Multiple private key format support
- **Message Deletion** - Private key messages deleted immediately
- **Error Recovery** - Clear feedback on validation failures

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

#### Web Service

```bash
pip install -r requirements.txt
```

#### Start Command

```bash
uvicorn backend.main:app --host 0.0.0.0 --port $PORT
```

#### Background Worker

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

### Application Security

- Private keys encrypted with Fernet
- API key authentication
- Input validation and sanitization
- SQL injection protection
- Rate limiting
- Logging

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

1. **📚 Check the [FAQ](FAQ.md)** - Answers to common questions
2. **📧 Email Support:** <support@fse-group3.co.za>
3. **🐛 Report Issues:** [GitHub Issues](https://github.com/FSE-Class-Project/xrp-telegram-bot/issues)
4. **📊 Project Progress:** [Project Board](https://github.com/orgs/FSE-Class-Project/projects/1/views/1)

When reporting issues, please include:

- Description of the problem
- Steps to reproduce
- Error messages or logs
- Your environment details

---

---

### Key Points

- 🚫 **TestNet only** - No real XRP or monetary value
- 🎓 **Test purposes** - Transaction mechanics mirror real XRPL
  behavior
- 🏗️ **Simplified security model** - Real-world implementations require
  additional security measures
- 📚 **Production differences** - Wallet management, funding, and security
  differ significantly on MainNet

See [FAQ.md](FAQ.md) for detailed comparisons between this test bot
and real-world XRP usage.
