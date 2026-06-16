# -*- coding: utf-8 -*-
"""ラジオコント漫才〜RAKOMAN〜 : ラジオコント・ラジオ漫才専用の音声投稿サイト"""
import os
import re
import sqlite3
import uuid
import datetime
import functools

from flask import (
    Flask, g, render_template, request, redirect, url_for,
    session, send_from_directory, abort, jsonify, flash
)
from werkzeug.security import generate_password_hash, check_password_hash

# ---------------------------------------------------------------- 設定
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("DATA_DIR", os.path.join(BASE_DIR, "data"))
UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")
DB_PATH = os.path.join(DATA_DIR, "rakoman.db")
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")  # この名前のユーザーが管理人

os.makedirs(UPLOAD_DIR, exist_ok=True)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "rakoman-dev-secret-change-me")
app.config["MAX_CONTENT_LENGTH"] = 80 * 1024 * 1024  # 80MB(音声+写真4枚)

# ---- 全テンプレート同梱(スマホだけでデプロイできる1ファイル版) ----
from jinja2 import DictLoader
TEMPLATES = {'404.html': '{% extends "base.html" %}\n'
             '{% block content %}\n'
             '<div class="empty" style="font-size:1.1rem">\n'
             '  <p style="font-size:3rem;margin:0">📻💦</p>\n'
             '  <p>ページが見つかりませんでした(非公開か、削除された可能性があります)</p>\n'
             '  <a class="btn btn-primary" href="{{ url_for(\'index\') }}">トップに戻る</a>\n'
             '</div>\n'
             '{% endblock %}\n',
 'base.html': '<!DOCTYPE html>\n'
              '<html lang="ja">\n'
              '<head>\n'
              '<meta charset="UTF-8">\n'
              '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
              '<title>{% block title %}ラジオコント漫才〜RAKOMAN〜{% endblock %}</title>\n'
              '<meta name="description" content="ラジオコント・ラジオ漫才専門の音声投稿サイト「RAKOMAN（ラコマン）」。コント・漫才・漫談・エピソードトークを聴いて、いいねやお気に入りで応援しよう。">\n'
              '<meta name="keywords" content="RAKOMAN,ラコマン,ラジオコント,ラジオ漫才,コント,漫才,漫談,エピソードトーク,音声投稿,お笑い">\n'
              '<meta property="og:title" content="ラジオコント漫才〜RAKOMAN〜">\n'
              '<meta property="og:description" content="ラジオコント・ラジオ漫才専門の音声投稿サイト。聴いて、笑って、応援しよう！">\n'
              '<meta property="og:type" content="website">\n'
              '<meta property="og:site_name" content="RAKOMAN">\n'
              '<meta name="twitter:card" content="summary">\n'
              '<!-- ▼▼▼ Google Search Console の確認タグはこの下に貼る ▼▼▼ -->\n'
              '<meta name="google-site-verification" content="qHToFhRL6ZYDZtT1VRfxmR0RDeBT6THWZ3uaKSkdA_s" />\n'
              '<!-- ▲▲▲ ここまで ▲▲▲ -->\n'
              '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
              '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
              '<link href="https://fonts.googleapis.com/css2?family=Zen+Maru+Gothic:wght@500;700;900&family=Baloo+2:wght@600;800&display=swap" rel="stylesheet">\n'
              '<style>\n'
              '{% raw %}/* ラジオコント漫才〜RAKOMAN〜 : 白基調ポップデザイン */\n'
              ':root{\n'
              '  --ink:#33303b;\n'
              '  --coral:#ff5470;\n'
              '  --sun:#ffc830;\n'
              '  --mint:#2ec4b6;\n'
              '  --sky:#5aa9ff;\n'
              '  --paper:#ffffff;\n'
              '  --soft:#fff6f0;\n'
              '  --line:#f0e4dc;\n'
              '  --radius:22px;\n'
              '  --shadow:0 6px 0 rgba(51,48,59,.08);\n'
              '}\n'
              '*{box-sizing:border-box}\n'
              'html{-webkit-text-size-adjust:100%}\n'
              'body{\n'
              '  margin:0;background:var(--paper);color:var(--ink);\n'
              '  font-family:"Zen Maru Gothic","Hiragino Maru Gothic ProN",sans-serif;\n'
              '  font-weight:500;line-height:1.7;\n'
              '  background-image:radial-gradient(#ffe9ef 1.5px, transparent 1.6px);\n'
              '  background-size:26px 26px;\n'
              '}\n'
              'a{color:inherit;text-decoration:none}\n'
              'img{max-width:100%}\n'
              '.container{max-width:980px;margin:0 auto;padding:16px}\n'
              '\n'
              '/* ---------- header ---------- */\n'
              '.site-header{\n'
              '  position:sticky;top:0;z-index:50;\n'
              '  display:flex;align-items:center;gap:12px;flex-wrap:wrap;\n'
              '  padding:10px 16px;background:rgba(255,255,255,.94);\n'
              '  border-bottom:3px solid var(--ink);backdrop-filter:blur(6px);\n'
              '}\n'
              '.logo{display:flex;align-items:center;gap:10px;font-weight:900}\n'
              '.logo-text{font-size:1.05rem;letter-spacing:.02em}\n'
              '.logo-text b{color:var(--coral);font-family:"Baloo 2","Zen Maru Gothic",sans-serif}\n'
              '.onair{\n'
              '  display:inline-flex;align-items:center;gap:6px;\n'
              '  font-family:"Baloo 2",sans-serif;font-weight:800;font-size:.72rem;letter-spacing:.12em;\n'
              '  color:#fff;background:var(--coral);border-radius:999px;padding:3px 10px;\n'
              '  box-shadow:0 3px 0 rgba(51,48,59,.18);\n'
              '}\n'
              '.onair .dot{width:8px;height:8px;border-radius:50%;background:var(--sun);animation:blink 1.4s infinite}\n'
              '@keyframes blink{0%,100%{opacity:1}50%{opacity:.25}}\n'
              '@media (prefers-reduced-motion:reduce){.onair .dot{animation:none}}\n'
              '.search{flex:1;min-width:180px}\n'
              '.search input{\n'
              '  width:100%;padding:10px 16px;border:2.5px solid var(--ink);border-radius:999px;\n'
              '  font:inherit;background:#fff;\n'
              '}\n'
              '.nav{display:flex;gap:8px;align-items:center}\n'
              '.mini-icon{width:22px;height:22px;border-radius:50%;object-fit:cover;vertical-align:-5px;margin-right:2px}\n'
              '\n'
              '/* ---------- buttons ---------- */\n'
              '.btn{\n'
              '  display:inline-flex;align-items:center;gap:6px;cursor:pointer;\n'
              '  border:2.5px solid var(--ink);border-radius:999px;\n'
              '  padding:8px 16px;font:inherit;font-weight:700;background:#fff;color:var(--ink);\n'
              '  box-shadow:0 4px 0 var(--ink);transition:transform .08s, box-shadow .08s;\n'
              '}\n'
              '.btn:active{transform:translateY(3px);box-shadow:0 1px 0 var(--ink)}\n'
              '.btn-primary{background:var(--coral);color:#fff}\n'
              '.btn-sun{background:var(--sun)}\n'
              '.btn-mint{background:var(--mint);color:#fff}\n'
              '.btn-ghost{box-shadow:none;border-color:transparent;background:transparent}\n'
              '.btn-ghost:hover{border-color:var(--line)}\n'
              '.btn-small{padding:4px 12px;font-size:.85rem;box-shadow:0 3px 0 var(--ink)}\n'
              '.btn-danger{background:#fff;color:var(--coral);border-color:var(--coral);box-shadow:0 3px 0 var(--coral)}\n'
              '\n'
              '/* ---------- flash ---------- */\n'
              '.flash-area{max-width:980px;margin:10px auto 0;padding:0 16px}\n'
              '.flash{\n'
              '  background:var(--sun);border:2.5px solid var(--ink);border-radius:14px;\n'
              '  padding:10px 16px;font-weight:700;margin-bottom:8px;box-shadow:var(--shadow);\n'
              '}\n'
              '\n'
              '/* ---------- hero / filters ---------- */\n'
              '.hero{margin:18px 0 8px}\n'
              '.hero h1{font-size:1.3rem;margin:0}\n'
              '.hero p{margin:4px 0 0;color:#7a7484;font-size:.92rem}\n'
              '.filters{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:14px 0 18px}\n'
              '.tab{\n'
              '  border:2.5px solid var(--ink);border-radius:999px;padding:5px 14px;font-weight:700;\n'
              '  background:#fff;font-size:.9rem;\n'
              '}\n'
              '.tab.active{background:var(--ink);color:#fff}\n'
              '.period-select{\n'
              '  margin-left:auto;border:2.5px solid var(--ink);border-radius:999px;\n'
              '  padding:6px 12px;font:inherit;font-weight:700;background:#fff;\n'
              '}\n'
              '\n'
              '/* ---------- post cards ---------- */\n'
              '\n'
              '\n'
              '\n'
              '\n'
              '\n'
              '\n'
              '\n'
              '\n'
              '\n'
              '.badge-private{background:var(--ink);color:#fff;border-radius:999px;padding:1px 9px;font-size:.72rem}\n'
              '\n'
              '/* ---------- post page ---------- */\n'
              '.post-box{\n'
              '  background:#fff;border:2.5px solid var(--ink);border-radius:var(--radius);\n'
              '  padding:18px;box-shadow:var(--shadow);margin-bottom:18px;\n'
              '}\n'
              '.post-title{font-size:1.4rem;font-weight:900;margin:0 0 6px}\n'
              '.user-chip{display:inline-flex;align-items:center;gap:8px;font-weight:700}\n'
              '.user-chip img,.avatar{width:34px;height:34px;border-radius:50%;object-fit:cover;border:2px solid var(--ink);background:var(--soft)}\n'
              '.avatar-placeholder{display:inline-flex;align-items:center;justify-content:center;font-size:1.1rem}\n'
              '\n'
              '.player{margin:14px 0;background:var(--soft);border:2.5px solid var(--ink);border-radius:16px;padding:12px}\n'
              '.player audio{width:100%}\n'
              '.speed-row{display:flex;gap:6px;flex-wrap:wrap;margin-top:8px;align-items:center}\n'
              '.speed-row .label{font-size:.82rem;font-weight:700;color:#7a7484}\n'
              '.speed{border:2px solid var(--ink);background:#fff;border-radius:999px;padding:3px 11px;font:inherit;font-size:.85rem;font-weight:700;cursor:pointer}\n'
              '.speed.active{background:var(--mint);color:#fff}\n'
              '\n'
              '.photo-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:8px;margin:12px 0}\n'
              '.photo-grid img{width:100%;aspect-ratio:1;object-fit:cover;border:2.5px solid var(--ink);border-radius:14px}\n'
              '\n'
              '.action-row{display:flex;gap:10px;flex-wrap:wrap;margin:14px 0;align-items:center}\n'
              '.count{font-family:"Baloo 2",sans-serif;font-weight:800}\n'
              '.tags{display:flex;gap:6px;flex-wrap:wrap;margin-top:8px}\n'
              '.tag{background:var(--sky);color:#fff;border:2px solid var(--ink);border-radius:999px;padding:2px 11px;font-size:.84rem;font-weight:700}\n'
              '.desc{white-space:pre-wrap;margin-top:10px}\n'
              '\n'
              '/* ---------- comments ---------- */\n'
              '.comment{display:flex;gap:10px;padding:12px 0;border-top:2px dashed var(--line)}\n'
              '.comment .body{flex:1}\n'
              '.comment .who{font-weight:700;font-size:.9rem}\n'
              '.comment .text{white-space:pre-wrap}\n'
              '.comment time{font-size:.75rem;color:#9b94a5}\n'
              '.note{color:var(--coral);font-weight:700;font-size:.85rem}\n'
              '\n'
              '/* ---------- forms ---------- */\n'
              '.form-box{max-width:520px;margin:24px auto;background:#fff;border:2.5px solid var(--ink);border-radius:var(--radius);padding:22px;box-shadow:var(--shadow)}\n'
              '.form-box h1{margin-top:0;font-size:1.25rem}\n'
              '.field{margin-bottom:14px}\n'
              '.field label{display:block;font-weight:700;margin-bottom:4px;font-size:.92rem}\n'
              '.field input[type=text],.field input[type=password],.field input[type=search],\n'
              '.field textarea,.field select{\n'
              '  width:100%;padding:10px 14px;border:2.5px solid var(--ink);border-radius:14px;font:inherit;background:#fff;\n'
              '}\n'
              '.field textarea{min-height:100px}\n'
              '.hint{font-size:.8rem;color:#9b94a5;margin-top:3px}\n'
              '.warn-box{background:#fff2f5;border:2.5px solid var(--coral);border-radius:14px;padding:10px 14px;font-size:.88rem;margin-bottom:14px}\n'
              '.file-input{font:inherit}\n'
              '\n'
              '/* ---------- profile ---------- */\n'
              '.profile-head{display:flex;align-items:center;gap:16px;margin:18px 0}\n'
              '.profile-head .avatar{width:84px;height:84px;font-size:2.2rem}\n'
              '.profile-head h1{margin:0;font-size:1.3rem}\n'
              '.tabs{display:flex;gap:8px;margin:14px 0;flex-wrap:wrap}\n'
              '\n'
              '/* ---------- playlist ---------- */\n'
              '.pl-item{display:flex;align-items:center;gap:12px;padding:12px;border:2.5px solid var(--ink);border-radius:16px;background:#fff;margin-bottom:10px;box-shadow:var(--shadow)}\n'
              '.pl-item .num{font-family:"Baloo 2",sans-serif;font-weight:800;color:var(--coral);width:26px;text-align:center}\n'
              '.inline-form{display:inline}\n'
              '\n'
              '.site-footer{margin-top:48px;padding:24px 16px;border-top:3px solid var(--ink);text-align:center;font-size:.85rem;background:#fff}\n'
              '.empty{padding:36px 12px;text-align:center;color:#9b94a5}\n'
              '\n'
              '\n'
              '@media (max-width:640px){\n'
              '  .site-header{padding:8px 10px}\n'
              '  .logo-text{font-size:.92rem}\n'
              '  .search{order:3;width:100%}\n'
              '  \n'
              '}\n'
              '{% endraw %}\n'
              '\n'
              '\n'
              '\n'
              '\n'
              '\n'
              '\n'
              '\n'
              '.card .body > *{margin-bottom:3px}\n'
              '\n'
              '\n'
              '\n'
              '\n'
              '\n'
              '\n'
              '\n'
              '\n'
              '\n'
              '\n'
              '\n'
              '\n'
              '\n'
              '\n'
              '.grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}\n'
              '.card{display:flex;flex-direction:column;background:#fff;border:2.5px solid var(--ink);border-radius:var(--radius);overflow:hidden;box-shadow:var(--shadow);cursor:pointer}\n'
              '.card .thumb{order:0;width:100%;aspect-ratio:16/10;flex:none;display:flex;align-items:center;justify-content:center;font-size:2.2rem;border-bottom:2.5px solid '
              'var(--ink);overflow:hidden;position:relative}\n'
              '.card .thumb img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}\n'
              '.card .body{order:1;width:100%;padding:8px 12px 10px;display:flex;flex-direction:column;gap:3px}\n'
              '.card .title{font-weight:900;font-size:.95rem;line-height:1.4}\n'
              '.card .meta{display:flex;align-items:center;gap:6px;font-size:.8rem;color:#7a7484}\n'
              '.card .stats{display:flex;gap:9px;font-size:.8rem;font-weight:700;flex-wrap:wrap}\n'
              '</style>\n'
              '</head>\n'
              '<body>\n'
              '<header class="site-header">\n'
              '  <a class="logo" href="{{ url_for(\'index\') }}">\n'
              '    <span class="onair"><span class="dot"></span>ON AIR</span>\n'
              '    <span class="logo-text">ラジオコント漫才<b>〜RAKOMAN〜</b></span>\n'
              '  </a>\n'
              '  <form class="search" action="{{ url_for(\'index\') }}" method="get">\n'
              '    <input type="search" name="q" value="{{ request.args.get(\'q\',\'\') }}" placeholder="🔍 タイトル・ユーザー・#ハッシュタグ">\n'
              '  </form>\n'
              '  <nav class="nav">\n'
              '    {% if me %}\n'
              '      <a class="btn btn-primary" href="{{ url_for(\'upload\') }}">🎙️ 投稿する</a>\n'
              '      <a class="btn btn-ghost" href="{{ url_for(\'profile\', username=me.username) }}">\n'
              '        {% if me.icon %}<img class="mini-icon" src="{{ url_for(\'media\', filename=me.icon) }}" alt="">{% else %}😀{% endif %}\n'
              '        マイページ</a>\n'
              '      <a class="btn btn-ghost" href="{{ url_for(\'logout\') }}">ログアウト</a>\n'
              '    {% else %}\n'
              '      <a class="btn btn-primary" href="{{ url_for(\'register\') }}">はじめる 🎉</a>\n'
              '      <a class="btn btn-ghost" href="{{ url_for(\'login\') }}">ログイン</a>\n'
              '    {% endif %}\n'
              '  </nav>\n'
              '</header>\n'
              '\n'
              '{% with messages = get_flashed_messages() %}\n'
              '  {% if messages %}\n'
              '    <div class="flash-area">\n'
              '      {% for m in messages %}<div class="flash">{{ m }}</div>{% endfor %}\n'
              '    </div>\n'
              '  {% endif %}\n'
              '{% endwith %}\n'
              '\n'
              '<main class="container">\n'
              '{% block content %}{% endblock %}\n'
              '</main>\n'
              '\n'
              '<footer class="site-footer">\n'
              '  <p>📻 ラジオコント漫才〜RAKOMAN〜 — ラジオコント・ラジオ漫才専門の音声投稿サイト</p>\n'
              '  <p class="note">※誹謗中傷、性的な内容はおやめください</p>\n'
              '</footer>\n'
              '<script>\n'
              '{% raw %}// RAKOMAN front script\n'
              'document.addEventListener("DOMContentLoaded", () => {\n'
              '\n'
              '  // ---- ジャンル選択ボタンのビジュアル ----\n'
              '  document.querySelectorAll(".genre-radio").forEach(radio => {\n'
              '    const span = radio.nextElementSibling;\n'
              '    const colors = {"コント":"#ff5470","漫才":"#5aa9ff","漫談":"#2ec4b6","エピソードトーク":"#ffc830","その他":"#7a7484"};\n'
              '    const update = () => {\n'
              '      document.querySelectorAll(".genre-radio").forEach(r => {\n'
              '        const s = r.nextElementSibling;\n'
              '        const c = colors[r.value] || "#7a7484";\n'
              '        s.style.background = r.checked ? c : "#fff";\n'
              '        s.style.color = r.checked ? "#fff" : "var(--ink)";\n'
              '        s.style.borderColor = r.checked ? "var(--ink)" : "var(--line)";\n'
              '      });\n'
              '    };\n'
              '    radio.addEventListener("change", update);\n'
              '    span.addEventListener("click", () => { radio.checked = true; radio.dispatchEvent(new Event("change")); });\n'
              '    update();\n'
              '  });\n'
              '\n'
              '  // ---- ジャンルバッジクリックで絞り込み ----\n'
              '  document.querySelectorAll(".genre-jump").forEach(el => {\n'
              '    el.addEventListener("click", e => {\n'
              '      e.preventDefault(); e.stopPropagation();\n'
              '      location.href = "/?genre=" + encodeURIComponent(el.dataset.genre);\n'
              '    });\n'
              '  });\n'
              '\n'
              '  // ---- ユーザーアイコン/名前クリックでプロフィールへ ----\n'
              '  document.querySelectorAll(".user-link").forEach(el => {\n'
              '    el.style.cursor = "pointer";\n'
              '    el.addEventListener("click", e => {\n'
              '      e.preventDefault();\n'
              '      e.stopPropagation();\n'
              '      location.href = "/user/" + encodeURIComponent(el.dataset.user);\n'
              '    });\n'
              '  });\n'
              '\n'
              '  // ---- いいね(何回でも押せる) ----\n'
              '  document.querySelectorAll("[data-like]").forEach(btn => {\n'
              '    btn.addEventListener("click", async () => {\n'
              '      const id = btn.dataset.like;\n'
              '      btn.classList.add("pop");\n'
              '      try {\n'
              '        const res = await fetch(`/post/${id}/like`, { method: "POST" });\n'
              '        const data = await res.json();\n'
              '        const c = btn.querySelector(".count");\n'
              '        if (c) c.textContent = data.likes;\n'
              '      } catch (e) {}\n'
              '      setTimeout(() => btn.classList.remove("pop"), 150);\n'
              '    });\n'
              '  });\n'
              '\n'
              '  // ---- お気に入り(1人1回・トグル) ----\n'
              '  document.querySelectorAll("[data-fav]").forEach(btn => {\n'
              '    btn.addEventListener("click", async () => {\n'
              '      const id = btn.dataset.fav;\n'
              '      try {\n'
              '        const res = await fetch(`/post/${id}/favorite`, { method: "POST" });\n'
              '        if (res.redirected) { location.href = res.url; return; }\n'
              '        const data = await res.json();\n'
              '        const c = btn.querySelector(".count");\n'
              '        if (c) c.textContent = data.count;\n'
              '        btn.classList.toggle("btn-sun", data.faved);\n'
              '        btn.querySelector(".fav-label").textContent =\n'
              '          data.faved ? "お気に入り済み" : "お気に入り";\n'
              '      } catch (e) {}\n'
              '    });\n'
              '  });\n'
              '\n'
              '  // ---- URLコピー(SNS共有用) ----\n'
              '  document.querySelectorAll("[data-copy-url]").forEach(btn => {\n'
              '    btn.addEventListener("click", async () => {\n'
              '      const url = btn.dataset.copyUrl || location.href;\n'
              '      try {\n'
              '        await navigator.clipboard.writeText(url);\n'
              '      } catch (e) {\n'
              '        const ta = document.createElement("textarea");\n'
              '        ta.value = url; document.body.appendChild(ta);\n'
              '        ta.select(); document.execCommand("copy"); ta.remove();\n'
              '      }\n'
              '      const old = btn.textContent;\n'
              '      btn.textContent = "コピーしました!✅";\n'
              '      setTimeout(() => (btn.textContent = old), 1600);\n'
              '    });\n'
              '  });\n'
              '\n'
              '  // ---- 倍速再生 ----\n'
              '  document.querySelectorAll(".player").forEach(player => {\n'
              '    const audio = player.querySelector("audio");\n'
              '    if (!audio) return;\n'
              '    player.querySelectorAll(".speed").forEach(b => {\n'
              '      b.addEventListener("click", () => {\n'
              '        audio.playbackRate = parseFloat(b.dataset.rate);\n'
              '        player.querySelectorAll(".speed").forEach(x => x.classList.remove("active"));\n'
              '        b.classList.add("active");\n'
              '      });\n'
              '    });\n'
              '  });\n'
              '\n'
              '  // ---- バックグラウンド再生(Media Session API) ----\n'
              '  // 画面を閉じても・他のアプリを開いても、ロック画面/通知から操作できるようにする\n'
              '  const mainAudio = document.querySelector("audio[data-title]");\n'
              '  if (mainAudio && "mediaSession" in navigator) {\n'
              '    const setMeta = () => {\n'
              '      const artwork = mainAudio.dataset.artwork\n'
              '        ? [{ src: mainAudio.dataset.artwork, sizes: "512x512", type: "image/png" }]\n'
              '        : [];\n'
              '      navigator.mediaSession.metadata = new MediaMetadata({\n'
              '        title: mainAudio.dataset.title,\n'
              '        artist: mainAudio.dataset.artist || "RAKOMAN",\n'
              '        album: "ラジオコント漫才〜RAKOMAN〜",\n'
              '        artwork\n'
              '      });\n'
              '    };\n'
              '    mainAudio.addEventListener("play", () => {\n'
              '      setMeta();\n'
              '      navigator.mediaSession.playbackState = "playing";\n'
              '    });\n'
              '    mainAudio.addEventListener("pause", () => {\n'
              '      navigator.mediaSession.playbackState = "paused";\n'
              '    });\n'
              '    navigator.mediaSession.setActionHandler("play", () => mainAudio.play());\n'
              '    navigator.mediaSession.setActionHandler("pause", () => mainAudio.pause());\n'
              '    navigator.mediaSession.setActionHandler("seekbackward", () => {\n'
              '      mainAudio.currentTime = Math.max(0, mainAudio.currentTime - 10);\n'
              '    });\n'
              '    navigator.mediaSession.setActionHandler("seekforward", () => {\n'
              '      mainAudio.currentTime = Math.min(mainAudio.duration || 0, mainAudio.currentTime + 10);\n'
              '    });\n'
              '  }\n'
              '\n'
              '  // ---- 連続再生:終わったら一覧の順で次の投稿を自動再生 ----\n'
              '  if (mainAudio) {\n'
              '    let nextEndpoint = mainAudio.dataset.next;\n'
              '    mainAudio.addEventListener("ended", async () => {\n'
              '      if (!nextEndpoint) return;\n'
              '      try {\n'
              '        const res = await fetch(nextEndpoint);\n'
              '        const d = await res.json();\n'
              '        if (d.end) return;\n'
              '        mainAudio.src = d.audio;\n'
              '        mainAudio.dataset.title = d.title;\n'
              '        mainAudio.dataset.artist = d.artist;\n'
              '        if (d.artwork) mainAudio.dataset.artwork = d.artwork; else delete mainAudio.dataset.artwork;\n'
              '        nextEndpoint = d.next_endpoint;\n'
              '        const banner = document.getElementById("next-banner");\n'
              '        const link = document.getElementById("next-link");\n'
              '        if (banner && link) {\n'
              '          link.textContent = `${d.title}(${d.artist})`;\n'
              '          link.href = d.post_url;\n'
              '          banner.hidden = false;\n'
              '        }\n'
              '        mainAudio.play();  // playイベントでMedia Sessionの曲情報も更新される\n'
              '      } catch (e) {}\n'
              '    });\n'
              '  }\n'
              '});\n'
              '{% endraw %}\n'
              '</script>\n'
              '</body>\n'
              '</html>\n',
 'edit_post.html': '{% extends "base.html" %}\n'
                   '{% block title %}投稿を編集 | RAKOMAN{% endblock %}\n'
                   '{% block content %}\n'
                   '<div class="form-box">\n'
                   '  <h1 style="margin-top:0;font-size:1.2rem">✏️ 投稿を編集</h1>\n'
                   '  <form method="post" enctype="multipart/form-data">\n'
                   '    <div class="field">\n'
                   '      <label>🎭 ジャンル(必須)</label>\n'
                   '      <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:4px">\n'
                   '        {% for g in GENRES %}\n'
                   '        <label style="cursor:pointer">\n'
                   '          <input type="radio" name="genre" value="{{ g }}" {{ \'checked\' if post.genre == g }} required style="display:none" class="genre-radio">\n'
                   '          <span class="genre-badge" style="background:{{ GENRE_COLOR.get(g,\'#fff\') if post.genre==g else \'#fff\' }};color:{{ \'#fff\' if post.genre==g else \'var(--ink)\' '
                   '}};border-color:{{ \'var(--ink)\' if post.genre==g else \'var(--line)\' }}">{{ g }}</span>\n'
                   '        </label>\n'
                   '        {% endfor %}\n'
                   '      </div>\n'
                   '    </div>\n'
                   '    <div class="field">\n'
                   '      <label for="title">タイトル(必須)</label>\n'
                   '      <input type="text" id="title" name="title" maxlength="60" required value="{{ post.title }}">\n'
                   '    </div>\n'
                   '    <div class="field">\n'
                   '      <label for="description">説明</label>\n'
                   '      <textarea id="description" name="description">{{ post.description or "" }}</textarea>\n'
                   '    </div>\n'
                   '    <div class="field">\n'
                   '      <label for="hashtags">ハッシュタグ</label>\n'
                   '      <input type="text" id="hashtags" name="hashtags"\n'
                   '             placeholder="例:#コント #漫才 #エピソードトーク"\n'
                   '             value="{{ post.hashtags or "" }}">\n'
                   '      <p class="hint">スペースか「,」で区切って入力</p>\n'
                   '    </div>\n'
                   '    <div class="field">\n'
                   '      <label>🎙️ 音声ファイルを差し替え(任意)</label>\n'
                   '      <audio controls src="{{ url_for(\'media\', filename=post.audio) }}" style="width:100%;margin:6px 0"></audio>\n'
                   '      <input class="file-input" type="file" name="audio" accept="audio/*,.m4a,.mp3,.wav,.aac">\n'
                   '      <p class="hint">選ばない場合は現在の音声のままです</p>\n'
                   '    </div>\n'
                   '    {% if images %}\n'
                   '    <div class="field">\n'
                   '      <label>📸 現在の写真(×で削除)</label>\n'
                   '      <div class="photo-grid">\n'
                   '        {% for img in images %}\n'
                   '        <div style="position:relative">\n'
                   '          <img src="{{ url_for(\'media\', filename=img.filename) }}"\n'
                   '               style="width:100%;aspect-ratio:1;object-fit:cover;border:2.5px solid var(--ink);border-radius:14px">\n'
                   '          <label style="position:absolute;top:4px;right:4px;background:var(--coral);color:#fff;border-radius:999px;padding:2px '
                   '8px;font-size:.8rem;font-weight:700;cursor:pointer">\n'
                   '            <input type="checkbox" name="delete_image" value="{{ img.id }}" style="display:none">❌</label>\n'
                   '        </div>\n'
                   '        {% endfor %}\n'
                   '      </div>\n'
                   '      <p class="hint">❌をタップしてチェックを入れると「更新する」時に削除されます</p>\n'
                   '    </div>\n'
                   '    {% endif %}\n'
                   '    {% if images|length < 4 %}\n'
                   '    <div class="field">\n'
                   '      <label>📸 写真を追加(合計4枚まで・あと{{ 4 - images|length }}枚)</label>\n'
                   '      <input class="file-input" type="file" name="new_images" accept="image/*" multiple>\n'
                   '    </div>\n'
                   '    {% endif %}\n'
                   '    <div style="display:flex;gap:10px;flex-wrap:wrap;margin-top:6px">\n'
                   '      <button class="btn btn-primary">更新する ✏️</button>\n'
                   '      <a class="btn btn-ghost" href="{{ url_for(\'post_page\', post_id=post.id) }}">キャンセル</a>\n'
                   '    </div>\n'
                   '  </form>\n'
                   '</div>\n'
                   '{% endblock %}',
 'index.html': '{% extends "base.html" %}\n'
               '{% block content %}\n'
               '<div class="hero">\n'
               '  <h1>📻 笑える"音"だけのステージ</h1>\n'
               '  <p>ラジオコント・ラジオ漫才専門の投稿サイト。聴いて、笑って、👍と🤩で応援しよう!</p>\n'
               '</div>\n'
               '\n'
               '{% if q %}<p>「<b>{{ q }}</b>」の検索結果({{ posts|length }}件)</p>{% endif %}\n'
               '\n'
               '<div style="display:flex;gap:8px;flex-wrap:wrap;margin:10px 0 6px">\n'
               '  <a href="{{ url_for(\'index\', sort=sort, period=period, q=q) }}"\n'
               '     style="display:inline-block;border:2.5px solid var(--ink);border-radius:999px;padding:5px 14px;font-weight:700;font-size:.88rem;text-decoration:none;background:{{ \'var(--ink)\' '
               'if not genre else \'#fff\' }};color:{{ \'#fff\' if not genre else \'var(--ink)\' }}">すべて</a>\n'
               '  {% for g in GENRES %}\n'
               '  <a href="{{ url_for(\'index\', sort=sort, period=period, q=q, genre=g) }}"\n'
               '     style="display:inline-block;border:2.5px solid var(--ink);border-radius:999px;padding:5px 14px;font-weight:700;font-size:.88rem;text-decoration:none;background:{{ GENRE_COLOR[g] '
               'if genre==g else \'#fff\' }};color:{{ \'#fff\' if genre==g else \'var(--ink)\' }}">{{ g }}</a>\n'
               '  {% endfor %}\n'
               '</div>\n'
               '\n'
               '<div class="filters">\n'
               '  {% for key, label in SORTS %}\n'
               '    <button class="tab {{ \'active\' if sort == key }}" onclick="location.href=\'{{ url_for(\'index\', sort=key, period=period, q=q, genre=genre) }}\'">{{ label }}</button>\n'
               '  {% endfor %}\n'
               '  <select class="period-select" onchange="location.href=this.value">\n'
               '    {% for key, label, _ in PERIODS %}\n'
               '      <option value="{{ url_for(\'index\', sort=sort, period=key, q=q, genre=genre) }}" {{ \'selected\' if period == key }}>⏰ {{ label }}</option>\n'
               '    {% endfor %}\n'
               '  </select>\n'
               '</div>\n'
               '\n'
               '{% if posts %}\n'
               '<div class="grid">\n'
               '  {% for p in posts %}\n'
               '  <a class="card" href="{{ url_for(\'post_page\', post_id=p.id) }}?src=feed&sort={{ sort }}&period={{ period }}{% if q %}&q={{ q|urlencode }}{% endif %}{% if genre %}&genre={{ '
               'genre|urlencode }}{% endif %}">\n'
               '    <div class="thumb" style="background:linear-gradient(135deg,#fff6f0,#fffbe9)">\n'
               '      {% if p.thumb %}<img src="{{ url_for(\'media\', filename=p.thumb) }}" alt="" loading="lazy">{% else %}🎙️{% endif %}\n'
               '    </div>\n'
               '    <div class="body">\n'
               '      {% if p.genre %}\n'
               '      <span class="genre-jump" data-genre="{{ p.genre }}"\n'
               '         style="display:block;text-align:center;border-radius:10px;padding:3px 6px;font-size:.8rem;font-weight:700;color:#fff;background:{{ GENRE_COLOR.get(p.genre,\'#7a7484\') '
               '}};border:2px solid var(--ink);cursor:pointer">{{ p.genre }}</span>\n'
               '      {% endif %}\n'
               '      <div class="title">{{ p.title }}{% if not p.is_public %} <span class="badge-private">非公開</span>{% endif %}</div>\n'
               '      <div class="meta user-link" data-user="{{ p.username }}" style="cursor:pointer">\n'
               '        {% if p.user_icon %}<img class="mini-icon" src="{{ url_for(\'media\', filename=p.user_icon) }}" alt="">{% else %}😀{% endif %}\n'
               '        <u>{{ p.username }}</u>\n'
               '      </div>\n'
               '      <div class="stats"><span>▶️ {{ p.views }}</span><span>👍 {{ p.likes }}</span><span>🤩 {{ p.fav_count }}</span><span>💬 {{ p.comment_count }}</span></div>\n'
               '    </div>\n'
               '  </a>\n'
               '  {% endfor %}\n'
               '</div>\n'
               '{% else %}\n'
               '<div class="empty">{% if genre %}「{{ genre }}」の投稿はまだありません 🎙️{% else %}まだ投稿がありません。最初のコントを投稿してみよう!🎙️✨{% endif %}</div>\n'
               '{% endif %}\n'
               '{% endblock %}',
 'login.html': '{% extends "base.html" %}\n'
               '{% block title %}ログイン | RAKOMAN{% endblock %}\n'
               '{% block content %}\n'
               '<div class="form-box">\n'
               '  <h1>📻 ログイン</h1>\n'
               '  <form method="post">\n'
               '    <div class="field">\n'
               '      <label for="username">ユーザーネーム</label>\n'
               '      <input type="text" id="username" name="username" required autocomplete="username">\n'
               '    </div>\n'
               '    <div class="field">\n'
               '      <label for="password">パスワード</label>\n'
               '      <input type="password" id="password" name="password" required autocomplete="current-password">\n'
               '    </div>\n'
               '    <button class="btn btn-primary">ログイン</button>\n'
               '  </form>\n'
               '  <p style="margin-top:14px">はじめての方は <a href="{{ url_for(\'register\') }}"><b>新規登録</b></a> 🎉</p>\n'
               '</div>\n'
               '{% endblock %}\n',
 'playlist.html': '{% extends "base.html" %}\n'
                  '{% block title %}{{ pl.title }} | RAKOMAN{% endblock %}\n'
                  '{% block content %}\n'
                  '<div class="post-box">\n'
                  '  <h1 class="post-title">🎶 {{ pl.title }}\n'
                  '    <span class="badge-private" style="{{ \'background:var(--mint)\' if pl.is_public }}">{{ \'公開\' if pl.is_public else \'非公開\' }}</span>\n'
                  '  </h1>\n'
                  '  <p class="meta">作成:<a href="{{ url_for(\'profile\', username=pl.username) }}"><b>{{ pl.username }}</b></a> ・ {{ items|length }}本</p>\n'
                  '\n'
                  '  {% if mine %}\n'
                  '  <div class="action-row">\n'
                  '    <form class="inline-form" method="post" action="{{ url_for(\'playlist_toggle_public\', playlist_id=pl.id) }}">\n'
                  '      <button class="btn btn-small">{{ \'🔓 公開にする\' if not pl.is_public else \'🔒 非公開にする\' }}</button>\n'
                  '    </form>\n'
                  '    <details>\n'
                  '      <summary class="btn btn-small">✏️ タイトル変更</summary>\n'
                  '      <form method="post" action="{{ url_for(\'playlist_rename\', playlist_id=pl.id) }}" style="margin-top:8px;display:flex;gap:6px">\n'
                  '        <input type="text" name="title" value="{{ pl.title }}" required style="padding:6px 12px;border:2.5px solid var(--ink);border-radius:999px;font:inherit">\n'
                  '        <button class="btn btn-small btn-primary">変更</button>\n'
                  '      </form>\n'
                  '    </details>\n'
                  '    <form class="inline-form" method="post" action="{{ url_for(\'playlist_delete\', playlist_id=pl.id) }}"\n'
                  '          onsubmit="return confirm(\'このプレイリストを削除しますか?(投稿自体は消えません)\')">\n'
                  '      <button class="btn btn-small btn-danger">🗑️ プレイリストを削除</button>\n'
                  '    </form>\n'
                  '  </div>\n'
                  '  {% endif %}\n'
                  '</div>\n'
                  '\n'
                  '{% for p in items %}\n'
                  '<div class="pl-item">\n'
                  '  <span class="num">{{ loop.index }}</span>\n'
                  '  {% if p.thumb %}<img class="avatar" src="{{ url_for(\'media\', filename=p.thumb) }}" alt="">{% else %}<span class="avatar avatar-placeholder">🎙️</span>{% endif %}\n'
                  '  <div style="flex:1;min-width:0">\n'
                  '    <a href="{{ url_for(\'post_page\', post_id=p.id) }}"><b>{{ p.title }}</b></a>\n'
                  '    <div class="meta"><a href="{{ url_for(\'profile\', username=p.username) }}"><b>{{ p.username }}</b></a> ・ ▶️ {{ p.views }} ・ 👍 {{ p.likes }}</div>\n'
                  '    <audio class="pl-audio" controls preload="none" src="{{ url_for(\'media\', filename=p.audio) }}" style="width:100%;margin-top:4px"></audio>\n'
                  '  </div>\n'
                  '  {% if mine %}\n'
                  '  <div style="display:flex;flex-direction:column;gap:4px">\n'
                  '    <form class="inline-form" method="post" action="{{ url_for(\'playlist_move\', playlist_id=pl.id) }}">\n'
                  '      <input type="hidden" name="item_id" value="{{ p.item_id }}"><input type="hidden" name="dir" value="up">\n'
                  '      <button class="btn btn-small" {{ \'disabled\' if loop.first }}>▲</button>\n'
                  '    </form>\n'
                  '    <form class="inline-form" method="post" action="{{ url_for(\'playlist_move\', playlist_id=pl.id) }}">\n'
                  '      <input type="hidden" name="item_id" value="{{ p.item_id }}"><input type="hidden" name="dir" value="down">\n'
                  '      <button class="btn btn-small" {{ \'disabled\' if loop.last }}>▼</button>\n'
                  '    </form>\n'
                  '  </div>\n'
                  '  <form class="inline-form" method="post" action="{{ url_for(\'playlist_toggle_item\', playlist_id=pl.id) }}">\n'
                  '    <input type="hidden" name="post_id" value="{{ p.id }}">\n'
                  '    <button class="btn btn-small btn-danger">➖</button>\n'
                  '  </form>\n'
                  '  {% endif %}\n'
                  '</div>\n'
                  '{% else %}\n'
                  '<div class="empty">まだ投稿が入っていません。投稿ページの「🎶 プレイリストに追加」から追加できます!</div>\n'
                  '{% endfor %}\n'
                  '\n'
                  '<script>\n'
                  '// プレイリスト連続再生:1本終わったら次を自動再生\n'
                  'const list = Array.from(document.querySelectorAll(".pl-audio"));\n'
                  'list.forEach((a, i) => {\n'
                  '  a.addEventListener("play", () => list.forEach(o => { if (o !== a) o.pause(); }));\n'
                  '  a.addEventListener("ended", () => { if (list[i + 1]) list[i + 1].play(); });\n'
                  '});\n'
                  '</script>\n'
                  '{% endblock %}\n',
 'post.html': '{% extends "base.html" %}\n'
              '{% block title %}{{ post.title }} | RAKOMAN{% endblock %}\n'
              '{% block content %}\n'
              '<article class="post-box">\n'
              '  {% if post.genre %}<a class="genre-badge" href="{{ url_for(\'index\', genre=post.genre) }}" style="background:{{ GENRE_COLOR.get(post.genre,\'#7a7484\') '
              '}};margin-bottom:6px;display:inline-block">{{ post.genre }}</a>{% endif %}\n'
              '  <h1 class="post-title">{{ post.title }}{% if not post.is_public %} <span class="badge-private">非公開</span>{% endif %}</h1>\n'
              '  <a class="user-chip" href="{{ url_for(\'profile\', username=post.username) }}">\n'
              '    {% if post.user_icon %}<img src="{{ url_for(\'media\', filename=post.user_icon) }}" alt="">\n'
              '    {% else %}<span class="avatar avatar-placeholder">😀</span>{% endif %}\n'
              '    {{ post.username }}\n'
              '  </a>\n'
              '  <span class="meta"> ・ ▶️ {{ post.views + 1 }}回再生 ・ {{ post.created_at[:10] }}</span>\n'
              '\n'
              '  <div class="player">\n'
              '    <audio controls preload="metadata"\n'
              '      src="{{ url_for(\'media\', filename=post.audio) }}"\n'
              '      data-title="{{ post.title }}"\n'
              '      data-artist="{{ post.username }}"\n'
              '      data-next="{{ url_for(\'next_post\', post_id=post.id) }}{% if request.query_string %}?{{ request.query_string.decode() }}{% endif %}"\n'
              '      {% if images %}data-artwork="{{ url_for(\'media\', filename=images[0].filename) }}"{% endif %}>\n'
              '    </audio>\n'
              '    <div class="speed-row">\n'
              '      <span class="label">⏩ 倍速:</span>\n'
              "      {% for r in ['0.75','1.0','1.25','1.5','2.0'] %}\n"
              '        <button type="button" class="speed {{ \'active\' if r == \'1.0\' }}" data-rate="{{ r }}">×{{ r }}</button>\n'
              '      {% endfor %}\n'
              '    </div>\n'
              '    <div id="next-banner" hidden style="margin-top:10px;background:#fff;border:2.5px solid var(--ink);border-radius:12px;padding:8px 12px;font-size:.88rem;font-weight:700">\n'
              '      ▶️ 次を再生中:<a id="next-link" href="#" style="color:var(--coral)"></a>\n'
              '    </div>\n'
              '    <p class="hint">🔒 画面を閉じたり他のアプリを開いてもそのまま再生できます(ロック画面から操作OK)<br>\n'
              '    🔁 再生が終わると、いま見ていた一覧の順で次の投稿が自動再生されます</p>\n'
              '  </div>\n'
              '\n'
              '  {% if images %}\n'
              '  <div class="photo-grid">\n'
              '    {% for img in images %}\n'
              '      <div>\n'
              '        <a href="{{ url_for(\'media\', filename=img.filename) }}" target="_blank" rel="noopener">\n'
              '          <img src="{{ url_for(\'media\', filename=img.filename) }}" alt="投稿写真{{ loop.index }}" loading="lazy"\n'
              '               style="{{ \'outline:4px solid var(--sun)\' if img.id == post.thumb_id or (not post.thumb_id and loop.first) }}">\n'
              '        </a>\n'
              '        {% if me and (me.id == post.user_id or me_is_admin) %}\n'
              '          {% if img.id == post.thumb_id or (not post.thumb_id and loop.first) %}\n'
              '            <p class="hint" style="text-align:center">🖼️ サムネイル</p>\n'
              '          {% else %}\n'
              '            <form method="post" action="{{ url_for(\'set_thumbnail\', post_id=post.id) }}" style="text-align:center">\n'
              '              <input type="hidden" name="image_id" value="{{ img.id }}">\n'
              '              <button class="btn btn-small" style="margin-top:4px">🖼️ サムネにする</button>\n'
              '            </form>\n'
              '          {% endif %}\n'
              '        {% endif %}\n'
              '      </div>\n'
              '    {% endfor %}\n'
              '  </div>\n'
              '  {% endif %}\n'
              '\n'
              '  <div class="action-row">\n'
              '    <button class="btn" data-like="{{ post.id }}">👍 いいね <span class="count">{{ post.likes }}</span></button>\n'
              '    {% if me %}\n'
              '      <button class="btn {{ \'btn-sun\' if faved }}" data-fav="{{ post.id }}">\n'
              '        🤩 <span class="fav-label">{{ \'お気に入り済み\' if faved else \'お気に入り\' }}</span>\n'
              '        <span class="count">{{ post.fav_count }}</span>\n'
              '      </button>\n'
              '    {% else %}\n'
              '      <a class="btn" href="{{ url_for(\'login\', next=request.path) }}">🤩 お気に入り <span class="count">{{ post.fav_count }}</span></a>\n'
              '    {% endif %}\n'
              '    <button class="btn btn-mint" data-copy-url="{{ request.url_root.rstrip(\'/\') }}{{ url_for(\'post_page\', post_id=post.id) }}">🔗 URLをコピーして共有</button>\n'
              '  </div>\n'
              '\n'
              '  {% if post.description %}<p class="desc">{{ post.description }}</p>{% endif %}\n'
              '  {% if post.hashtags %}\n'
              '  <div class="tags">\n'
              '    {% for t in post.hashtags|tags %}\n'
              '      <a class="tag" href="{{ url_for(\'index\', q=\'#\' + t) }}">#{{ t }}</a>\n'
              '    {% endfor %}\n'
              '  </div>\n'
              '  {% endif %}\n'
              '\n'
              '  {% if me %}\n'
              '  <div class="action-row" style="margin-top:18px">\n'
              '    {% if my_playlists %}\n'
              '    <details>\n'
              '      <summary class="btn btn-small">🎶 プレイリストに追加</summary>\n'
              '      <div style="margin-top:8px;display:flex;flex-direction:column;gap:6px">\n'
              '        {% for pl in my_playlists %}\n'
              '        <form class="inline-form" method="post" action="{{ url_for(\'playlist_toggle_item\', playlist_id=pl.id) }}">\n'
              '          <input type="hidden" name="post_id" value="{{ post.id }}">\n'
              '          <button class="btn btn-small {{ \'btn-sun\' if pl.has_it }}">{{ \'✅\' if pl.has_it else \'➕\' }} {{ pl.title }}</button>\n'
              '        </form>\n'
              '        {% endfor %}\n'
              '      </div>\n'
              '    </details>\n'
              '    {% endif %}\n'
              '    <details>\n'
              '      <summary class="btn btn-small">🆕 新しいプレイリストを作って追加</summary>\n'
              '      <form method="post" action="{{ url_for(\'create_playlist\') }}" style="margin-top:8px;display:flex;gap:6px;flex-wrap:wrap">\n'
              '        <input type="hidden" name="post_id" value="{{ post.id }}">\n'
              '        <input type="text" name="title" placeholder="プレイリスト名" required style="padding:6px 12px;border:2.5px solid var(--ink);border-radius:999px;font:inherit">\n'
              '        <label style="font-size:.85rem"><input type="checkbox" name="is_public" value="1"> 公開する</label>\n'
              '        <button class="btn btn-small btn-primary">作成 🎶</button>\n'
              '      </form>\n'
              '    </details>\n'
              '  </div>\n'
              '  {% endif %}\n'
              '\n'
              '  {% if me and (me.id == post.user_id or me_is_admin) %}\n'
              '  <div class="action-row" style="border-top:2px dashed var(--line);padding-top:12px">\n'
              '    \n'
              '    {% if me.id == post.user_id %}\n'
              '    <a class="btn btn-small" href="{{ url_for(\'edit_post\', post_id=post.id) }}">✏️ タイトル・説明を編集</a>\n'
              '    {% endif %}\n'
              '    <form class="inline-form" method="post" action="{{ url_for(\'toggle_public\', post_id=post.id) }}">\n'
              '      <button class="btn btn-small">{{ \'🔓 公開にする\' if not post.is_public else \'🔒 非公開にする\' }}</button>\n'
              '    </form>\n'
              '    <span id="del-wrap-{{post.id}}">\n'
              '      <button type="button" class="btn btn-small btn-danger" onclick="document.getElementById(\'del-wrap-{{post.id}}\').innerHTML=\'<form method=\\\'post\\\'  '
              'action=\\\'/post/{{post.id}}/delete\\\'><button class=\\\'btn btn-small btn-danger\\\'>⚠️ 本当に削除する</button></form>\'">🗑️ 投稿を削除{{ \'(管理人)\' if me.id != post.user_id }}</span>\n'
              '  </div>\n'
              '  {% endif %}\n'
              '</article>\n'
              '\n'
              '<section class="post-box" id="comments">\n'
              '  <h2 style="margin-top:0">💬 コメント({{ comments|length }})</h2>\n'
              '  <p class="note">※誹謗中傷、性的な内容はおやめください</p>\n'
              '\n'
              '  {% for c in comments %}\n'
              '  <div class="comment">\n'
              '    <a href="{{ url_for(\'profile\', username=c.username) }}" title="{{ c.username }}のプロフィールを見る">\n'
              '      {% if c.user_icon %}<img class="avatar" src="{{ url_for(\'media\', filename=c.user_icon) }}" alt="{{ c.username }}">\n'
              '      {% else %}<span class="avatar avatar-placeholder">😀</span>{% endif %}\n'
              '    </a>\n'
              '    <div class="body">\n'
              '      <div class="who"><a href="{{ url_for(\'profile\', username=c.username) }}">{{ c.username }}</a>\n'
              '        <time> {{ c.created_at[:16] }}</time></div>\n'
              '      <div class="text">{{ c.body }}</div>\n'
              '    </div>\n'
              '    {% if me and (me.id == c.user_id or me.id == post.user_id or me_is_admin) %}\n'
              '    <form class="inline-form" method="post" action="{{ url_for(\'delete_comment\', comment_id=c.id) }}"\n'
              '          onsubmit="return confirm(\'このコメントを削除しますか?\')">\n'
              '      <button class="btn btn-small btn-danger">🗑️</button>\n'
              '    </form>\n'
              '    {% endif %}\n'
              '  </div>\n'
              '  {% else %}\n'
              '  <p class="empty">まだコメントがありません。感想を伝えてあげよう!😆🎉👏</p>\n'
              '  {% endfor %}\n'
              '\n'
              '  {% if me %}\n'
              '  <form method="post" action="{{ url_for(\'add_comment\', post_id=post.id) }}" style="margin-top:14px">\n'
              '    <div class="field">\n'
              '      <textarea name="body" placeholder="おもしろかったポイントを伝えよう!😂👏✨" required></textarea>\n'
              '      <p class="hint">🎯 ルール:コメントには絵文字を<b>3種類以上</b>入れてね!(例:😂👏🔥)</p>\n'
              '    </div>\n'
              '    <button class="btn btn-primary">コメントする 💬</button>\n'
              '  </form>\n'
              '  {% else %}\n'
              '  <p><a class="btn" href="{{ url_for(\'login\', next=request.path) }}">ログインしてコメントする ✍️</a></p>\n'
              '  {% endif %}\n'
              '</section>\n'
              '{% endblock %}\n',
 'profile.html': '{% extends "base.html" %}\n'
                 '{% block title %}{{ user.username }} | RAKOMAN{% endblock %}\n'
                 '{% block content %}\n'
                 '<div class="profile-head">\n'
                 '  {% if user.icon %}<img class="avatar" src="{{ url_for(\'media\', filename=user.icon) }}" alt="">\n'
                 '  {% else %}<span class="avatar avatar-placeholder">😀</span>{% endif %}\n'
                 '  <div>\n'
                 "    <h1>{{ user.username }} {% if user.username == 'admin' %}🛡️{% endif %}</h1>\n"
                 '    <p class="hint">{{ user.created_at[:10] }} からRAKOMANにいます 📻</p>\n'
                 '    {% if mine %}\n'
                 '    <form method="post" action="{{ url_for(\'change_icon\') }}" enctype="multipart/form-data" style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">\n'
                 '      <input class="file-input" type="file" name="icon" accept="image/*" required>\n'
                 '      <button class="btn btn-small">📸 アイコンを変更</button>\n'
                 '    </form>\n'
                 '    {% endif %}\n'
                 '  </div>\n'
                 '</div>\n'
                 '\n'
                 '{% if user.bio %}\n'
                 '<div class="post-box" style="padding:14px 18px">\n'
                 '  <p class="desc" style="margin:0">{{ user.bio }}</p>\n'
                 '</div>\n'
                 '{% endif %}\n'
                 '\n'
                 '{% if mine %}\n'
                 '<details style="margin:10px 0 4px">\n'
                 '  <summary class="btn btn-small">📝 自己紹介を{{ \'編集\' if user.bio else \'書く\' }}(500字まで)</summary>\n'
                 '  <form method="post" action="{{ url_for(\'change_bio\') }}" style="margin-top:8px">\n'
                 '    <div class="field">\n'
                 '      <textarea name="bio" id="bio" maxlength="500" placeholder="コンビ名、活動歴、好きなネタのジャンルなど…">{{ user.bio or \'\' }}</textarea>\n'
                 '      <p class="hint"><span id="bio-count">{{ (user.bio or \'\')|length }}</span> / 500字</p>\n'
                 '    </div>\n'
                 '    <button class="btn btn-small btn-primary">保存する 📝</button>\n'
                 '  </form>\n'
                 '</details>\n'
                 '<script>\n'
                 'const bioEl = document.getElementById("bio");\n'
                 'if (bioEl) bioEl.addEventListener("input", () => {\n'
                 '  document.getElementById("bio-count").textContent = bioEl.value.length;\n'
                 '});\n'
                 '</script>\n'
                 '{% endif %}\n'
                 '\n'
                 '<div class="tabs">\n'
                 '  <a class="tab {{ \'active\' if tab == \'posts\' }}" href="{{ url_for(\'profile\', username=user.username, tab=\'posts\') }}">🎙️ 投稿({{ posts|length }})</a>\n'
                 '  <a class="tab {{ \'active\' if tab == \'favorites\' }}" href="{{ url_for(\'profile\', username=user.username, tab=\'favorites\') }}">🤩 お気に入り({{ favorites|length }})</a>\n'
                 '  <a class="tab {{ \'active\' if tab == \'playlists\' }}" href="{{ url_for(\'profile\', username=user.username, tab=\'playlists\') }}">🎶 プレイリスト({{ playlists|length }})</a>\n'
                 '</div>\n'
                 '\n'
                 "{% if tab == 'favorites' %}\n"
                 '  {% set items = favorites %}\n'
                 "{% elif tab == 'playlists' %}\n"
                 '  {% set items = [] %}\n'
                 '{% else %}\n'
                 '  {% set items = posts %}\n'
                 '{% endif %}\n'
                 '\n'
                 "{% if tab == 'playlists' %}\n"
                 '  {% if mine %}\n'
                 '  <form method="post" action="{{ url_for(\'create_playlist\') }}" style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:16px">\n'
                 '    <input type="text" name="title" placeholder="新しいプレイリスト名" required style="padding:8px 14px;border:2.5px solid var(--ink);border-radius:999px;font:inherit">\n'
                 '    <label style="align-self:center;font-size:.9rem"><input type="checkbox" name="is_public" value="1"> 公開する</label>\n'
                 '    <button class="btn btn-primary btn-small">作成 🎶</button>\n'
                 '  </form>\n'
                 '  {% endif %}\n'
                 '  {% for pl in playlists %}\n'
                 '  <a class="pl-item" href="{{ url_for(\'playlist_page\', playlist_id=pl.id) }}">\n'
                 '    <span class="num">🎶</span>\n'
                 '    <div style="flex:1">\n'
                 '      <b>{{ pl.title }}</b>\n'
                 '      <span class="hint">{{ pl.n }}本</span>\n'
                 '    </div>\n'
                 '    <span class="badge-private" style="{{ \'background:var(--mint)\' if pl.is_public }}">{{ \'公開\' if pl.is_public else \'非公開\' }}</span>\n'
                 '  </a>\n'
                 '  {% else %}\n'
                 '  <div class="empty">プレイリストはまだありません 🎶</div>\n'
                 '  {% endfor %}\n'
                 '{% else %}\n'
                 '  {% if items %}\n'
                 '  <div class="grid">\n'
                 '    {% for p in items %}\n'
                 '    <a class="card" href="{{ url_for(\'post_page\', post_id=p.id) }}?src={{ \'ufav\' if tab == \'favorites\' else \'user\' }}&u={{ user.username|urlencode }}">\n'
                 '      <div class="thumb">\n'
                 '        {% if p.thumb %}<img src="{{ url_for(\'media\', filename=p.thumb) }}" alt="" loading="lazy">{% else %}🎙️{% endif %}\n'
                 '      </div>\n'
                 '      <div class="body">\n'
                 '        {% if p.genre %}<span class="genre-jump" data-genre="{{ p.genre }}" style="background:{{ GENRE_COLOR.get(p.genre,\'#7a7484\') '
                 '}};display:block;text-align:center;border-radius:12px;padding:3px 8px;margin-bottom:4px;font-size:.82rem" style="cursor:pointer">{{ p.genre }}</span>{% endif %}\n'
                 '        <div class="title">{{ p.title }}{% if not p.is_public %} <span class="badge-private">非公開</span>{% endif %}</div>\n'
                 '        <div class="meta user-link" data-user="{{ p.username }}">{{ p.username }}</div>\n'
                 '        <div class="stats"><span>▶️ {{ p.views }}</span><span>👍 {{ p.likes }}</span><span>🤩 {{ p.fav_count }}</span></div>\n'
                 '      </div>\n'
                 '    </a>\n'
                 '    {% endfor %}\n'
                 '  </div>\n'
                 '  {% else %}\n'
                 '  <div class="empty">{{ \'お気に入りはまだありません 🤩\' if tab == \'favorites\' else \'まだ投稿がありません 🎙️\' }}</div>\n'
                 '  {% endif %}\n'
                 '{% endif %}\n'
                 '{% endblock %}\n',
 'register.html': '{% extends "base.html" %}\n'
                  '{% block title %}はじめる | RAKOMAN{% endblock %}\n'
                  '{% block content %}\n'
                  '<div class="form-box">\n'
                  '  <h1>🎉 RAKOMANをはじめる</h1>\n'
                  '  <p class="hint">メールアドレスの登録は不要です。ユーザーネームとパスワードだけでOK!</p>\n'
                  '  <div class="warn-box">\n'
                  '    ⚠️ <b>ご注意:ユーザーネームはあとから変更できません。</b><br>\n'
                  '    よく考えてから登録してください(アイコン画像はいつでも変更できます)。\n'
                  '  </div>\n'
                  '  <form method="post">\n'
                  '    <div class="field">\n'
                  '      <label for="username">ユーザーネーム(変更不可)</label>\n'
                  '      <input type="text" id="username" name="username" maxlength="20" required autocomplete="username">\n'
                  '      <p class="hint">1〜20文字。ひらがな・カタカナ・漢字・英数字・「_」「.」「・」が使えます</p>\n'
                  '    </div>\n'
                  '    <div class="field">\n'
                  '      <label for="password">パスワード</label>\n'
                  '      <input type="password" id="password" name="password" minlength="6" required autocomplete="new-password">\n'
                  '      <p class="hint">6文字以上</p>\n'
                  '    </div>\n'
                  '    <button class="btn btn-primary">登録してはじめる 🎙️</button>\n'
                  '  </form>\n'
                  '  <p style="margin-top:14px">アカウントを持っている方は <a href="{{ url_for(\'login\') }}"><b>ログイン</b></a></p>\n'
                  '</div>\n'
                  '{% endblock %}\n',
 'upload.html': '{% extends "base.html" %}\n'
                '{% block title %}投稿する | RAKOMAN{% endblock %}\n'
                '{% block content %}\n'
                '<div class="form-box">\n'
                '  <h1>🎙️ コント・漫才を投稿する</h1>\n'
                '  <form method="post" enctype="multipart/form-data">\n'
                '    <div class="field">\n'
                '      <label for="audio">音声ファイル(必須)</label>\n'
                '      <input class="file-input" type="file" id="audio" name="audio" accept="audio/*,.m4a,.mp3,.wav,.aac,.caf" required>\n'
                '      <p class="hint">📱 スマホの「ファイル」やボイスメモから選べます(mp3 / m4a / wav など)<br>🚫 動画はアップロードできません。音声は必須なので写真だけの投稿はできません</p>\n'
                '    </div>\n'
                '    <div class="field">\n'
                '      <label>🎭 ジャンル(必須)</label>\n'
                '      <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:4px">\n'
                '        {% for g in GENRES %}\n'
                '        <label style="cursor:pointer">\n'
                '          <input type="radio" name="genre" value="{{ g }}" required style="display:none" class="genre-radio">\n'
                '          <span class="genre-badge" style="background:#fff;color:var(--ink);border-color:var(--line)">{{ g }}</span>\n'
                '        </label>\n'
                '        {% endfor %}\n'
                '      </div>\n'
                '      <p class="hint">いずれか1つを選んでください</p>\n'
                '    </div>\n'
                '    <div class="field">\n'
                '      <label for="title">タイトル(必須)</label>\n'
                '      <input type="text" id="title" name="title" maxlength="60" required placeholder="例:コンビニの新人がヤバすぎる">\n'
                '    </div>\n'
                '    <div class="field">\n'
                '      <label for="description">説明</label>\n'
                '      <textarea id="description" name="description" placeholder="ネタの紹介や聞きどころなど"></textarea>\n'
                '    </div>\n'
                '    <div class="field">\n'
                '      <label for="hashtags">ハッシュタグ</label>\n'
                '      <input type="text" id="hashtags" name="hashtags" placeholder="例:#コント #漫才 #エピソードトーク">\n'
                '      <p class="hint">スペースか「,」で区切って入力</p>\n'
                '    </div>\n'
                '    <div class="field">\n'
                '      <label for="images">写真(4枚まで)</label>\n'
                '      <input class="file-input" type="file" id="images" name="images" accept="image/*" multiple>\n'
                '      <p class="hint">📸 5枚以上選んだ場合は先頭の4枚だけ使われます。投稿後、投稿ページでどの写真をサムネイルにするか選べます🖼️</p>\n'
                '    </div>\n'
                '    <div class="field">\n'
                '      <label><input type="checkbox" name="is_public" value="1" checked> 公開する(あとからいつでも変更できます)</label>\n'
                '    </div>\n'
                '    <p class="note">※誹謗中傷、性的な内容はおやめください</p>\n'
                '    <button class="btn btn-primary">投稿する 🎉</button>\n'
                '  </form>\n'
                '</div>\n'
                '<script>\n'
                'document.getElementById("images").addEventListener("change", function () {\n'
                '  if (this.files.length > 4) {\n'
                '    alert("写真は4枚までです!先頭の4枚だけが投稿されます 📸");\n'
                '  }\n'
                '});\n'
                '</script>\n'
                '{% endblock %}\n'}
app.jinja_loader = DictLoader(TEMPLATES)


GENRES = ["コント", "漫才", "漫談", "エピソードトーク", "その他"]
GENRE_COLOR = {
    "コント": "#ff5470", "漫才": "#5aa9ff", "漫談": "#2ec4b6",
    "エピソードトーク": "#ffc830", "その他": "#7a7484",
}

AUDIO_EXT = {"mp3", "m4a", "wav", "aac", "ogg", "oga", "webm", "flac", "caf", "amr", "3gp"}  # 動画(mp4等)は不可
IMAGE_EXT = {"jpg", "jpeg", "png", "gif", "webp", "heic", "heif"}

PERIODS = [
    ("24h", "24時間", 1),
    ("1w", "1週間", 7),
    ("1m", "1ヶ月", 30),
    ("3m", "3ヶ月", 92),
    ("6m", "半年", 183),
    ("1y", "1年", 366),
    ("all", "全期間", None),
]
SORTS = [("new", "新着順"), ("likes", "いいね順"), ("favs", "お気に入り順")]

# 絵文字判定(主要な絵文字ブロックをカバー)
EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001F5FF"
    "\U0001F600-\U0001F64F"
    "\U0001F680-\U0001F6FF"
    "\U0001F700-\U0001F77F"
    "\U0001F780-\U0001F7FF"
    "\U0001F900-\U0001F9FF"
    "\U0001FA70-\U0001FAFF"
    "\U0001F1E6-\U0001F1FF"
    "\U00002600-\U000027BF"
    "\U00002B00-\U00002BFF"
    "\U00002190-\U000021FF"
    "\U00002300-\U000023FF"
    "\u2764\u2763\u203C\u2049\u3030\u303D\u3297\u3299"
    "]"
)


def distinct_emoji_count(text):
    """文章中の絵文字の「種類」を数える"""
    return len(set(EMOJI_RE.findall(text or "")))


# ---------------------------------------------------------------- DB
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(DB_PATH)
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            icon TEXT,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            hashtags TEXT DEFAULT '',
            audio TEXT NOT NULL,
            views INTEGER DEFAULT 0,
            likes INTEGER DEFAULT 0,
            is_public INTEGER DEFAULT 1,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS post_images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
            filename TEXT NOT NULL,
            position INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS favorites (
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            post_id INTEGER NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
            created_at TEXT NOT NULL,
            PRIMARY KEY (user_id, post_id)
        );
        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            body TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS playlists (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            title TEXT NOT NULL,
            is_public INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS playlist_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            playlist_id INTEGER NOT NULL REFERENCES playlists(id) ON DELETE CASCADE,
            post_id INTEGER NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
            position INTEGER DEFAULT 0,
            UNIQUE (playlist_id, post_id)
        );
        """
    )
    # 既存DBへのマイグレーション:自己紹介カラム
    cols = [r[1] for r in db.execute("PRAGMA table_info(users)").fetchall()]
    if "bio" not in cols:
        db.execute("ALTER TABLE users ADD COLUMN bio TEXT DEFAULT ''")
    pcols = [r[1] for r in db.execute("PRAGMA table_info(posts)").fetchall()]
    if "thumb_id" not in pcols:
        db.execute("ALTER TABLE posts ADD COLUMN thumb_id INTEGER")
    if "genre" not in pcols:
        db.execute("ALTER TABLE posts ADD COLUMN genre TEXT DEFAULT ''")
    db.commit()
    db.close()


init_db()


def now_str():
    return datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


# ---------------------------------------------------------------- 認証まわり
def current_user():
    uid = session.get("user_id")
    if not uid:
        return None
    return get_db().execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()


def is_admin(user):
    return bool(user) and user["username"] == ADMIN_USERNAME


def login_required(view):
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user():
            flash("ログインしてください 🙏")
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


@app.context_processor
def inject_globals():
    user = current_user()
    return dict(me=user, me_is_admin=is_admin(user), SORTS=SORTS, PERIODS=PERIODS, GENRES=GENRES, GENRE_COLOR=GENRE_COLOR)


# ---------------------------------------------------------------- ファイル
def ext_of(filename):
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


MIME_TO_EXT = {
    "image/jpeg": "jpg", "image/jpg": "jpg", "image/png": "png",
    "image/gif": "gif", "image/webp": "webp",
    "image/heic": "heic", "image/heif": "heif",
    "audio/mpeg": "mp3", "audio/mp3": "mp3",
    "audio/mp4": "m4a", "audio/x-m4a": "m4a", "audio/aac": "aac",
    "audio/wav": "wav", "audio/x-wav": "wav",
    "audio/ogg": "ogg", "audio/webm": "webm",
    "audio/flac": "flac", "audio/amr": "amr",
    "video/mp4": None,  # 動画は明示的に拒否
}

def save_upload(file, allowed):
    ext = ext_of(file.filename or "")
    # iOSなど拡張子がない・不正な場合はContent-Typeから推定
    if not ext or ext not in allowed:
        ct = (file.content_type or "").split(";")[0].strip().lower()
        guessed = MIME_TO_EXT.get(ct)
        if guessed is None and ct.startswith("video/"):
            return None  # 動画は拒否
        if guessed:
            ext = guessed
    if not ext or ext not in allowed:
        return None
    name = uuid.uuid4().hex + "." + ext
    file.save(os.path.join(UPLOAD_DIR, name))
    return name


def delete_file(name):
    if not name:
        return
    try:
        os.remove(os.path.join(UPLOAD_DIR, name))
    except OSError:
        pass


@app.route("/media/<path:filename>")
def media(filename):
    return send_from_directory(UPLOAD_DIR, filename, conditional=True)


# ---------------------------------------------------------------- 投稿一覧クエリ
POST_SELECT = """
SELECT p.*, u.username, u.icon AS user_icon,
       (SELECT COUNT(*) FROM favorites f WHERE f.post_id = p.id) AS fav_count,
       (SELECT COUNT(*) FROM comments c WHERE c.post_id = p.id) AS comment_count,
       COALESCE(
         (SELECT filename FROM post_images i WHERE i.id = p.thumb_id AND i.post_id = p.id),
         (SELECT filename FROM post_images i WHERE i.post_id = p.id ORDER BY position LIMIT 1)
       ) AS thumb
FROM posts p JOIN users u ON u.id = p.user_id
"""


def fetch_posts(where="", params=(), sort="new", period="all"):
    conds = [where] if where else []
    args = list(params)
    days = next((d for key, _, d in PERIODS if key == period), None)
    if days:
        since = (datetime.datetime.utcnow() - datetime.timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        conds.append("p.created_at >= ?")
        args.append(since)
    sql = POST_SELECT
    if conds:
        sql += " WHERE " + " AND ".join(conds)
    order = {"new": "p.created_at DESC, p.id DESC",
             "likes": "p.likes DESC, p.created_at DESC, p.id DESC",
             "favs": "fav_count DESC, p.created_at DESC, p.id DESC"}.get(sort, "p.created_at DESC, p.id DESC")
    sql += " ORDER BY " + order + " LIMIT 200"
    return get_db().execute(sql, args).fetchall()


def split_tags(hashtags):
    return [t for t in re.split(r"[\s,、]+", (hashtags or "").replace("#", " ")) if t]


app.jinja_env.filters["tags"] = split_tags


# ---------------------------------------------------------------- ページ
@app.route("/")
def index():
    sort   = request.args.get("sort", "new")
    period = request.args.get("period", "all")
    genre  = request.args.get("genre", "")
    q      = (request.args.get("q") or "").strip()
    where, params = "p.is_public = 1", []
    if genre and genre in GENRES:
        where += " AND p.genre = ?"
        params.append(genre)
    if q:
        like = f"%{q}%"
        where += " AND (p.title LIKE ? OR u.username LIKE ? OR p.hashtags LIKE ?)"
        params += [like, like, like.replace("#", "")]
    posts = fetch_posts(where, params, sort, period)
    return render_template("index.html", posts=posts, sort=sort, period=period, q=q, genre=genre)


# -------- 会員登録 / ログイン
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        if not re.fullmatch(r"[0-9A-Za-zぁ-んァ-ヶ一-龠ー_．.・]{1,20}", username):
            flash("ユーザーネームは1〜20文字で、使えない記号が含まれています 🙅")
        elif len(password) < 6:
            flash("パスワードは6文字以上にしてください 🔑")
        else:
            db = get_db()
            try:
                db.execute(
                    "INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
                    (username, generate_password_hash(password), now_str()),
                )
                db.commit()
            except sqlite3.IntegrityError:
                flash("そのユーザーネームはすでに使われています 😢")
            else:
                user = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
                session["user_id"] = user["id"]
                flash(f"ようこそ {username} さん!🎉")
                return redirect(url_for("index"))
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        user = get_db().execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            flash("おかえりなさい!📻")
            return redirect(request.args.get("next") or url_for("index"))
        flash("ユーザーネームかパスワードが違います 😣")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("ログアウトしました 👋")
    return redirect(url_for("index"))


# -------- 投稿
@app.route("/upload", methods=["GET", "POST"])
@login_required
def upload():
    if request.method == "POST":
        me = current_user()
        title = (request.form.get("title") or "").strip()
        description = (request.form.get("description") or "").strip()
        hashtags = " ".join(split_tags(request.form.get("hashtags")))
        is_public = 1 if request.form.get("is_public") == "1" else 0
        genre = (request.form.get("genre") or "").strip()
        audio = request.files.get("audio")
        if not title:
            flash("タイトルを入れてください ✍️")
        elif genre not in GENRES:
            flash("ジャンルを選んでください 🎭")
        elif not audio or not audio.filename:
            flash("音声ファイルを選んでください 🎙️")
        else:
            audio_name = save_upload(audio, AUDIO_EXT)
            if not audio_name:
                flash("対応していない音声形式です(mp3 / m4a / wav などでお願いします)🙏")
            else:
                db = get_db()
                cur = db.execute(
                    "INSERT INTO posts (user_id, title, description, hashtags, audio, is_public, genre, created_at)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (me["id"], title, description, hashtags, audio_name, is_public, genre, now_str()),
                )
                post_id = cur.lastrowid
                images = [f for f in request.files.getlist("images") if f and f.filename][:4]
                for i, img in enumerate(images):
                    img_name = save_upload(img, IMAGE_EXT)
                    if img_name:
                        db.execute(
                            "INSERT INTO post_images (post_id, filename, position) VALUES (?, ?, ?)",
                            (post_id, img_name, i),
                        )
                db.commit()
                flash("投稿しました!🎉📻")
                return redirect(url_for("post_page", post_id=post_id))
    return render_template("upload.html")


def get_post_or_404(post_id):
    post = get_db().execute(POST_SELECT + " WHERE p.id = ?", (post_id,)).fetchone()
    if not post:
        abort(404)
    return post


def can_view(post, user):
    return post["is_public"] or (user and (user["id"] == post["user_id"] or is_admin(user)))


@app.route("/post/<int:post_id>")
def post_page(post_id):
    db = get_db()
    post = get_post_or_404(post_id)
    me = current_user()
    if not can_view(post, me):
        abort(404)
    db.execute("UPDATE posts SET views = views + 1 WHERE id = ?", (post_id,))
    db.commit()
    images = db.execute(
        "SELECT * FROM post_images WHERE post_id = ? ORDER BY position", (post_id,)
    ).fetchall()
    comments = db.execute(
        "SELECT c.*, u.username, u.icon AS user_icon FROM comments c JOIN users u ON u.id = c.user_id"
        " WHERE c.post_id = ? ORDER BY c.created_at",
        (post_id,),
    ).fetchall()
    faved = False
    my_playlists = []
    if me:
        faved = db.execute(
            "SELECT 1 FROM favorites WHERE user_id = ? AND post_id = ?", (me["id"], post_id)
        ).fetchone() is not None
        my_playlists = db.execute(
            "SELECT pl.*, (SELECT 1 FROM playlist_items pi WHERE pi.playlist_id = pl.id AND pi.post_id = ?) AS has_it"
            " FROM playlists pl WHERE pl.user_id = ? ORDER BY pl.created_at DESC",
            (post_id, me["id"]),
        ).fetchall()
    return render_template(
        "post.html", post=post, images=images, comments=comments,
        faved=faved, my_playlists=my_playlists,
    )


@app.post("/post/<int:post_id>/like")
def like(post_id):
    db = get_db()
    db.execute("UPDATE posts SET likes = likes + 1 WHERE id = ?", (post_id,))
    db.commit()
    likes = db.execute("SELECT likes FROM posts WHERE id = ?", (post_id,)).fetchone()
    if not likes:
        abort(404)
    return jsonify(likes=likes["likes"])


@app.post("/post/<int:post_id>/favorite")
@login_required
def favorite(post_id):
    me = current_user()
    db = get_db()
    get_post_or_404(post_id)
    row = db.execute(
        "SELECT 1 FROM favorites WHERE user_id = ? AND post_id = ?", (me["id"], post_id)
    ).fetchone()
    if row:
        db.execute("DELETE FROM favorites WHERE user_id = ? AND post_id = ?", (me["id"], post_id))
        faved = False
    else:
        db.execute(
            "INSERT INTO favorites (user_id, post_id, created_at) VALUES (?, ?, ?)",
            (me["id"], post_id, now_str()),
        )
        faved = True
    db.commit()
    count = db.execute("SELECT COUNT(*) AS c FROM favorites WHERE post_id = ?", (post_id,)).fetchone()["c"]
    return jsonify(faved=faved, count=count)


@app.post("/post/<int:post_id>/toggle_public")
@login_required
def toggle_public(post_id):
    me = current_user()
    post = get_post_or_404(post_id)
    if post["user_id"] != me["id"] and not is_admin(me):
        abort(403)
    db = get_db()
    db.execute("UPDATE posts SET is_public = 1 - is_public WHERE id = ?", (post_id,))
    db.commit()
    flash("公開設定を変更しました 🔁")
    return redirect(url_for("post_page", post_id=post_id))


@app.post("/post/<int:post_id>/delete")
@login_required
def delete_post(post_id):
    me = current_user()
    post = get_post_or_404(post_id)
    if post["user_id"] != me["id"] and not is_admin(me):
        abort(403)
    db = get_db()
    delete_file(post["audio"])
    for img in db.execute("SELECT filename FROM post_images WHERE post_id = ?", (post_id,)):
        delete_file(img["filename"])
    db.execute("DELETE FROM posts WHERE id = ?", (post_id,))
    db.commit()
    flash("投稿を削除しました 🗑️")
    return redirect(url_for("profile", username=post["username"]))


@app.post("/post/<int:post_id>/thumbnail")
@login_required
def set_thumbnail(post_id):
    me = current_user()
    post = get_post_or_404(post_id)
    if post["user_id"] != me["id"] and not is_admin(me):
        abort(403)
    image_id = request.form.get("image_id")
    db = get_db()
    img = db.execute(
        "SELECT id FROM post_images WHERE id = ? AND post_id = ?", (image_id, post_id)
    ).fetchone()
    if img:
        db.execute("UPDATE posts SET thumb_id = ? WHERE id = ?", (img["id"], post_id))
        db.commit()
        flash("サムネイルを設定しました!🖼️✨")
    return redirect(url_for("post_page", post_id=post_id))


def rows_for_context(args):
    """連続再生のコンテキスト(どの一覧から再生したか)に応じた投稿リスト"""
    src = args.get("src", "feed")
    me = current_user()
    db = get_db()
    if src in ("user", "ufav"):
        u = db.execute("SELECT * FROM users WHERE username = ?", (args.get("u", ""),)).fetchone()
        if not u:
            return []
        if src == "user":
            mine = me and (me["id"] == u["id"] or is_admin(me))
            where = "p.user_id = ?" if mine else "p.user_id = ? AND p.is_public = 1"
            return fetch_posts(where, (u["id"],), "new", "all")
        return fetch_posts(
            "p.is_public = 1 AND p.id IN (SELECT post_id FROM favorites WHERE user_id = ?)",
            (u["id"],), "new", "all",
        )
    # feed: トップの並び(新着/いいね/お気に入り)・期間・検索・ジャンルをそのまま引き継ぐ
    sort = args.get("sort", "new")
    period = args.get("period", "all")
    genre  = args.get("genre", "")
    q = (args.get("q") or "").strip()
    where, params = "p.is_public = 1", []
    if genre and genre in GENRES:
        where += " AND p.genre = ?"
        params.append(genre)
    if q:
        like = f"%{q}%"
        where += " AND (p.title LIKE ? OR u.username LIKE ? OR p.hashtags LIKE ?)"
        params += [like, like, like.replace("#", "")]
    return fetch_posts(where, params, sort, period)


@app.get("/post/<int:post_id>/next")
def next_post(post_id):
    rows = rows_for_context(request.args)
    ids = [r["id"] for r in rows]
    if post_id in ids:
        i = ids.index(post_id) + 1
        if i < len(rows):
            nxt = rows[i]
            db = get_db()
            db.execute("UPDATE posts SET views = views + 1 WHERE id = ?", (nxt["id"],))
            db.commit()
            qs = request.query_string.decode()
            return jsonify(
                end=False,
                id=nxt["id"],
                title=nxt["title"],
                artist=nxt["username"],
                audio=url_for("media", filename=nxt["audio"]),
                artwork=url_for("media", filename=nxt["thumb"]) if nxt["thumb"] else None,
                post_url=url_for("post_page", post_id=nxt["id"]) + ("?" + qs if qs else ""),
                next_endpoint=url_for("next_post", post_id=nxt["id"]) + ("?" + qs if qs else ""),
            )
    return jsonify(end=True)



@app.route("/post/<int:post_id>/edit", methods=["GET", "POST"])
@login_required
def edit_post(post_id):
    me = current_user()
    post = get_post_or_404(post_id)
    if post["user_id"] != me["id"] and not is_admin(me):
        abort(403)
    db = get_db()
    images = db.execute(
        "SELECT * FROM post_images WHERE post_id = ? ORDER BY position", (post_id,)
    ).fetchall()
    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        description = (request.form.get("description") or "").strip()
        hashtags = " ".join(split_tags(request.form.get("hashtags")))
        genre = (request.form.get("genre") or "").strip()
        if not title:
            flash("タイトルを入れてください ✍️")
        elif genre not in GENRES:
            flash("ジャンルを選んでください 🎭")
        else:
            pass
        if not title or genre not in GENRES:
            return render_template("edit_post.html", post=post, images=images)
        if True:
            # 音声ファイルの差し替え(任意)
            new_audio = request.files.get("audio")
            if new_audio and new_audio.filename:
                audio_name = save_upload(new_audio, AUDIO_EXT)
                if audio_name:
                    delete_file(post["audio"])
                    db.execute("UPDATE posts SET audio = ? WHERE id = ?", (audio_name, post_id))
                else:
                    flash("対応していない音声形式です(mp3 / m4a / wav など)🙏")
                    return render_template("edit_post.html", post=post, images=images)
            # 写真の個別削除
            for img_id in request.form.getlist("delete_image"):
                img = db.execute(
                    "SELECT filename FROM post_images WHERE id = ? AND post_id = ?", (img_id, post_id)
                ).fetchone()
                if img:
                    delete_file(img["filename"])
                    db.execute("DELETE FROM post_images WHERE id = ?", (img_id,))
            # 新しい写真の追加(合計4枚まで)
            cur_count = db.execute(
                "SELECT COUNT(*) FROM post_images WHERE post_id = ?", (post_id,)
            ).fetchone()[0]
            slots = max(0, 4 - cur_count)
            new_imgs = [f for f in request.files.getlist("new_images") if f and f.filename][:slots]
            for i, img in enumerate(new_imgs):
                img_name = save_upload(img, IMAGE_EXT)
                if img_name:
                    db.execute(
                        "INSERT INTO post_images (post_id, filename, position) VALUES (?, ?, ?)",
                        (post_id, img_name, cur_count + i),
                    )
            db.execute(
                "UPDATE posts SET title = ?, description = ?, hashtags = ?, genre = ? WHERE id = ?",
                (title, description, hashtags, genre, post_id),
            )
            db.commit()
            flash("投稿を更新しました!✏️✨")
            return redirect(url_for("post_page", post_id=post_id))
    return render_template("edit_post.html", post=post, images=images)

# -------- コメント
@app.post("/post/<int:post_id>/comment")
@login_required
def add_comment(post_id):
    me = current_user()
    get_post_or_404(post_id)
    body = (request.form.get("body") or "").strip()
    if not body:
        flash("コメントを入力してください ✍️")
    elif distinct_emoji_count(body) < 3:
        flash("コメントには絵文字を3種類以上入れてください!😆🎉👏")
    else:
        db = get_db()
        db.execute(
            "INSERT INTO comments (post_id, user_id, body, created_at) VALUES (?, ?, ?, ?)",
            (post_id, me["id"], body, now_str()),
        )
        db.commit()
        flash("コメントしました!💬✨")
    return redirect(url_for("post_page", post_id=post_id) + "#comments")


@app.post("/comment/<int:comment_id>/delete")
@login_required
def delete_comment(comment_id):
    me = current_user()
    db = get_db()
    c = db.execute(
        "SELECT c.*, p.user_id AS post_owner FROM comments c JOIN posts p ON p.id = c.post_id WHERE c.id = ?",
        (comment_id,),
    ).fetchone()
    if not c:
        abort(404)
    if c["user_id"] != me["id"] and c["post_owner"] != me["id"] and not is_admin(me):
        abort(403)
    db.execute("DELETE FROM comments WHERE id = ?", (comment_id,))
    db.commit()
    flash("コメントを削除しました 🗑️")
    return redirect(url_for("post_page", post_id=c["post_id"]) + "#comments")


# -------- プロフィール
@app.route("/user/<username>")
def profile(username):
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    if not user:
        abort(404)
    me = current_user()
    mine = bool(me) and me["id"] == user["id"]
    tab = request.args.get("tab", "posts")
    where = "p.user_id = ?" if (mine or is_admin(me)) else "p.user_id = ? AND p.is_public = 1"
    posts = fetch_posts(where, (user["id"],))
    favorites_rows = fetch_posts(
        "p.is_public = 1 AND p.id IN (SELECT post_id FROM favorites WHERE user_id = ?)", (user["id"],)
    )
    pl_where = "user_id = ?" if mine else "user_id = ? AND is_public = 1"
    playlists = db.execute(
        f"SELECT pl.*, (SELECT COUNT(*) FROM playlist_items pi WHERE pi.playlist_id = pl.id) AS n"
        f" FROM playlists pl WHERE {pl_where} ORDER BY created_at DESC",
        (user["id"],),
    ).fetchall()
    return render_template(
        "profile.html", user=user, mine=mine, tab=tab,
        posts=posts, favorites=favorites_rows, playlists=playlists,
    )


@app.post("/profile/icon")
@login_required
def change_icon():
    me = current_user()
    icon = request.files.get("icon")
    if icon and icon.filename:
        name = save_upload(icon, IMAGE_EXT)
        if name:
            delete_file(me["icon"])
            db = get_db()
            db.execute("UPDATE users SET icon = ? WHERE id = ?", (name, me["id"]))
            db.commit()
            flash("アイコンを変更しました!📸✨")
        else:
            flash("画像ファイル(jpg / png など)を選んでください 🙏")
    return redirect(url_for("profile", username=me["username"]))


@app.post("/profile/bio")
@login_required
def change_bio():
    me = current_user()
    bio = (request.form.get("bio") or "").strip()
    if len(bio) > 500:
        flash("自己紹介は500字までです ✍️(いま" + str(len(bio)) + "字)")
    else:
        db = get_db()
        db.execute("UPDATE users SET bio = ? WHERE id = ?", (bio, me["id"]))
        db.commit()
        flash("自己紹介を更新しました!📝✨")
    return redirect(url_for("profile", username=me["username"]))


# -------- プレイリスト
@app.post("/playlists/create")
@login_required
def create_playlist():
    me = current_user()
    title = (request.form.get("title") or "").strip()
    if not title:
        flash("プレイリストのタイトルを入れてください ✍️")
        return redirect(request.referrer or url_for("index"))
    db = get_db()
    cur = db.execute(
        "INSERT INTO playlists (user_id, title, is_public, created_at) VALUES (?, ?, ?, ?)",
        (me["id"], title, 1 if request.form.get("is_public") == "1" else 0, now_str()),
    )
    post_id = request.form.get("post_id")
    if post_id:
        db.execute(
            "INSERT OR IGNORE INTO playlist_items (playlist_id, post_id) VALUES (?, ?)",
            (cur.lastrowid, post_id),
        )
    db.commit()
    flash(f"プレイリスト「{title}」を作りました!🎶")
    return redirect(request.referrer or url_for("playlist_page", playlist_id=cur.lastrowid))


def get_playlist_or_404(playlist_id):
    pl = get_db().execute(
        "SELECT pl.*, u.username FROM playlists pl JOIN users u ON u.id = pl.user_id WHERE pl.id = ?",
        (playlist_id,),
    ).fetchone()
    if not pl:
        abort(404)
    return pl


@app.route("/playlist/<int:playlist_id>")
def playlist_page(playlist_id):
    pl = get_playlist_or_404(playlist_id)
    me = current_user()
    mine = bool(me) and me["id"] == pl["user_id"]
    if not pl["is_public"] and not mine and not is_admin(me):
        abort(404)
    items = get_db().execute(
        POST_SELECT.replace("FROM posts", ", pi.id AS item_id FROM posts") + " JOIN playlist_items pi ON pi.post_id = p.id"
        " WHERE pi.playlist_id = ? AND (p.is_public = 1 OR p.user_id = ?)"
        " ORDER BY pi.position, pi.id",
        (playlist_id, me["id"] if me else -1),
    ).fetchall()
    return render_template("playlist.html", pl=pl, items=items, mine=mine)


@app.post("/playlist/<int:playlist_id>/toggle_public")
@login_required
def playlist_toggle_public(playlist_id):
    pl = get_playlist_or_404(playlist_id)
    me = current_user()
    if pl["user_id"] != me["id"]:
        abort(403)
    db = get_db()
    db.execute("UPDATE playlists SET is_public = 1 - is_public WHERE id = ?", (playlist_id,))
    db.commit()
    flash("プレイリストの公開設定を変更しました 🔁")
    return redirect(url_for("playlist_page", playlist_id=playlist_id))


@app.post("/playlist/<int:playlist_id>/rename")
@login_required
def playlist_rename(playlist_id):
    pl = get_playlist_or_404(playlist_id)
    me = current_user()
    title = (request.form.get("title") or "").strip()
    if pl["user_id"] != me["id"]:
        abort(403)
    if title:
        db = get_db()
        db.execute("UPDATE playlists SET title = ? WHERE id = ?", (title, playlist_id))
        db.commit()
        flash("タイトルを変更しました ✏️")
    return redirect(url_for("playlist_page", playlist_id=playlist_id))


@app.post("/playlist/<int:playlist_id>/delete")
@login_required
def playlist_delete(playlist_id):
    pl = get_playlist_or_404(playlist_id)
    me = current_user()
    if pl["user_id"] != me["id"] and not is_admin(me):
        abort(403)
    db = get_db()
    db.execute("DELETE FROM playlists WHERE id = ?", (playlist_id,))
    db.commit()
    flash("プレイリストを削除しました 🗑️")
    return redirect(url_for("profile", username=me["username"], tab="playlists"))


@app.post("/playlist/<int:playlist_id>/toggle_item")
@login_required
def playlist_toggle_item(playlist_id):
    pl = get_playlist_or_404(playlist_id)
    me = current_user()
    if pl["user_id"] != me["id"]:
        abort(403)
    post_id = request.form.get("post_id")
    db = get_db()
    row = db.execute(
        "SELECT 1 FROM playlist_items WHERE playlist_id = ? AND post_id = ?", (playlist_id, post_id)
    ).fetchone()
    if row:
        db.execute("DELETE FROM playlist_items WHERE playlist_id = ? AND post_id = ?", (playlist_id, post_id))
        flash(f"「{pl['title']}」から外しました ➖")
    else:
        db.execute(
            "INSERT OR IGNORE INTO playlist_items (playlist_id, post_id) VALUES (?, ?)",
            (playlist_id, post_id),
        )
        flash(f"「{pl['title']}」に追加しました!🎶")
    db.commit()
    return redirect(request.referrer or url_for("playlist_page", playlist_id=playlist_id))


@app.post("/playlist/<int:playlist_id>/move")
@login_required
def playlist_move(playlist_id):
    pl = get_playlist_or_404(playlist_id)
    me = current_user()
    if pl["user_id"] != me["id"]:
        abort(403)
    item_id = int(request.form.get("item_id") or 0)
    direction = request.form.get("dir")  # up / down
    db = get_db()
    items = db.execute(
        "SELECT id FROM playlist_items WHERE playlist_id = ? ORDER BY position, id", (playlist_id,)
    ).fetchall()
    ids = [r["id"] for r in items]
    if item_id in ids:
        i = ids.index(item_id)
        j = i - 1 if direction == "up" else i + 1
        if 0 <= j < len(ids):
            ids[i], ids[j] = ids[j], ids[i]
            for pos, iid in enumerate(ids):
                db.execute("UPDATE playlist_items SET position = ? WHERE id = ?", (pos, iid))
            db.commit()
    return redirect(url_for("playlist_page", playlist_id=playlist_id))



@app.route("/robots.txt")
def robots_txt():
    body = "User-agent: *\nAllow: /\nSitemap: " + request.url_root.rstrip("/") + "/sitemap.xml\n"
    return app.response_class(body, mimetype="text/plain")


@app.route("/sitemap.xml")
def sitemap_xml():
    db = get_db()
    posts = db.execute("SELECT id, created_at FROM posts WHERE is_public = 1 ORDER BY id DESC LIMIT 1000").fetchall()
    root = request.url_root.rstrip("/")
    urls = ['<url><loc>' + root + '/</loc><changefreq>daily</changefreq></url>']
    for p in posts:
        urls.append('<url><loc>' + root + '/post/' + str(p["id"]) + '</loc></url>')
    xml = ('<?xml version="1.0" encoding="UTF-8"?>'
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
           + "".join(urls) + '</urlset>')
    return app.response_class(xml, mimetype="application/xml")


@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404


@app.errorhandler(413)
def too_large(e):
    flash("ファイルが大きすぎます(合計80MBまで)🙏")
    return redirect(request.referrer or url_for("index"))


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
