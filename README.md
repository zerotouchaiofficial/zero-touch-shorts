# Zero Touch Shorts 🤖🎬

**Fully automated YouTube Shorts bot — zero human intervention required!**  

Zero Touch Shorts is a Python-powered bot that creates **cinematic, SEO-optimized YouTube Shorts** automatically, 10 times per day. It fetches random facts, generates speech, combines visuals, and uploads directly to your channel — all using **GitHub Actions**. Perfect for creators who want **high-quality content without lifting a finger**.  

---

## 🚀 Features

- Fetches **unique random facts** from a public API  
- Converts text to speech using **Google Text-to-Speech**  
- Downloads **high-quality backgrounds** from Unsplash  
- Generates **50–60 second vertical videos** with:  
  - 3-second **attention-grabbing hooks**  
  - **Karaoke-style word-by-word text** synced to audio  
  - **Animated Ken Burns backgrounds**  
  - **Cross-dissolve transitions** and floating particles  
  - Progress bar, intro/outro cards, and **subscribe popup**  
  - **Ambient background music**  
- Creates **custom thumbnails** automatically  
- Uploads videos via **YouTube Data API** with:  
  - **SEO-optimized curiosity-gap titles**  
  - **Keyword-rich descriptions**  
  - **30 rotating hashtags**  
  - **Pinned engagement comment**  
  - Playlist addition  
- Runs automatically **10 times per day** during peak hours (12 PM–11 PM EST)  
- Persistent `used_facts.json` ensures **no repeated facts**  

---

## 🛠 Tech Stack

- **Python** – Video creation and automation  
- **MoviePy & Pillow** – Video and image processing  
- **Google Text-to-Speech API** – Voiceover generation  
- **Unsplash API** – High-quality background images  
- **YouTube Data API v3** – Automatic upload and SEO optimization  
- **GitHub Actions** – Fully automated workflow  

---

## ⚡ Setup Guide

1. **Clone the repository**
   ```bash
   git clone https://github.com/zerotouchaiofficial/zero-touch-shorts.git
   cd zero-touch-shorts
