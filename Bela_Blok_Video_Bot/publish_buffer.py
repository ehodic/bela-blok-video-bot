#!/usr/bin/env python3
"""Schedule 5 generated public MP4s on connected Buffer Instagram and TikTok channels.

Everything stays in the user's Buffer account. Never place API keys in the repo.
"""
import argparse
import datetime as dt
import json
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parent
API='https://api.buffer.com'
TZ=ZoneInfo('Europe/Zagreb')
POSTING_TIMES=['09:15','11:45','14:15','17:30','20:15']
CREATE_MUTATION='''
mutation CreateBelaPost($input: CreatePostInput!) {
  createPost(input: $input) {
    ... on PostActionSuccess { post { id text dueAt } }
    ... on MutationError { message }
  }
}
'''

class BufferError(RuntimeError): pass

def api_call(query,variables=None):
    token=os.environ.get('BUFFER_API_KEY','').strip()
    if not token: raise BufferError('Nedostaje BUFFER_API_KEY (GitHub Actions secret).')
    body=json.dumps({'query':query,'variables':variables or {}},ensure_ascii=False).encode('utf-8')
    request=urllib.request.Request(API,data=body,headers={
        'Content-Type':'application/json','Authorization':f'Bearer {token}'
    },method='POST')
    try:
        with urllib.request.urlopen(request,timeout=25) as response:
            result=json.loads(response.read())
    except Exception as e:
        raise BufferError(f'Buffer zahtjev nije uspio: {e}') from e
    if result.get('errors'):
        raise BufferError('Buffer GraphQL greška: '+json.dumps(result['errors'],ensure_ascii=False))
    return result.get('data',{})


def list_channels():
    # Buffer account's organizations can include multiple workspaces.
    response=api_call('query { account { organizations { id name } } }')
    all_channels=[]
    for org in response['account']['organizations']:
        q='query($input: ChannelsInput!) { channels(input: $input) { id name service isDisconnected isLocked } }'
        data=api_call(q,{'input':{'organizationId':org['id']}})
        all_channels+=data['channels']
    return all_channels


def channels_for_bot():
    avail=list_channels()
    channels={}
    for platform in ('instagram','tiktok'):
        matches=[ch for ch in avail if ch['service'].lower()==platform and not ch['isDisconnected'] and not ch['isLocked']]
        # Optional explicit channel IDs disambiguate if several profiles are connected.
        pinned=os.environ.get('BUFFER_'+platform.upper()+'_CHANNEL_ID','').strip()
        if pinned: matches=[ch for ch in matches if ch['id']==pinned]
        if len(matches)!=1:
            summary=', '.join(f"{x['service']}:{x['name']} ({x['id']})" for x in avail)
            raise BufferError(f'Za {platform} očekujem točno jedan aktivan profil, pronađeno {len(matches)}. Profili: {summary}. Postavi BUFFER_{platform.upper()}_CHANNEL_ID ako treba.')
        channels[platform]=matches[0]
    return channels


def media_available(url):
    # HEAD can be blocked by storage hosts; try a 1-byte Range GET as a fallback.
    for method in ['HEAD','GET']:
        try:
            headers={'User-Agent':'BelaBlokVideoBot/1.0'}
            if method=='GET':headers['Range']='bytes=0-0'
            req=urllib.request.Request(url,headers=headers,method=method)
            with urllib.request.urlopen(req,timeout=20) as resp:
                content_type=resp.headers.get('Content-Type','')
                if resp.status in (200,206) and ('video/' in content_type or 'application/octet-stream' in content_type):
                    return True
        except Exception:
            time.sleep(2)
    return False


def post_payload(platform,channel_id,caption,url,when):
    metadata={'instagram':{'type':'reel','shouldShareToFeed':True}} if platform=='instagram' else {'tiktok':{'isAiGenerated':False}}
    return {
        'text':caption,
        'channelId':channel_id,
        'schedulingType':'automatic',
        'mode':'customScheduled',
        'dueAt':when.astimezone(dt.timezone.utc).isoformat().replace('+00:00','Z'),
        'metadata':metadata,
        'assets':[{'video':{'url':url,'metadata':{'thumbnailOffset':1500}}}]
    }


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--test-connection',action='store_true',help='Check Buffer profiles without publishing')
    parser.add_argument('--dry-run',action='store_true',help='Show planned schedule; no posts are created')
    options=parser.parse_args()
    channels=channels_for_bot()
    for key,ch in channels.items(): print('Povezano:',key,ch['name'],ch['id'])
    if options.test_connection: return
    base=os.environ.get('VIDEO_PUBLIC_BASE','').strip().rstrip('/')
    if not base.startswith('https://'):raise BufferError('Postavi GitHub Actions varijablu VIDEO_PUBLIC_BASE (https://tvoj-projekt.pages.dev).')
    manifest=json.loads((ROOT/'manifest.json').read_text(encoding='utf-8'))
    day=dt.date.fromisoformat(manifest['date'])
    localnow=dt.datetime.now(TZ)
    if not manifest.get('videos'): raise BufferError('Manifest nema videa.')
    state_file=ROOT/'state.json'
    state=json.loads(state_file.read_text(encoding='utf-8')) if state_file.exists() else {}
    for idx,vid in enumerate(manifest['videos']):
        if idx>=len(POSTING_TIMES):break
        hh,mm=map(int,POSTING_TIMES[idx].split(':'))
        when=dt.datetime(day.year,day.month,day.day,hh,mm,tzinfo=TZ)
        if when<=localnow+dt.timedelta(minutes=6):
            print('Preskačem termin koji je prošao:',when.isoformat());continue
        url=base+'/'+urllib.parse.quote(vid['path'],safe='/')
        if not options.dry_run and not media_available(url):
            raise BufferError('MP4 nije javno dostupan (provjeri Cloudflare Pages deployment): '+url)
        for platform,ch in channels.items():
            key=f'{day.isoformat()}::{platform}::{idx}'
            if key in state:
                print('Već zakazano:',key);continue
            if options.dry_run:
                print('TEST',platform,when.isoformat(),url)
                continue
            data=api_call(CREATE_MUTATION,{'input':post_payload(platform,ch['id'],vid['caption'],url,when)})
            status=data['createPost']
            if status.get('message'):
                raise BufferError(f"Buffer {platform} nije zakazao video {idx+1}: {status['message']}")
            post=status.get('post')
            if not post or not post.get('id'):raise BufferError(f'Neočekivan Buffer odgovor: {status}')
            state[key]={'postId':post['id'],'video':url,'when':when.isoformat()}
            state_file.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
            print('ZAKAZANO:',platform,'video',idx+1,when.isoformat(),'id',post['id'])
            time.sleep(.6)
    print('Gotovo.')

if __name__=='__main__':main()
