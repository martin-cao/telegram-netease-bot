import requests
import os.path
import yaml
import logging

logger = logging.getLogger(__name__)

# Construct Song Class
class Song(object):
    name = ""
    artist = ""
    id = 0
    url = ""
    format = ""
    album = ""

    def __init__(self, name, artist, id, format, album, url=None):
        self.name = name
        self.artist = artist
        self.id = id
        self.url = url
        self.format = format
        self.album = album

# Construct Location Class
class Location(object):
    song = ""
    thumb = ""

    def __init__(self, song, thumb):
        self.song = song
        self.thumb = thumb

# Load API config
config = yaml.safe_load(open("config.yml"))
api = config['netease']['neteaseapi']
userid = config['netease']['userid']
tmp_dir = config['netease']['tmpdir']

# Wrap RESTful API access
def request_api(url):
    cookies = {'MUSIC_U': userid}
    return requests.get(url, cookies=cookies)

# Search for songs
def get_song_info(keyword):
    songs = request_api(api+"/search?keywords="+keyword+"&type=1").json()["result"]["songs"]
    for song in songs:
        artists = []
        for artist in song['artists']:
            artists.append(artist['name'])
        if check_exist(str(song['id']), tmp_dir):
            return Song(song["name"], '&'.join(artists), song["id"], check_exist(str(song['id']), tmp_dir).split('.')[-1].lower(), song['album']['name'])
        availability = request_api(api+"/check/music?id="+str(song["id"])).json()["success"]
        if availability:
            song_meta = request_api(api+"/song/url?id="+str(song["id"])).json()["data"][0]
            if song_meta["url"] is not None and song_meta["freeTrialInfo"] is None:
                return Song(song["name"], '&'.join(artists), song["id"], song_meta["type"].lower(), song['album']['name'], song_meta["url"])
    return False

# Cache media
def cache_song(id, url, format, name, artist, album):
    location = tmp_dir+str(id)+'.'+format
    # delete low-res audio file
    if format == 'flac':
        if os.path.exists(tmp_dir+str(id)+'.mp3'):
            os.remove(tmp_dir+str(id)+'.mp3')
    try:
        img_location = cache_thumb(id)
    except Exception as e:
        img_location = None
        logger.error("Unable to cache thumbnail for "+name+' - '+artist)
        logger.debug(e)
    if not os.path.isfile(location):
        data = requests.get(url)
        with open(location, 'wb')as file:
            file.write(data.content)
        try:
            write_tags(location, format, artist, album, name, img_location)
        except Exception as e:
            logger.error("Could not write tag of "+name+" - "+artist)
            logger.debug(e)
        else:
            logger.warning("Tag "+name+" - "+artist+"has been written to "+location)
        logger.warning("Song "+str(id)+" has been cached")
    return Location(location, img_location)

# Write Audio Files tag
def write_tags(location, format, artist, album, name, thumb):
    if format == 'flac':
        from mutagen.flac import Picture, FLAC
        audio = FLAC(location)
        if thumb:
            image = Picture()
            image.type = 3
            image.desc = 'cover'
            if thumb.endswith('png'):
                image.mime = 'image/png'
            elif thumb.endswith('jpg'):
                image.mime = 'image/jpeg'
            with open(thumb, 'rb') as img:
                image.data = img.read()
            audio.add_picture(image)
        audio["TITLE"] = name
        audio['ARTIST'] = artist
        audio['ALBUM'] = album
        audio.save()
    if format == 'mp3':
        if thumb:
            from mutagen.mp3 import MP3
            from mutagen.id3 import ID3, APIC
            audio = MP3(location, ID3=ID3)   
            if thumb.endswith('png'):
                mime = 'image/png'
            elif thumb.endswith('jpg'):
                mime = 'image/jpeg' 
            audio.tags.add(
                APIC(
                    encoding=3, 
                    mime=mime, 
                    type=3, 
                    desc=u'Cover',
                    data=open(thumb).read()
                )
            )
            audio.save()
        from mutagen.easyid3 import EasyID3
        audio = EasyID3(location)
        audio["title"] = name
        audio['artist'] = artist
        audio['album'] = album
        audio.save()
        
# Cache thumbnails
def cache_thumb(id): 
    img_dir = tmp_dir+'img/'
    if not check_exist(str(id), img_dir):
        img_url = request_api(api+"/song/detail?ids="+str(id)).json()["songs"][0]['al']['picUrl']
        img = requests.get(img_url)
        img_ext = img_url.split('.')[-1].lower()
        location = img_dir+str(id) + '.' + img_ext
        with open(location, 'wb')as file:
            file.write(img.content)
        from pillow import Image
        MAX_SIZE = 320
        image = Image.open(location)
        original_size = max(image.size[0], image.size[1])
        if original_size >= MAX_SIZE:
            resized_file = open(location.split('.')[0]+'.jpg', "w")
            if (image.size[0] > image.size[1]):
                resized_width = MAX_SIZE
                resized_height = int(round((MAX_SIZE/float(image.size[0]))*image.size[1])) 
            else:
                resized_height = MAX_SIZE
                resized_width = int(round((MAX_SIZE/float(image.size[1]))*image.size[0]))
            image = image.resize((resized_width, resized_height), Image.ANTIALIAS)
            image.save(resized_file, 'JPEG')
            return img_dir+str(id) + '.jpg'
        return location
    else:
        return check_exist(str(id), img_dir)
        
# Check if directory has item(s)
def check_exist(item, dir):
    for item in os.listdir(dir):
        if os.path.splitext(item)[0] == id and os.path.isfile(os.path.join(dir, item)):
            return os.path.join(dir, item)
        else:
            return False