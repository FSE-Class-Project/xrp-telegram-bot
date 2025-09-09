# XRP Telegram Bot

A Telegram bot for managing XRP (Ripple) cryptocurrency on the TestNet, built with Python, FastAPI, and the XRP Ledger.

## Features

- 🎯 **Wallet Management**: Create and manage XRP wallets via Telegram
- 💸 **Send & Receive XRP**: Transfer XRP between addresses with simple commands
- 💰 **Balance Tracking**: Real-time balance updates from the XRP Ledger
- 📊 **Price Information**: Current XRP market prices and 24h changes
- 📜 **Transaction History**: View your recent transactions
- 🔐 **Secure Storage**: Encrypted wallet secrets using Fernet encryption
- 🧪 **TestNet Integration**: Safe testing environment with free TestNet XRP

## Quick Start

### Prerequisites

- Python 3.8 or higher
- Telegram account
- Git

### 1. Clone the Repository

```bash
git clone https://github.com/ces0491/xrp-telegram-bot.git
cd xrp-telegram-bot
git checkout dev/ces
```

### 2. Set Up Python Environment

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On Mac/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Create Telegram Bot

1. Open Telegram and search for [@BotFather](https://t.me/BotFather)
2. Send `/newbot` command
3. Choose a name for your bot (e.g., "My XRP Wallet")
4. Choose a username (must end with 'bot', e.g., "my_xrp_wallet_bot")
5. Copy the bot token you receive

### 4. Configure Environment

```bash
# Copy environment template
cp .env.example .env

# Edit .env file and add your bot token
# Required: TELEGRAM_BOT_TOKEN=your_bot_token_here
```

### 5. Run the Bot

```bash
# Run both backend and bot (recommended for development)
python run.py

# Or run services separately:
python run.py backend  # Run only API backend
python run.py bot      # Run only Telegram bot
```

The script will:

- Initialize the database
- Generate encryption keys (if needed)
- Start the FastAPI backend on [http://localhost:8000](http://localhost:8000)
- Start the Telegram bot
- Show you all available endpoints and commands

### 6. Test Your Bot

1. Open Telegram and search for your bot username
2. Send `/start` to register and create a wallet
3. Your wallet will be automatically funded with TestNet XRP
4. Try commands like `/balance`, `/price`, `/help`

## Bot Commands

| Command | Description | Example |
|---------|-------------|---------|
| `/start` | Register and create XRP wallet | `/start` |
| `/help` | Show all available commands | `/help` |
| `/balance` | Check your XRP balance | `/balance` |
| `/send` | Send XRP to another address | `/send 10 rN7n7...` or `/send` |
| `/price` | View current XRP market price | `/price` |
| `/history` | View your transaction history | `/history` |
| `/profile` | View your profile and wallet info | `/profile` |
| `/settings` | Manage preferences (coming soon) | `/settings` |

## Project Structure

```text

xrp-telegram-bot/
├── backend/                 # FastAPI backend
│   ├── api/                # API routes and schemas
│   ├── database/           # Database models and connection
│   ├── services/           # Business logic services
│   │   ├── xrp_service.py    # XRP Ledger integration
│   │   ├── user_service.py   # User management
│   │   └── security_service.py
│   ├── utils/              # Utility functions
│   │   └── encryption.py     # Encryption service
│   ├── config.py           # Configuration management
│   └── main.py            # FastAPI application
├── bot/                    # Telegram bot
│   ├── handlers/          # Command handlers
│   │   ├── start.py        # Registration handlers
│   │   ├── wallet.py       # Wallet operations
│   │   ├── transaction.py  # Send XRP flow
│   │   └── price.py        # Price information
│   ├── keyboards/         # Telegram keyboards
│   ├── messages/          # Message templates
│   └── main.py           # Bot application
├── tests/                 # Test suite
├── .env.example          # Environment template
├── requirements.txt      # Python dependencies
├── run.py               # Development startup script
└── README.md           # This file

```

## API Documentation

Once the backend is running, visit [http://localhost:8000/docs](http://localhost:8000/docs) for interactive API documentation (Swagger UI).

### Key Endpoints

- `POST /api/v1/user/register` - Register new user
- `GET /api/v1/wallet/balance/{telegram_id}` - Get user balance
- `POST /api/v1/transaction/send` - Send XRP transaction
- `GET /api/v1/transaction/history/{telegram_id}` - Get transaction history
- `GET /api/v1/price/current` - Get current XRP price
- `GET /api/v1/health` - Health check

## Deployment

### Deploy to Render

1. Fork this repository
2. Create account at [render.com](https://render.com)
3. Create a new **Web Service** for the backend:
   - Connect your GitHub repository
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
   - Add environment variables from `.env`

4. Create a new **Background Worker** for the bot:
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `python -m bot.main`
   - Add environment variables including `API_URL` pointing to your backend service

### Deploy to Railway

1. Install Railway CLI: `npm install -g @railway/cli`
2. Login: `railway login`
3. Initialize: `railway init`
4. Deploy: `railway up`
5. Add environment variables in Railway dashboard

### Environment Variables

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `TELEGRAM_BOT_TOKEN` | Your bot token from BotFather | Yes | - |
| `DATABASE_URL` | Database connection string | No | `sqlite:///./xrp_bot.db` |
| `ENCRYPTION_KEY` | 32-byte Fernet key for encryption | No | Auto-generated |
| `JWT_SECRET` | Secret for JWT tokens | No | Auto-generated |
| `API_URL` | Backend API URL | No | `http://localhost:8000` |
| `DEBUG` | Enable debug mode | No | `True` |
| `ENVIRONMENT` | Environment name | No | `development` |

## Security Considerations

- **Custodial Wallet Model**: The bot manages wallets on behalf of users
- **Encrypted Storage**: All wallet secrets are encrypted using Fernet (AES-128)
- **TestNet Only**: Currently configured for TestNet only (no real money)
- **Rate Limiting**: Consider implementing rate limiting for production
- **HTTPS Only**: Use HTTPS in production with valid certificates

## Testing

```bash
# Run all tests
python run.py test

# Or use pytest directly
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=backend --cov=bot
```

## Troubleshooting

### Bot not responding

- Check bot token in `.env`
- Ensure backend is running (`http://localhost:8000/health`)
- Check logs for errors

### Database errors

- Delete `xrp_bot.db` and restart to recreate
- Check DATABASE_URL in `.env`

### XRP TestNet issues

- TestNet might be down - check [status](https://xrpl.org/public-servers.html)
- Faucet might be rate-limited - wait and retry

### Transaction failures

- Check wallet balance with `/balance`
- Verify recipient address format (starts with 'r')
- Ensure sufficient balance including fees

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Resources

- [XRP Ledger Documentation](https://xrpl.org)
- [Telegram Bot API](https://core.telegram.org/bots/api)
- [Python Telegram Bot](https://python-telegram-bot.org)
- [FastAPI Documentation](https://fastapi.tiangolo.com)
- [XRP TestNet Faucet](https://xrpl.org/xrp-testnet-faucet.html)

## License

MIT - see the [LICENSE](./LICENSE) file for details
