import logging
import sys, os
import yaml
import netease
import telebot
from telebot import util

logger = logging.getLogger(__name__)

# Load config.yml
try:
    config = yaml.safe_load(open("config.yml"))
    log_level = config['general']['loglevel']
    token = config['general']['token']
    tmp_dir = config['netease']['tmpdir']
except Exception as e:
    logger.critical("config.yml is not valid!")
    logger.debug(e)
    sys.exit()
    
logging.basicConfig(level=getattr(logging, log_level.upper(), 10),
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Check if temporary directory is writable
try:
    if not os.path.exists(tmp_dir):
        os.makedirs(tmp_dir)
    if not os.path.exists(tmp_dir+'img/'):
        os.makedirs(tmp_dir+'img/')
except Exception as e:
    logger.critical("Temp directory not writable!!!")
    logger.debug(e)
    sys.exit()

# Sign into Telegram
if 'tgapi' in config['general']:
    from telebot import apihelper
    apihelper.API_URL = config['general']['tgapi']
bot = telebot.TeleBot(token, threaded=True)
if 'threads' in config['general']:
    bot.worker_pool = util.ThreadPool(num_threads=config['general']['threads'])


# Handle '/start' and '/help' command
@bot.message_handler(commands=['help', 'start'])
def send_welcome(message):
    bot.send_chat_action(message.chat.id, "typing")
    bot.reply_to(message, 
    """欢迎使用669点歌台!\n\n发送\n<b>点歌</b> 歌曲名称\n进行网易云搜索！\n\nPowered by <b><a href='https://dragon-fly.club/'>DragonFly Club</a></b>\n<a href='https://github.com/HolgerHuo/telegram-netease-bot/'>Source Code</a>
    """,
    parse_mode='HTML')

# Handle 点歌
@bot.message_handler(regexp="(点歌).*")
def handle_netease(message):
    keyword = message.text[2:]
    reply = bot.reply_to(message, text='正在搜索<b>'+ keyword+"</b>...", parse_mode='HTML')
    # Search NCMAPI for keywords
    try:
        song = netease.get_song_info(keyword.replace(" ", "+"))
    except Exception as e:
        bot.edit_message_text(chat_id=message.chat.id, message_id=reply.id, text='搜索\n<b>'+keyword+'</b>\n失败！请重试！', parse_mode='HTML')
        logger.error(keyword+" search cannot be performed!")
        logger.debug(e)
    else:
        # Return copyright content error
        if not song: 
            bot.edit_message_text(chat_id=message.chat.id, message_id=reply.id, text='<b>'+keyword+'</b>\n无法被找到或没有版权', parse_mode='HTML')
            logger.warning(keyword+" is not found!")
        else:  
            bot.edit_message_text(chat_id=message.chat.id, message_id=reply.id, text="正在缓存\n「<b>"+song.name+"</b>」\nby "+song.artist, parse_mode='HTML')
            # Caching Audio
            try:
                location = netease.cache_song(song.id, song.url, song.format, song.name, song.artist, song.album)
            except Exception as e:
                bot.edit_message_text(chat_id=message.chat.id, message_id=reply.id, text="「<b>"+song.name+"</b>」\n缓存失败！请重试", parse_mode='HTML')
                logger.error(song.name+" - "+song.artist+" could not be cached!")
                logger.debug(e)
            # Send audio
            else:
                bot.edit_message_text(chat_id=message.chat.id, message_id=reply.id, text="正在发送\n「<b>"+song.name+"</b>」\nby "+song.artist, parse_mode='HTML')
                audio = open(location.song, 'rb')
                if location.thumb:
                    thumb = open(location.thumb, 'rb')
                else:
                    thumb = None
                bot.send_chat_action(message.chat.id, "upload_audio")
                bot.send_audio(chat_id=message.chat.id, reply_to_message_id=message.message_id, audio=audio, caption="「<b>"+song.name+"</b>」\nby "+song.artist, parse_mode='HTML', title=song.name, performer=song.artist, thumb=thumb)
                audio.close()
                if thumb:
                    thumb.close()
                bot.delete_message(chat_id=message.chat.id, message_id=reply.id)
                logger.warning(song.name+' - '+song.artist+" has been sent to "+str(message.chat.id))

# Start polling
bot.infinity_polling()