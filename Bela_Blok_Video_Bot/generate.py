#!/usr/bin/env python3
"""Offline Bela Blok MP4 generator. No AI subscription and no external APIs."""
import argparse
import datetime as dt
import hashlib
import json
import math
import os
import random
import shutil
import subprocess
import tempfile
import wave
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

BASE = Path(__file__).resolve().parent
ASSETS = BASE / 'assets'
PUBLIC = BASE / 'public'
VIDEOS = PUBLIC / 'videos'
W, H = 720, 1280
RED = '#971b2c'
INK = '#25211e'
CREAM = '#f8f1e7'
GOLD = '#e5bd56'
APP_URL = 'https://apps.apple.com/hr/app/bela-blok-belot-scorekeeper/id6809587024'

SCENARIOS = [
    {'asset':'pocetna.png', 'hooks':['Bela bez papira i olovke?', 'Dosta ti je računanja na papiru?', 'Zapisuješ belu u bilježnicu?'], 'body':['Rezultati partije uvijek su pri ruci.', 'Napravi novu partiju u nekoliko dodira.', 'Digitalni blok koji ide s tobom.'], 'tag':'DIGITALNI BLOK'},
    {'asset':'unos.png', 'hooks':['Tri igrača? Nema problema.', 'Kako najbrže upisati rundu?', 'Tko je osvojio ostatak do 162?'], 'body':['Upiši bodove za dvoje. Treći se izračuna.', 'Unos bodova jednostavan je i brz.', 'Aplikacija automatski računa rezultat trećeg.'], 'tag':'UNOS RUNDE'},
    {'asset':'rezultati.png','hooks':['Tko je na redu za miješanje?', 'Kad krene prava bela...', 'Bodovi su napokon pregledni.'], 'body':['Bela Blok prati sljedećeg mješača.', 'Rezultati svih igrača na jednom ekranu.', 'Vidi koliko kome nedostaje do cilja.'], 'tag':'PREGLED REZULTATA'},
    {'asset':'povijest.png','hooks':['Revanš jednim dodirom!', 'A kad izgubiš za dlaku?', 'Pamti sve odigrane partije.'], 'body':['Nema ponovnog upisivanja igrača.', 'Odaberi Revanš i kreni ponovno.', 'Pogledaj pobjednike i konačne rezultate.'], 'tag':'POVIJEST IGRANJA'},
    {'asset':'statistika.png','hooks':['Tko je bio najbolji za stolom?', 'Brojke ne lažu!', 'Sjećaš se najbolje runde?'], 'body':['Pogledaj bodove, belu i prosjek po rundi.', 'Statistika pokazuje kako ste igrali.', 'Najbolja runda i ukupni bodovi na jednom mjestu.'], 'tag':'STATISTIKA PARTIJE'},
    {'asset':'izbornik.png','hooks':['Bela Blok ima i pravila igre!', 'Nisi siguran koliko vrijedi zvanje?', 'Bela na mobitelu, bez komplikacija.'], 'body':['Pravila igre uvijek su dostupna.', 'Pogledaj bodovanje i vrijednosti karata.', 'Rezultati, povijest i upute na jednom mjestu.'], 'tag':'SVE NA JEDNOM MJESTU'},
]


def font_paths():
    candidates = [
        ('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf','/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'),
        ('/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf','/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf'),
    ]
    for heavy, normal in candidates:
        if Path(heavy).exists() and Path(normal).exists():
            return heavy, normal
    return None, None
BOLD_PATH, REG_PATH = font_paths()

def get_font(size, bold=True):
    path = BOLD_PATH if bold else REG_PATH
    return ImageFont.truetype(path, size) if path else ImageFont.load_default()


def wrapped_lines(draw, content, font, limit):
    words = content.split()
    lines = []
    row = ''
    for word in words:
        trial = (row + ' ' + word).strip()
        if draw.textbbox((0,0),trial,font=font)[2] <= limit:
            row = trial
        else:
            if row:
                lines.append(row)
            row = word
    if row: lines.append(row)
    return lines


def centered_text(draw, content, y, max_width=610, size=58, color=INK, bold=True, spacing=16):
    font = get_font(size, bold)
    while size >= 26 and len(wrapped_lines(draw, content, font, max_width)) > 3:
        size -= 3
        font = get_font(size, bold)
    lines = wrapped_lines(draw, content, font, max_width)
    for line in lines:
        bb = draw.textbbox((0,0),line,font=font)
        draw.text(((W-(bb[2]-bb[0]))/2,y), line, font=font, fill=color)
        y += bb[3]-bb[1]+spacing
    return y


def ground(theme=CREAM):
    im = Image.new('RGB',(W,H),theme)
    d = ImageDraw.Draw(im)
    for idx in range(8):
        x = 80 + ((idx*157)%730)
        y = 70 + (idx*217)%1280
        d.ellipse((x-90,y-90,x+90,y+90),outline=('#e9ded0' if theme==CREAM else '#a93644'),width=2)
    return im


def brand(draw, dark=False):
    white = CREAM if dark else RED
    draw.rounded_rectangle((50,42,112,104),radius=18,fill=white)
    draw.text((67,43),'♣', font=get_font(42), fill=RED if dark else CREAM)
    draw.text((130,52),'BELA BLOK',font=get_font(31),fill=CREAM if dark else INK)


def cover(headline, tag, variant=0):
    im=ground(RED)
    draw=ImageDraw.Draw(im)
    brand(draw,True)
    draw.rounded_rectangle((65,283,655,331),radius=24,fill=GOLD)
    tfont=get_font(22)
    bb=draw.textbbox((0,0),tag,font=tfont)
    draw.text(((W-(bb[2]-bb[0]))/2,295),tag,font=tfont,fill=INK)
    centered_text(draw,headline,407,max_width=610,size=66,color=CREAM,spacing=22)
    draw.rounded_rectangle((62,800,658,965),radius=35,fill='#7d1222',outline='#c55b69',width=3)
    centered_text(draw,'BELA BL0K'.replace('0','O'),836,size=52,color=CREAM)
    centered_text(draw,'Digitalni blok za belu',909,size=25,color='#f1cbcc',bold=False)
    centered_text(draw,'Dostupno na App Storeu',1090,size=27,color=CREAM)
    return im


def screenshot_card(asset, label):
    im=ground()
    draw=ImageDraw.Draw(im)
    brand(draw)
    centered_text(draw,label,143,size=38,color=RED)
    photo=Image.open(ASSETS/asset).convert('RGB')
    # keep the full app screen inside a modern rounded phone mockup
    frame=(122,245,598,1134)
    draw.rounded_rectangle((frame[0]-12,frame[1]-12,frame[2]+12,frame[3]+12),radius=45,fill='#242b35')
    draw.rounded_rectangle(frame,radius=32,fill=CREAM)
    inside=(frame[0]+10,frame[1]+10,frame[2]-10,frame[3]-10)
    thumb=ImageOps.contain(photo,(inside[2]-inside[0],inside[3]-inside[1]),Image.Resampling.LANCZOS)
    x=inside[0]+((inside[2]-inside[0])-thumb.width)//2
    y=inside[1]+((inside[3]-inside[1])-thumb.height)//2
    mask=Image.new('L',thumb.size)
    ImageDraw.Draw(mask).rounded_rectangle((0,0,thumb.width,thumb.height),radius=23,fill=255)
    im.paste(thumb,(x,y),mask)
    centered_text(draw,'Jednostavno. Pregledno. Bez papira.',1188,size=22,color=INK)
    return im


def end_card(description):
    im=ground(RED)
    draw=ImageDraw.Draw(im)
    brand(draw, True)
    draw.rounded_rectangle((71,275,649,510),radius=42,fill=CREAM)
    centered_text(draw,'IGRAJ BEZ',322,size=57,color=RED)
    centered_text(draw,'PAPIRA!',406,size=67,color=RED)
    centered_text(draw,description,630,size=38,color=CREAM,max_width=600)
    draw.rounded_rectangle((125,925,595,1026),radius=28,fill=CREAM)
    centered_text(draw,'BELA BLOK',949,size=43,color=RED)
    centered_text(draw,'Preuzmi na App Storeu',1090,size=28,color=CREAM)
    return im


def make_audio(path,duration):
    # Quiet 100% original pluck, generated mathematically; no copyrighted tracks.
    rate=22050
    count=int(duration*rate)
    with wave.open(str(path),'wb') as wav:
        wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(rate)
        import struct
        for start in range(0,count,rate):
            batch=[]
            for j in range(start,min(count,start+rate)):
                t=j/rate
                beat=int(t*2.0)
                pos=(t*2.0)%1
                notes=[196,246.94,293.66,246.94,174.61,220,261.63,220]
                hz=notes[beat%len(notes)]
                envelope=math.exp(-pos*6.5)*0.13
                sound=(math.sin(2*math.pi*hz*t)+0.26*math.sin(2*math.pi*hz*2*t))*envelope
                batch.append(struct.pack('<h',int(max(-1,min(1,sound))*32767)))
            wav.writeframes(b''.join(batch))


def encode_card_triplet(cards,dst):
    with tempfile.TemporaryDirectory(prefix='bela-frames-') as td:
        td=Path(td)
        frames=[]
        for idx,card in enumerate(cards):
            frame=td/f'card{idx}.png';card.save(frame,optimize=True);frames.append(frame)
        audio=td/'sound.wav';make_audio(audio,10.8)
        ff=['ffmpeg','-y','-loglevel','error']
        for frame in frames:
            ff+=['-loop','1','-framerate','24','-t','3.6','-i',str(frame)]
        ff+=['-i',str(audio),'-filter_complex',
             '[0:v]fps=24,format=yuv420p,fade=t=in:st=0:d=0.30[v0];'
             '[1:v]fps=24,format=yuv420p[v1];'
             '[2:v]fps=24,format=yuv420p,fade=t=out:st=3.2:d=0.40[v2];'
             '[v0][v1][v2]concat=n=3:v=1:a=0[v]',
             '-map','[v]','-map','3:a:0','-c:v','libx264','-preset','veryfast','-crf','27',
             '-pix_fmt','yuv420p','-r','24','-c:a','aac','-b:a','96k','-shortest',
             '-movflags','+faststart',str(dst)]
        subprocess.run(ff,check=True)
        # Host rejects giant media; guard the Cloudflare Pages per-file limit.
        if dst.stat().st_size > 24*1024*1024:
            raise RuntimeError(f'MP4 is too big: {dst}')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--date',help='YYYY-MM-DD; default today Europe/Zagreb')
    parser.add_argument('--count',type=int,default=5)
    parser.add_argument('--preview',action='store_true',help='Save a single preview at preview.mp4')
    opt=parser.parse_args()
    from zoneinfo import ZoneInfo
    day=dt.date.fromisoformat(opt.date) if opt.date else dt.datetime.now(ZoneInfo('Europe/Zagreb')).date()
    VIDEOS.mkdir(parents=True,exist_ok=True)
    # Keep a 7-day window to ensure all queued Buffer videos remain fetchable.
    for folder in VIDEOS.iterdir():
        if folder.is_dir():
            try:
                if (day-dt.date.fromisoformat(folder.name)).days>7: shutil.rmtree(folder)
            except ValueError: pass
    out=VIDEOS/day.isoformat();out.mkdir(exist_ok=True)
    rng=random.Random(int(hashlib.sha256(day.isoformat().encode()).hexdigest()[:12],16))
    order=list(range(len(SCENARIOS)));rng.shuffle(order)
    manifest=[]
    for i in range(min(opt.count,10)):
        s=SCENARIOS[order[i%len(order)]]
        flavor=(day.toordinal()//6+i)%3
        filename=f'bela_{day.strftime("%Y%m%d")}_{i+1:02}.mp4'
        path=out/filename
        intro=cover(s['hooks'][flavor],s['tag'])
        feature=screenshot_card(s['asset'],s['tag'])
        end=end_card(s['body'][flavor])
        encode_card_triplet((intro,feature,end),path)
        caption=f"{s['hooks'][flavor]} {s['body'][flavor]} Bela Blok za iPhone: {APP_URL} #Bela #Belot #BelaBlok #Kartanje #DrustveneIgre"
        manifest.append({'name':filename,'path':str(path.relative_to(PUBLIC)).replace(os.sep,'/'),'caption':caption})
        print(f'{i+1}. {path.name} ({path.stat().st_size/1024/1024:.2f} MB)')
    (BASE/'manifest.json').write_text(json.dumps({'date':str(day),'videos':manifest},ensure_ascii=False,indent=2),encoding='utf-8')
    if opt.preview and manifest:
        shutil.copyfile(out/manifest[0]['name'],BASE/'preview.mp4')
        print('Preview:', BASE/'preview.mp4')
    print('Manifest:',BASE/'manifest.json')

if __name__=='__main__':main()
