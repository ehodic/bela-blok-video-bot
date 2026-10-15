#!/usr/bin/env python3
"""Bela Blok 150: 5 distinctive topics/day, Azure Gabrijela private preview.
Production has music and captions but no robotic speech unless properly licensed Azure voice is configured later.
Never publishes Azure F0 voice output commercially.
"""
import argparse
import sys
import datetime as dt
import html
import hashlib
import json
import math
import os
import random
import shutil
import subprocess
import tempfile
import urllib.request
import re
from xml.sax.saxutils import escape as xml_escape
import wave
from html.parser import HTMLParser
from pathlib import Path
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / 'assets'
VIDEOS = ROOT / 'public' / 'videos'
FACTS = json.loads((ROOT / 'facts.json').read_text(encoding='utf-8'))
W, H = 720, 1280
BG, WHITE, YELLOW, RED, BLUE = '#10121d', '#fff9f3', '#ffe45c', '#ff4960', '#59e2e7'
APP_URL = 'https://apps.apple.com/hr/app/bela-blok-belot-scorekeeper/id6809587024'
HASHTAGS = ['#bela', '#belot', '#BelaBlok', '#kartanje', '#drustveneigre']

FONTS = [
    '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
    '/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf',
]
FONT_BOLD = next((p for p in FONTS if Path(p).exists()), None)
FONT_REG = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'

def font(size, bold=True):
    path = FONT_BOLD if bold else FONT_REG
    return ImageFont.truetype(path, size) if path and Path(path).exists() else ImageFont.load_default()

def wrap(draw, content, f, width):
    chunks, line = [], ''
    for word in content.split():
        test = (line + ' ' + word).strip()
        if draw.textbbox((0, 0), test, font=f)[2] <= width:
            line = test
        else:
            if line: chunks.append(line)
            line = word
    if line: chunks.append(line)
    return chunks

def multiline(draw, content, y, size=53, color=WHITE, max_width=610, max_lines=5):
    f = font(size)
    lines = wrap(draw, content, f, max_width)
    while len(lines) > max_lines and size > 24:
        size -= 3
        f = font(size)
        lines = wrap(draw, content, f, max_width)
    dy = int(size * 1.27)
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=f)
        draw.text(((W - (bbox[2] - bbox[0])) / 2, y), line, fill=color, font=f, stroke_width=0)
        y += dy
    return y

def make_back(asset, flip=False):
    im = Image.open(ASSETS / asset).convert('RGB')
    im = ImageOps.fit(im, (W, H), Image.Resampling.LANCZOS)
    im = im.filter(ImageFilter.GaussianBlur(22)).convert('RGBA')
    overlay = Image.new('RGBA', (W, H), (13, 17, 30, 221))
    im = Image.alpha_composite(im, overlay).convert('RGB')
    d = ImageDraw.Draw(im)
    for i, sym in enumerate(['♠', '♥', '♦', '♣']):
        c = YELLOW if i % 2 == 0 else RED
        x = 25 + i * 175
        y = (850 if flip else 175) + (i % 2) * 115
        d.text((x, y), sym, font=font(74), fill=c, stroke_width=0)
    return im

def brand(draw):
    draw.rounded_rectangle((24, 26, W - 24, 118), radius=22, fill='#272b3b')
    draw.ellipse((46, 44, 108, 106), fill=YELLOW)
    draw.text((61, 52), '♣', font=font(40), fill=BG)
    draw.text((126, 55), 'BELA BLOK', font=font(38), fill=WHITE)
    draw.rounded_rectangle((538, 51, 682, 95), radius=20, fill=RED)
    draw.text((567, 62), 'IGRAJ', font=font(19), fill=WHITE)

def panel(draw, bounds=(36, 306, 684, 893), fill='#24293b'):
    draw.rounded_rectangle(bounds, radius=44, fill=fill, outline='#3b4458', width=3)

def screenshot(drawable, asset, x1, y1, x2, y2):
    img = Image.open(ASSETS / asset).convert('RGB')
    w, h = x2 - x1, y2 - y1
    drawable.rounded_rectangle((x1-13, y1-13, x2+13, y2+13), radius=33, fill=WHITE)
    new = ImageOps.contain(img, (w, h), Image.Resampling.LANCZOS)
    mask = Image.new('L', new.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, new.width, new.height), radius=17, fill=255)
    return new, mask, x1 + (w-new.width)//2, y1+(h-new.height)//2

def draw_scene(fact, kind, style):
    asset = fact['asset']
    base = make_back(asset, flip=style % 2 == 1)
    d = ImageDraw.Draw(base)
    brand(d)
    if kind == 'hook':
        d.rounded_rectangle((132, 161, 588, 230), radius=30, fill=YELLOW)
        tag = 'BRZI KVIZ O BELI' if fact['category']=='kviz' else ('JESI LI ZNAO?' if fact['category']=='zanimljivost' else 'PRAVILO BELE')
        multiline(d, tag, 180, 26, BG)
        panel(d, (27, 306, 693, 900))
        multiline(d, ['ČEKAJ!', 'BRZI KVIZ!', 'POGODI!','JESI ZNAO?'][style%4], 345, 57, RED)
        multiline(d, fact['question'], 486, 55, WHITE, 580, 5)
        d.rounded_rectangle((62, 967, 658, 1070), radius=25, fill=RED)
        multiline(d, 'POGODI PRIJE ODGOVORA', 998, 26, WHITE)
        # Animated 3-2-1 countdown is drawn later by FFmpeg.
    elif kind == 'answer':
        d.rounded_rectangle((188, 169, 533, 239), radius=28, fill=BLUE)
        multiline(d, 'TOČAN ODGOVOR', 188, 26, BG)
        panel(d, (27, 290, 693, 790))
        multiline(d, fact['answer'], 375, 63, YELLOW, 600, 4)
        multiline(d, fact['explanation'], 583, 34, WHITE, 588, 5)
        d.rounded_rectangle((75, 865, 648, 1192), radius=35, fill='#e5e9f2')
        im, mask, x, y = screenshot(d, asset, 245, 878, 480, 1155)
        base.paste(im, (x, y), mask)
    else:
        d.rounded_rectangle((43, 151, 677, 283), radius=25, fill=YELLOW)
        multiline(d, 'BELA BEZ PAPIRA!', 193, 43, BG)
        d.rounded_rectangle((150, 334, 568, 973), radius=47, fill='#fafafa')
        im, mask, x, y = screenshot(d, asset, 176, 351, 544, 957)
        base.paste(im, (x, y), mask)
        d.rounded_rectangle((54, 1005, 665, 1111), radius=29, fill=RED)
        multiline(d, 'PREUZMI BELA BLOK', 1035, 32, WHITE)
        multiline(d, 'App Store  •  link u profilu', 1150, 24, WHITE)
    return base

class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__(); self.skip=0; self.text=[]
    def handle_starttag(self, tag, attrs):
        if tag in ('script','style'): self.skip += 1
    def handle_endtag(self, tag):
        if tag in ('script','style') and self.skip: self.skip -= 1
    def handle_data(self, data):
        if not self.skip: self.text.append(data)

def source_check(facts, offline=False):
    """Check whether sources are reachable. This is NOT automatic factual verification."""
    unique = sorted({f['source'] for f in facts})
    availability = {}
    for source in unique:
        if offline:
            availability[source] = 'offline-test'
            continue
        try:
            req = urllib.request.Request(source, headers={'User-Agent':'Mozilla/5.0 (compatible; BelaBlokVideoBot/2.0)'})
            with urllib.request.urlopen(req, timeout=9) as res:
                page = res.read(450_000).decode('utf-8', 'ignore')
            parser=TextExtractor(); parser.feed(page)
            txt=html.unescape(' '.join(parser.text)).lower()
            availability[source] = 'online' if len(txt) > 300 else 'unavailable'
        except Exception:
            availability[source] = 'unavailable'
    return availability

def cmd(args):
    subprocess.run(args, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=90)

def duration(path):
    result = subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','default=noprint_wrappers=1:nokey=1',str(path)],text=True)
    return float(result)

def speak(sentence, dst, voice='music'):
    """Private Azure preview or no-voice production. No eSpeak robotic narration."""
    if voice == 'music':
        # Use a silent WAV backing track; the original synthetic music is added later.
        # Length roughly matches natural Croatian speech, with a short reading pause.
        secs = max(2.0, min(18.0, len(sentence.split()) / 2.65 + 0.65))
        cmd(['ffmpeg','-y','-loglevel','error','-f','lavfi','-i',
             'anullsrc=r=24000:cl=mono','-t',f'{secs:.2f}','-c:a','pcm_s16le',str(dst)])
        return
    if voice != 'azure':
        raise ValueError('Supported voices: music, azure')
    key=os.environ.get('AZURE_SPEECH_KEY', '').strip()
    region=os.environ.get('AZURE_SPEECH_REGION','westeurope').strip().lower()
    if not key: raise RuntimeError('AZURE_SPEECH_KEY secret missing (needed for private test).')
    if not re.fullmatch('[a-z][a-z0-9]{2,29}',region):
        raise RuntimeError('Invalid AZURE_SPEECH_REGION value.')
    ssml = ('<speak version="1.0" xml:lang="hr-HR" '
            'xmlns="http://www.w3.org/2001/10/synthesis">'
            '<voice name="hr-HR-GabrijelaNeural"><prosody rate="+7%">'
            + xml_escape(sentence) + '</prosody></voice></speak>')
    req=urllib.request.Request(
        f'https://{region}.tts.speech.microsoft.com/cognitiveservices/v1',
        data=ssml.encode('utf-8'),method='POST', headers={
            'Ocp-Apim-Subscription-Key':key,
            'Content-Type':'application/ssml+xml',
            'X-Microsoft-OutputFormat':'riff-24khz-16bit-mono-pcm',
            'User-Agent':'BelaBlokVoicePrivatePreview/1.0'})
    try:
        with urllib.request.urlopen(req,timeout=40) as resp:
            data=resp.read()
    except Exception as exc:
        raise RuntimeError('Azure Speech private test failed; check Azure resource and quota (no publication).') from None
    if len(data)<1000 or data[:4]!=b'RIFF':
        raise RuntimeError('Azure returned invalid WAV audio (no publication).')
    dst.write_bytes(data)

def make_music(path, secs):
    rate=22050
    import struct
    notes=[196.00, 261.63, 329.63, 261.63, 220.0, 293.66, 392.0, 293.66]
    with wave.open(str(path), 'wb') as out:
        out.setnchannels(1); out.setsampwidth(2); out.setframerate(rate)
        total = int(secs * rate)
        # Low-volume synthetic original music + swoosh every second beat.
        for start in range(0,total,rate):
            samples=[]
            for j in range(start, min(total,start+rate)):
                t=j/rate
                n=int(t*2.5)
                pos=(t*2.5) % 1
                hz=notes[n%len(notes)]
                tone=(math.sin(t*math.tau*hz)+.20*math.sin(t*math.tau*2*hz)) * .040 * math.exp(-pos*7)
                tick=.020*(1-((t*2)%1)/.06) if ((t*2)%1)<.06 else 0
                val=max(-1,min(1,tone+tick))
                samples.append(struct.pack('<h',int(32767*val)))
            out.writeframes(b''.join(samples))

def segment(imagefile, audiofile, movie, seconds, first=False, last=False):
    # Pan/zoom keeps slides in motion, with brief jump-cut transitions.
    frames=int(round(seconds*24))
    zoom=f"zoompan=z='min(zoom+0.00055,1.095)':x='iw/2-iw/zoom/2+2*sin(on/15)':y='ih/2-ih/zoom/2':d={frames}:s={W}x{H}:fps=24"
    vf=zoom+',format=yuv420p'
    if first: vf+=',fade=t=in:st=0:d=0.12'
    # Small animated pop stickers; no copyrighted animation assets.
    sticker_font = FONT_BOLD if FONT_BOLD else '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
    if first:
        vf += (f",drawtext=fontfile={sticker_font}:text='?!':fontcolor=0xffe45c:"
               "fontsize=77:x='525+13*sin(9*t)':y='332+17*cos(7*t)':"
               "enable='lt(t,3.6)'")
        for n, begin in [(3,0.0),(2,1.05),(1,2.10)]:
            vf += (f",drawtext=fontfile={sticker_font}:text={n}:fontcolor=0xffe45c:"
                   f"fontsize=69:x='(w-text_w)/2':y='1110+12*sin(t*8)':"
                   f"enable='between(t,{begin:.2f},{begin+1.0:.2f})'")
    if last:
        vf += (f",drawtext=fontfile={sticker_font}:text='>>':fontcolor=0xffe45c:"
               "fontsize=38:x='585+6*sin(10*t)':y=1057")
    if last: vf+=f',fade=t=out:st={max(0,seconds-.28):.2f}:d=0.26'
    af=f'apad,atrim=duration={seconds:.3f},afade=t=in:st=0:d=0.08,afade=t=out:st={max(0,seconds-.18):.2f}:d=0.17'
    cmd(['ffmpeg','-y','-loglevel','error','-loop','1','-i',str(imagefile),'-i',str(audiofile),
        '-vf',vf,'-af',af,'-t',f'{seconds:.3f}','-r','24','-c:v','libx264','-preset','veryfast','-crf','29',
        '-pix_fmt','yuv420p','-c:a','aac','-ar','22050','-b:a','84k','-shortest',str(movie)])

def produce(fact, out, voice, style):
    hook=fact['question']
    detail=f"{fact['answer']} {fact['explanation']}"
    cta='Kartaš belu? Bez zbrajanja i papira! Preuzmi Bela Blok na App Storeu.'
    with tempfile.TemporaryDirectory(prefix='bela-v2-') as tmp:
        d=Path(tmp)
        movies=[]
        for i, (kind, speech) in enumerate([('hook',hook),('answer',detail),('cta',cta)]):
            png=d/f'slide{i}.png'; draw_scene(fact,kind,style).save(png,optimize=True)
            wav=d/f'speech{i}.wav'; speak(speech,wav,voice)
            length=max([3.2,5.0,4.0][i],duration(wav)+.36)
            mp4=d/f'segment{i}.mp4'
            segment(png,wav,mp4,length,first=i==0,last=i==2)
            movies.append(mp4)
        listing=d/'concat.txt'
        listing.write_text(''.join("file '"+str(p)+"'\n" for p in movies))
        mixed=d/'voiced.mp4'
        cmd(['ffmpeg','-y','-loglevel','error','-f','concat','-safe','0','-i',str(listing),'-c','copy',str(mixed)])
        soundtrack=d/'sound.wav'; make_music(soundtrack,duration(mixed)+.2)
        cmd(['ffmpeg','-y','-loglevel','error','-i',str(mixed),'-i',str(soundtrack),'-filter_complex',
             '[0:a]volume=1.8[voice];[1:a]volume=0.30[music];[voice][music]amix=inputs=2:duration=first:dropout_transition=0[a]',
             '-map','0:v:0','-map','[a]','-c:v','copy','-c:a','aac','-b:a','96k','-movflags','+faststart',str(out)])

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--date',help='YYYY-MM-DD (Croatian local)')
    ap.add_argument('--count',type=int,default=5)
    ap.add_argument('--preview',action='store_true')
    ap.add_argument('--offline',action='store_true',help='Skip network source availability check')
    ap.add_argument('--validate-only', action='store_true', help='Check all 150 ideas without creating or publishing any videos')
    ap.add_argument('--voice', choices=['music','azure'], default='music')
    args=ap.parse_args()
    if args.voice == 'azure' and not args.preview and os.getenv('AZURE_SPEECH_PAID_TIER_CONFIRMED','').lower() != 'yes':
        raise RuntimeError('Azure voice for promotional publishing requires paid tier and explicit license confirmation. F0 is private preview only.')
    day=dt.date.fromisoformat(args.date) if args.date else dt.datetime.now(ZoneInfo('Europe/Zagreb')).date()
    # The JSON already contains an editorially balanced and reproducible 30-day order.
    # Start date October 16, 2026. Exactly 5 NEW topic IDs per day for 30 days.
    if len(FACTS) != 150:
        raise RuntimeError(f'Expected 150 editorial ideas, received {len(FACTS)}')
    ids = [f['id'] for f in FACTS]
    if len(set(ids)) != len(ids) or not all(f.get('editorial_reviewed') for f in FACTS):
        raise RuntimeError('Facts must have 150 unique reviewed topic IDs')
    for n, fact in enumerate(FACTS):
        expected = (dt.date(2026,10,16)+dt.timedelta(days=n//5)).isoformat()
        if fact.get('scheduled_date') != expected or int(fact.get('scheduled_slot', 0)) != n%5+1:
            raise RuntimeError(f'Bad editorial calendar at index {n}: {fact.get("id")}')
    if args.validate_only:
        print('VALID: 150 unique reviewed ideas, 30 days of 5 topics each, with sources.')
        print('START: 2026-10-16  END: 2026-11-14; October 16-31 = 80 videos.')
        return
    start_day = dt.date(2026,10,16)
    delta = (day - start_day).days
    if delta < 0:
        raise RuntimeError('New 150-topic calendar begins on 2026-10-16. Test with --date 2026-10-16.')
    offset = (delta * 5) % len(FACTS)
    selected = [dict(FACTS[(offset+i)%len(FACTS)]) for i in range(min(10,args.count))]
    for item in selected:
        if not item.get('source'):
            raise RuntimeError('Missing fact source for '+item.get('id','?'))
    status=source_check(selected,offline=args.offline)
    print('Source availability:',status)
    VIDEOS.mkdir(parents=True,exist_ok=True)
    for sub in VIDEOS.iterdir():
        if sub.is_dir():
            try:
                if (day-dt.date.fromisoformat(sub.name)).days>7: shutil.rmtree(sub)
            except ValueError: pass
    dest=VIDEOS/day.isoformat();dest.mkdir(parents=True,exist_ok=True)
    manifest=[]
    for i,fact in enumerate(selected):
        name=f'bela_{day:%Y%m%d}_{i+1:02}.mp4'
        out=dest/name
        produce(fact,out,args.voice,style=(offset+i)%4)
        # Do not spoil the quiz answer in the social-media caption.
        opener = fact['question'].strip()
        interaction = ('Kako se igra kod vas? Napiši u komentar!' if fact['category'] == 'rasprava'
                       else 'Pogodi prije odgovora i napiši rezultat u komentar!')
        hashtags = ' '.join(dict.fromkeys(fact.get('hashtags', HASHTAGS)))
        caption = (f"🃏 {opener} {interaction} "
                   f"📲 Bela Blok: digitalni zapis rezultata, statistika i revanš. "
                   f"Preuzmi besplatno za iPhone u App Storeu. {hashtags}")
        manifest.append({'name':name,'path':f'videos/{day.isoformat()}/{name}',
                         'caption':caption,'topic_id':fact['id'],
                         'source_url':fact['source'],'source_status':status[fact['source']],
                         'editorial_class':fact.get('editorial_class','standard'),
                         'editorial_reviewed':fact.get('editorial_reviewed',False),
                         'math_formula':fact.get('math_formula'),
                         'claim_kind':fact.get('claim_kind')})
        print(f'{i+1}/{len(selected)} {name} {out.stat().st_size/1024/1024:.2f}MB {duration(out):.1f}s voice={args.voice}')
    (ROOT/'manifest.json').write_text(json.dumps({'date':day.isoformat(),'videos':manifest},ensure_ascii=False,indent=2),encoding='utf-8')
    if args.preview and manifest:
        shutil.copyfile(dest/manifest[0]['name'],ROOT/'preview.mp4')
    print('Manifest ready:',ROOT/'manifest.json')

if __name__=='__main__': main()
