# XRP Telegram Bot

ECO5040S Financial Software Engineering Class Project

## Team Members

- Ces
- Joseph
- Sam
- Victor

## Project Overview

A Telegram bot integrated with the XRP Ledger TestNet that allows users to send and receive XRP cryptocurrency.

## Features

- User registration via Telegram
- XRP wallet generation
- Send/receive XRP on TestNet
- Check balances
- View price information
- Transaction history

## Setup Instructions

### Prerequisites

- Python 3.8+
- Telegram account
- Git

### Installation

1. Clone the repository
2. Create virtual environment: `python -m venv venv`
3. Activate: `.\venv\Scripts\Activate.ps1` (Windows)
4. Install dependencies: `pip install -r requirements.txt`
5. Copy `.env.example` to `.env` and update values
6. Initialize database: `python -c "from backend.database.connection import init_database; init_database()"`

### Running the Application

1. Start backend: `python -m backend.main`
2. Start bot: `python -m bot.main`

## Documentation

See `/docs` folder for detailed documentation.

## License

MIT - see the [LICENSE](./LICENSE) file for details
