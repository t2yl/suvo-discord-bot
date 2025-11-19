# Suvo

---

## Setup Instructions
## 1. Clone the Repository
```bash
git clone https://github.com/yourusername/lumino.git
cd lumino
```

## 2. Install Dependencies
Make sure you have Python 3.10+ installed.
```python
pip install -r requirements.txt
```

## 3. Configure the Bot
Edit the `config.py` file and add your token and IDs:
```python
TOKEN = "your-bot-token"

# Customize these values as per your server setup
EMBED_COLOR = 0xf3a5b2
API_CATEGORY_ID = ...
DEV_SUPPORT_CATEGORY_ID = ...
# and so on...
```
> Make sure the bot has appropriate permissions in the server and all mentioned channel/role IDs are accurate.

## 4. Run the Bot
```python
python bot.py
```
The bot should be up and running.


## Notes
- Make sure the bot is added to your server with the `applications.commands` scope enabled.
- All slash commands are auto-synced to the `GUILD_ID` provided in the config.

## License
This project is open-source and available under the MIT License.

---

## Credits
Lumino is developed and maintained by [Suvo](https://github.com/t2yl).
Feel free to fork, contribute, or reach out if you'd like to collaborate.
Built with love, logic, and a lot of caffeine!
