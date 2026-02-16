# ================================================================
# 🎬 YouTube Shorts Generator
# ================================================================

import os, sys, math, time, io, textwrap, random, logging
import numpy as np
import requests
from gtts import gTTS
from pydub import AudioSegment
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
from moviepy.editor import VideoClip, VideoFileClip, AudioFileClip
from moviepy.config import change_settings

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')
log = logging.getLogger(__name__)

change_settings({'IMAGEMAGICK_BINARY': '/usr/bin/convert'})

W, H, FPS, SR = 1080, 1920, 30, 44100

def load_font(sz):
    for fp in ['/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
               '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf',
               '/usr/share/fonts/truetype/freefont/FreeSansBold.ttf']:
        try: return ImageFont.truetype(fp, sz)
        except: pass
    return ImageFont.load_default()

F_MAIN = load_font(58); F_LBL = load_font(44)
F_WM   = load_font(32); F_BIG = load_font(72); F_MED = load_font(44)

def textw(font, s):
    try: return int(font.getlength(s))
    except:
        try: return font.getsize(s)[0]
        except: return len(s)*32

# ── Audio ─────────────────────────────────────────────────────────
def np2seg(a):
    a = np.clip(a,-1,1)
    return AudioSegment((a*32767).astype(np.int16).tobytes(),
                        frame_rate=SR,sample_width=2,channels=1)

def gen_music(dur):
    t  = np.linspace(0,dur,int(dur*SR),dtype=np.float32)
    s  = sum(0.08*np.sin(2*np.pi*f*t)+0.025*np.sin(4*np.pi*f*t)
             for f in [130.8,164.8,196.0,261.6,329.6])
    s *= 0.75+0.25*np.sin(2*np.pi*0.07*t)
    fi = min(int(3*SR),len(t)//4)
    s[:fi]*=np.linspace(0,1,fi); s[-fi:]*=np.linspace(1,0,fi)
    mx = np.max(np.abs(s))
    return np2seg(s/mx*0.18 if mx>0 else s)

def gen_ding():
    t = np.linspace(0,0.5,int(0.5*SR),dtype=np.float32)
    return np2seg(np.sin(2*np.pi*880*t)*np.exp(-7*t)*0.45)

def get_word_timestamps(words, dur):
    lead  = 0.15
    avail = max(dur-lead-0.3, 0.5)
    def syl(w):
        w = w.lower().strip(".,!?;:'\"")
        return max(1,len([c for i,c in enumerate(w)
                          if c in 'aeiou' and(i==0 or w[i-1] not in 'aeiou')]))
    weights = [syl(w)+0.5 for w in words]
    tw_     = sum(weights)
    times,t = [],lead
    for wt in weights:
        dw = avail*(wt/tw_); times.append((t,t+dw)); t+=dw
    return times

# ── Facts + Audio ─────────────────────────────────────────────────
def fetch_and_generate(out_dir):
    os.makedirs(f'{out_dir}/audio',exist_ok=True)
    os.makedirs(f'{out_dir}/images',exist_ok=True)

    log.info('Fetching unique facts (50–60s)...')
    facts,apaths,durs,wtimes = [],[],[],[]
    seen,total,fails = set(),0.0,0

    while total<50 and fails<40:
        try:
            f = requests.get('https://uselessfacts.jsph.pl/random.json?language=en',
                             timeout=8).json().get('text','').strip()
            k = f.lower().replace(' ','')
            if not f or k in seen: time.sleep(0.2); continue
            seen.add(k)
        except: fails+=1; time.sleep(1); continue
        try:
            p = f'{out_dir}/audio/f{len(facts)}.mp3'
            gTTS(text=f,lang='en').save(p)
            seg = AudioSegment.from_mp3(p).fade_in(250).fade_out(400)
            seg += AudioSegment.silent(600)
            d = seg.duration_seconds
            if total+d>60: fails+=1; time.sleep(0.2); continue
            seg.export(p,format='mp3')
            facts.append(f); apaths.append(p); durs.append(d)
            wtimes.append(get_word_timestamps(f.split(),d))
            total+=d; fails=0
            log.info(f'  [{len(facts)}] {total:.1f}s  {f[:60]}')
            if total>=50: break
        except Exception as e: log.warning(f'Audio error: {e}'); fails+=1; time.sleep(0.5)

    fstarts = [sum(durs[:i]) for i in range(len(durs))]
    log.info(f'✅ {len(facts)} facts | {total:.1f}s')
    return facts,apaths,durs,wtimes,fstarts,total

def mix_audio(apaths,fstarts,total,out_dir):
    log.info('Mixing audio...')
    music = gen_music(total); ding = gen_ding()
    tts_t = AudioSegment.silent(int(total*1000))
    dng_t = AudioSegment.silent(int(total*1000))
    for p,s in zip(apaths,fstarts):
        tts_t = tts_t.overlay(AudioSegment.from_mp3(p),position=int(s*1000))
        dng_t = dng_t.overlay(ding,position=int(s*1000))
    mix_path = f'{out_dir}/audio/mix.mp3'
    ((music-14).overlay(tts_t).overlay(dng_t-3)).export(mix_path,format='mp3')
    log.info('✅ Audio mixed')
    return mix_path

# ── Backgrounds ───────────────────────────────────────────────────
def download_backgrounds(total,out_dir):
    log.info('Downloading backgrounds...')
    KEY    = os.environ.get('UNSPLASH_KEY','')
    needed = math.ceil(total/4)+3
    urls   = []
    for pg in range(1,8):
        try:
            rs = requests.get('https://api.unsplash.com/search/photos',
                headers={'Authorization':f'Client-ID {KEY}'},
                params={'query':'abstract colorful texture','orientation':'portrait',
                        'per_page':10,'page':pg,'content_filter':'high'},timeout=10)
            for p in rs.json().get('results',[]):
                urls.append(f"{p['urls']['raw']}&w={W}&h={H}&fit=crop&crop=entropy")
            if len(urls)>=needed: break
            time.sleep(0.3)
        except Exception as e: log.warning(f'Unsplash: {e}')

    ipaths,dcols = [],[]
    for i,url in enumerate(urls[:needed]):
        path = f'{out_dir}/images/bg{i}.jpg'
        try:
            img = Image.open(io.BytesIO(requests.get(url,timeout=15).content)).convert('RGB')
            rat = W/H
            if img.width/img.height>rat:
                nw=int(img.height*rat); img=img.crop(((img.width-nw)//2,0,(img.width+nw)//2,img.height))
            else:
                nh=int(img.width/rat); img=img.crop((0,(img.height-nh)//2,img.width,(img.height+nh)//2))
            img = img.resize((W,H),Image.LANCZOS)
            sm  = np.array(img.resize((50,50))).reshape(-1,3)
            dcols.append(tuple(int(x) for x in np.median(sm,axis=0)))
            img.filter(ImageFilter.GaussianBlur(1.5)).save(path,quality=92)
            ipaths.append(path)
        except Exception as e:
            log.warning(f'Image {i}: {e}'); dcols.append((20,20,60))

    if not ipaths:
        log.warning('No images — using gradients')
        rnd = random.Random(int(time.time()))
        for i in range(needed):
            path = f'{out_dir}/images/bg{i}.jpg'
            c1=(rnd.randint(20,100),rnd.randint(20,100),rnd.randint(100,200))
            c2=(rnd.randint(100,200),rnd.randint(20,100),rnd.randint(20,80))
            img=Image.new('RGB',(W,H)); dr2=ImageDraw.Draw(img)
            for y in range(H):
                dr2.line([0,y,W,y],fill=(c1[0]+int((c2[0]-c1[0])*y/H),
                                         c1[1]+int((c2[1]-c1[1])*y/H),
                                         c1[2]+int((c2[2]-c1[2])*y/H)))
            img.save(path); ipaths.append(path); dcols.append(c1)

    log.info(f'✅ {len(ipaths)} backgrounds')
    return ipaths,dcols

# ── Animated BG ───────────────────────────────────────────────────
def build_background(ipaths,dcols,total,out_dir):
    log.info('Building animated background...')

    def mk_bg(path,dur,dc):
        arr = np.array(Image.open(path).convert('RGB'))
        r,g,b = dc
        def fn(t):
            import math as _m
            sc   = 1.0+0.08*(t/dur)
            sw,sh= int(W/sc),int(H/sc)
            x0,y0= (W-sw)//2,(H-sh)//2
            crop = arr[y0:y0+sh,x0:x0+sw]
            fr   = np.array(Image.fromarray(crop).resize((W,H),Image.BILINEAR),dtype=np.float32)
            a_   = 0.06+0.04*_m.sin(t*0.5)
            fr[:,:,0]=np.clip(fr[:,:,0]*(1-a_)+r*a_,0,255)
            fr[:,:,1]=np.clip(fr[:,:,1]*(1-a_)+g*a_,0,255)
            fr[:,:,2]=np.clip(fr[:,:,2]*(1-a_)+b*a_,0,255)
            return fr.astype(np.uint8)
        return VideoClip(fn,duration=dur)

    def xfade(c1,c2,fade=0.5):
        d = c1.duration+c2.duration-fade
        def fn(t):
            if   t<c1.duration-fade: return c1.get_frame(t)
            elif t>=c1.duration:     return c2.get_frame(t-c1.duration+fade)
            else:
                a_=(t-(c1.duration-fade))/fade
                return (c1.get_frame(min(t,c1.duration-0.001))*(1-a_)+
                        c2.get_frame(t-(c1.duration-fade))*a_).astype(np.uint8)
        return VideoClip(fn,duration=d)

    bgs = [mk_bg(ipaths[i],4,dcols[i] if i<len(dcols) else (20,20,60))
           for i in range(len(ipaths))]
    bg  = bgs[0]
    for c in bgs[1:]: bg = xfade(bg,c,0.5)
    bg_path = f'{out_dir}/bg.mp4'
    bg.loop(duration=total).write_videofile(
        bg_path,fps=FPS,audio=False,verbose=False,logger=None)
    log.info('✅ Background done')
    return bg_path

# ── Rendering ─────────────────────────────────────────────────────
NP  = 28
_rng= np.random.RandomState(42)
PX  = _rng.uniform(0,W,NP); PY  = _rng.uniform(0,H,NP)
PVY = _rng.uniform(50,130,NP); PVX= _rng.uniform(-20,20,NP)
PSZ = _rng.randint(2,7,NP);  PPA = _rng.uniform(0,2*np.pi,NP)

def draw_particles(draw,t):
    for i in range(NP):
        py_=(PY[i]-PVY[i]*t)%H; px_=(PX[i]+PVX[i]*t)%W
        a_ =int(50+45*math.sin(t*2.5+float(PPA[i]))); sz_=int(PSZ[i])
        draw.ellipse([px_-sz_,py_-sz_,px_+sz_,py_+sz_],fill=(255,255,210,max(15,a_)))

def draw_progress(draw,t,total):
    p=min(t/total,1.0); x1,x2,by=50,W-50,H-50
    draw.rounded_rectangle([x1,by,x2,by+10],radius=5,fill=(255,255,255,50))
    fx=x1+int((x2-x1)*p)
    if fx>x1+5: draw.rounded_rectangle([x1,by,fx,by+10],radius=5,fill=(255,220,0,200))
    draw.ellipse([fx-7,by-3,fx+7,by+13],fill=(255,255,255,200))

def draw_dots(draw,t,facts,fstarts,durs):
    cur=-1
    for i in range(len(facts)):
        if fstarts[i]<=t<fstarts[i]+durs[i]: cur=i; break
    n=len(facts); sp=min(32,(W-120)//max(n,1))
    sx=W//2-n*sp//2; dy=H-85
    for i in range(n):
        dx=sx+i*sp+sp//2
        if i==cur: draw.ellipse([dx-9,dy-9,dx+9,dy+9],fill=(255,220,0,230))
        else:       draw.ellipse([dx-4,dy-4,dx+4,dy+4],fill=(255,255,255,90))

LW,LH,BP=25,78,28

def draw_karaoke(draw,t,idx,facts,fstarts,durs,word_times):
    import math as _m
    fact=facts[idx]; ft=t-fstarts[idx]
    words=fact.split(); wts=word_times[idx]
    cur_w=0
    for wi,(ws,we) in enumerate(wts):
        if ws<=ft<we: cur_w=wi; break
        if ft>=we: cur_w=wi
    lines=textwrap.wrap(fact,width=LW) or [fact]
    bw=W-80; bh=len(lines)*LH+BP*2
    bx1=(W-bw)//2; by1=H//2-bh//2; bx2=bx1+bw; by2=by1+bh; label_y=by1-64
    draw.rounded_rectangle([bx1,by1,bx2,by2],radius=28,fill=(10,10,30,195))
    draw.rounded_rectangle([bx1,by1,bx2,by2],radius=28,outline=(255,255,255,55),width=2)
    draw.text((W//2,label_y),f'✦  FACT  #{idx+1}  ✦',font=F_LBL,
              fill=(255,220,0,255),anchor='mm',stroke_width=2,stroke_fill=(0,0,0,200))
    gwi=0; yp=by1+BP+LH//2; sp_w=max(textw(F_MAIN,' '),12)
    for line in lines:
        lwords=line.split()
        if not lwords: yp+=LH; continue
        lnw=sum(textw(F_MAIN,w)+sp_w for w in lwords)-sp_w; xp=W//2-lnw//2
        for w in lwords:
            ww=textw(F_MAIN,w)
            col=(160,160,160,255) if gwi<cur_w else (255,220,0,255) if gwi==cur_w else (255,255,255,255)
            draw.text((xp,yp),w,font=F_MAIN,fill=col,anchor='lm',
                      stroke_width=2,stroke_fill=(0,0,0,180))
            xp+=ww+sp_w; gwi+=1
        yp+=LH

def draw_top(draw,t,total):
    sub_s=total/2; IDUR,SDUR=2.0,4.5
    if t<IDUR:
        a=int(255*(min(t/0.35,1.0) if t<IDUR-0.5 else (IDUR-t)/0.5)); a=max(0,min(255,a))
        draw.rectangle([0,0,W,230],fill=(0,0,0,int(a*0.85)))
        draw.text((W//2,78),'★  Did You Know?  ★',font=F_BIG,fill=(255,220,0,a),
                  anchor='mm',stroke_width=2,stroke_fill=(0,0,0,a))
        draw.text((W//2,172),'- Mind-Blowing Facts -',font=F_MED,fill=(255,255,255,a),anchor='mm')
    elif sub_s<=t<sub_s+SDUR:
        ft=t-sub_s; a=int(220*(min(ft/0.35,1.0) if ft<SDUR-0.5 else (SDUR-ft)/0.5)); a=max(0,min(220,a))
        bw,bh,by=740,100,65; bx=W//2-bw//2
        draw.rounded_rectangle([bx,by,bx+bw,by+bh],radius=20,fill=(200,0,0,int(a*0.9)))
        draw.rounded_rectangle([bx,by,bx+bw,by+bh],radius=20,outline=(255,255,255,80),width=2)
        draw.text((W//2,by+bh//2),'[+]  Follow for more facts!',font=F_MED,
                  fill=(255,255,255,a),anchor='mm',stroke_width=1,stroke_fill=(0,0,0,150))
    else:
        draw.text((W//2,52),'★ Did You Know? ★',font=F_WM,
                  fill=(255,255,255,140),anchor='mm',stroke_width=1,stroke_fill=(0,0,0,140))

def draw_outro(draw,t_in):
    DUR=2.5
    if t_in>=DUR: return
    a=int(255*(min(t_in/0.35,1.0) if t_in<DUR-0.5 else (DUR-t_in)/0.5)); a=max(0,min(255,a))
    draw.rectangle([0,H-290,W,H],fill=(0,0,0,int(a*0.88)))
    draw.text((W//2,H-210),">> That's a Wrap! <<",font=F_BIG,
              fill=(255,220,0,a),anchor='mm',stroke_width=2,stroke_fill=(0,0,0,a))
    draw.text((W//2,H-110),'Like  |  Follow  |  Share',font=F_MED,fill=(255,255,255,a),anchor='mm')

import math

def render_video(facts,durs,wtimes,fstarts,total,bg_path,mix_path,out_dir):
    log.info('Rendering final video...')
    bg_rd = VideoFileClip(bg_path)

    def render(t):
        bg  = bg_rd.get_frame(min(t,total-0.001)).copy()
        cv  = Image.new('RGBA',(W,H),(0,0,0,0)); dr=ImageDraw.Draw(cv)
        draw_particles(dr,t)
        for i in range(len(facts)):
            if fstarts[i]<=t<fstarts[i]+durs[i]:
                draw_karaoke(dr,t,i,facts,fstarts,durs,wtimes); break
        draw_top(dr,t,total); draw_dots(dr,t,facts,fstarts,durs)
        draw_progress(dr,t,total)
        if t>total-2.5: draw_outro(dr,t-(total-2.5))
        ov  = np.array(cv); alp=ov[:,:,3:4].astype(np.float32)/255.0
        return (bg.astype(np.float32)*(1-alp)+ov[:,:,:3].astype(np.float32)*alp).astype(np.uint8)

    out_path = f'{out_dir}/short.mp4'
    clip = VideoClip(render,duration=total).set_audio(AudioFileClip(mix_path))
    clip.write_videofile(out_path,fps=FPS,codec='libx264',
                         audio_codec='aac',bitrate='5000k',logger=None)
    log.info(f'✅ Video: {out_path}')
    return out_path

# ── Thumbnail ─────────────────────────────────────────────────────
def generate_thumbnail(facts,ipaths,out_dir):
    import glob
    def load_f(sz): return load_font(sz)

    bg_files = sorted(glob.glob(f'{out_dir}/images/bg*.jpg'))
    if not bg_files:
        bg_img = Image.new('RGB',(W,H))
        dr=ImageDraw.Draw(bg_img)
        for y in range(H): dr.line([0,y,W,y],fill=(int(10+60*y/H),0,int(80+120*y/H)))
    else:
        best,bsc=bg_files[0],0
        for p in bg_files[:6]:
            try:
                sm=np.array(Image.open(p).resize((40,40))); sat=np.std(sm.reshape(-1,3),axis=0).mean()
                if sat>bsc: bsc=sat; best=p
            except: pass
        bg_img=Image.open(best).convert('RGB').resize((W,H),Image.LANCZOS)

    bg_img=ImageEnhance.Color(bg_img).enhance(1.6)
    bg_img=ImageEnhance.Contrast(bg_img).enhance(1.2)
    bg_img=ImageEnhance.Brightness(bg_img).enhance(0.55)
    bg_img=bg_img.filter(ImageFilter.GaussianBlur(2))

    vig=Image.new('RGBA',(W,H),(0,0,0,0)); dv=ImageDraw.Draw(vig)
    for r in range(280,0,-1):
        alpha=int(200*(1-r/280)**1.8); pad=280-r
        dv.rounded_rectangle([pad,pad,W-pad,H-pad],radius=r*2,fill=(0,0,0,alpha))
    bg_rgba=Image.alpha_composite(bg_img.convert('RGBA'),vig)

    grad=Image.new('RGBA',(W,H),(0,0,0,0)); dg=ImageDraw.Draw(grad)
    for y in range(520):
        a=int(230*(1-y/520)**1.3); dg.line([0,y,W,y],fill=(5,0,25,a))
    for y in range(H-520,H):
        a=int(240*((y-(H-520))/520)**1.2); dg.line([0,y,W,y],fill=(5,0,20,a))
    bg_rgba=Image.alpha_composite(bg_rgba,grad)

    deco=Image.new('RGBA',(W,H),(0,0,0,0)); dd=ImageDraw.Draw(deco)
    def cbk(x,y,fx,fy,sz=90,col=(255,220,0,180)):
        sx=-1 if fx else 1; sy=-1 if fy else 1
        dd.line([x,y,x+sx*sz,y],fill=col,width=5); dd.line([x,y,x,y+sy*sz],fill=col,width=5)
        dd.ellipse([x-6,y-6,x+6,y+6],fill=col)
    cbk(55,55,False,False); cbk(W-55,55,True,False)
    cbk(55,H-55,False,True); cbk(W-55,H-55,True,True)
    rng2=random.Random(7)
    for _ in range(38):
        sx=rng2.randint(30,W-30); sy=rng2.randint(30,H-30)
        ss=rng2.randint(2,6); sa=rng2.randint(40,160)
        dd.ellipse([sx-ss,sy-ss,sx+ss,sy+ss],fill=(255,255,220,sa))
    bg_rgba=Image.alpha_composite(bg_rgba,deco)

    txt=Image.new('RGBA',(W,H),(0,0,0,0)); dt=ImageDraw.Draw(txt)
    F_BADGE=load_f(52); F_DYK1=load_f(128); F_DYK2=load_f(172)
    F_SUB=load_f(62); F_SMALL=load_f(44); F_FACT=load_f(42)

    def glow_text(draw,pos,text,font,fill,gcol,gr=28):
        for ox,oy,a in [(5,8,140),(3,5,100),(1,3,60)]:
            draw.text((pos[0]+ox,pos[1]+oy),text,font=font,fill=(0,0,0,a),
                      anchor='mm',stroke_width=5,stroke_fill=(0,0,0,a))
        for r in [gr,gr*2//3,gr//3]:
            for dx in range(-r,r+1,max(1,r//3)):
                for dy in range(-r,r+1,max(1,r//3)):
                    if abs(dx)+abs(dy)>r*1.4: continue
                    draw.text((pos[0]+dx,pos[1]+dy),text,font=font,fill=gcol+(22,),anchor='mm')
        draw.text(pos,text,font=font,fill=fill,anchor='mm',stroke_width=6,stroke_fill=(0,0,0,230))

    btxt='🧠  RANDOM FACTS'
    bw=textw(F_BADGE,btxt)+60; bh=80; bx=W//2-bw//2; by=115
    dt.rounded_rectangle([bx,by,bx+bw,by+bh],radius=40,fill=(255,220,0,235))
    dt.rounded_rectangle([bx,by,bx+bw,by+bh],radius=40,outline=(255,255,255,120),width=2)
    dt.text((W//2,by+bh//2),btxt,font=F_BADGE,fill=(10,10,30,255),anchor='mm')

    CY=H//2-80; ph_=420; pt1=CY-ph_//2-20; pt2=CY+ph_//2+20
    dt.rounded_rectangle([60,pt1,W-60,pt2],radius=36,fill=(0,0,0,160))
    dt.rounded_rectangle([60,pt1,W-60,pt2],radius=36,outline=(255,220,0,100),width=3)
    glow_text(dt,(W//2,CY-110),'DID  YOU',F_DYK1,(255,255,255,255),(120,180,255),gr=20)
    glow_text(dt,(W//2,CY+80),'KNOW?',F_DYK2,(255,225,0,255),(255,190,0),gr=35)
    for lw_,lop in [(8,200),(4,110),(2,55)]:
        dt.line([W//2-340,CY+195,W//2+340,CY+195],fill=(255,220,0,lop),width=lw_)
    n_f=len(facts)
    glow_text(dt,(W//2,CY+290),f'🔥  {n_f} Mind-Blowing Facts  🔥',F_SUB,(255,255,255,245),(180,220,255),gr=14)

    if facts:
        import textwrap as tw2
        prev=facts[0][:60]+('...' if len(facts[0])>60 else '')
        lns=tw2.wrap(prev,width=32)[:2]; pw=W-120; ph=len(lns)*64+38; px1=60; py1=H-380-ph
        dt.rounded_rectangle([px1,py1,px1+pw,py1+ph],radius=22,fill=(10,10,40,190))
        dt.rounded_rectangle([px1,py1,px1+pw,py1+ph],radius=22,outline=(255,220,0,90),width=2)
        dt.text((W//2,py1-36),'✦  FACT  #1  ✦',font=F_SMALL,fill=(255,220,0,200),
                anchor='mm',stroke_width=1,stroke_fill=(0,0,0,180))
        for li,ln in enumerate(lns):
            dt.text((W//2,py1+28+li*64),ln,font=F_FACT,fill=(255,255,255,230),
                    anchor='mm',stroke_width=1,stroke_fill=(0,0,0,160))

    cta_y=H-175
    dt.text((W//2,cta_y-28),'▶  WATCH NOW',font=F_SUB,fill=(255,220,0,235),
            anchor='mm',stroke_width=3,stroke_fill=(0,0,0,210))
    dt.text((W//2,cta_y+52),'👇  Swipe Up  👇',font=F_SMALL,fill=(255,255,255,180),
            anchor='mm',stroke_width=1,stroke_fill=(0,0,0,160))

    thumb=Image.alpha_composite(bg_rgba,txt).convert('RGB')
    thumb=thumb.filter(ImageFilter.UnsharpMask(radius=1.2,percent=140,threshold=2))
    thumb_path=f'{out_dir}/thumbnail.jpg'
    thumb.save(thumb_path,quality=97)
    log.info(f'✅ Thumbnail: {thumb_path}')
    return thumb_path

# ── Main entry point ──────────────────────────────────────────────
def generate(video_number=1):
    out_dir = f'output/video_{video_number}'
    os.makedirs(out_dir,exist_ok=True)

    facts,apaths,durs,wtimes,fstarts,total = fetch_and_generate(out_dir)
    mix_path  = mix_audio(apaths,fstarts,total,out_dir)
    ipaths,dc = download_backgrounds(total,out_dir)
    bg_path   = build_background(ipaths,dc,total,out_dir)
    vid_path  = render_video(facts,durs,wtimes,fstarts,total,bg_path,mix_path,out_dir)
    thumb     = generate_thumbnail(facts,ipaths,out_dir)

    return vid_path,thumb,facts
