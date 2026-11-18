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
              '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
              '<link rel="manifest" href="/manifest.webmanifest">\n'
              '<link rel="icon" type="image/png" sizes="32x32" href="/icon-32.png">\n'
              '<link rel="apple-touch-icon" href="/apple-touch-icon.png">\n'
              '<meta name="theme-color" content="#ffffff">\n'
              '<meta name="apple-mobile-web-app-capable" content="yes">\n'
              '<meta name="mobile-web-app-capable" content="yes">\n'
              '<meta name="apple-mobile-web-app-status-bar-style" content="default">\n'
              '<meta name="apple-mobile-web-app-title" content="ラコマン">\n'
              '<meta name="application-name" content="ラコマン">\n'
              '<title>{% block title %}ラジオコント漫才〜RAKOMAN〜{% endblock %}</title>\n'
              '<meta name="description" content="ラジオコント・ラジオ漫才専門の音声投稿サイト「RAKOMAN（ラコマン）」。コント・漫才・漫談・エピソードトーク・一発ギャグを聴いて、いいねやお気に入りで応援しよう。">\n'
              '<meta name="keywords" content="RAKOMAN,ラコマン,ラジオコント,ラジオ漫才,コント,漫才,漫談,エピソードトーク,一発ギャグ,音声投稿,お笑い">\n'
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
              '.genre-badge{display:inline-block;border:2.5px solid var(--ink);border-radius:999px;padding:4px '
              '14px;font-size:.85rem;font-weight:700;color:#fff;cursor:pointer;text-decoration:none;line-height:1.5}\n'
              '\n'
              '/* ===== ホーム画面に追加 ===== */\n'
              '.app-back{display:none;flex:none;width:40px;height:40px;border:2.5px solid var(--ink);border-radius:50%;background:#fff;\n'
              '  font:inherit;font-size:1.3rem;font-weight:900;line-height:1;cursor:pointer;color:var(--ink);box-shadow:0 3px 0 var(--ink)}\n'
              '.is-app .app-back.show{display:inline-flex;align-items:center;justify-content:center}\n.is-app .app-back.show{width:36px;height:36px;font-size:1.2rem}\n.is-app .app-back.show + .logo .onair{display:none}\n'
              '.is-app .site-header{padding-top:max(10px, env(safe-area-inset-top))}\n'
              '.a2hs-bar{display:none;align-items:center;gap:10px;margin:12px auto 0;max-width:760px;padding:10px 12px;\n'
              '  background:#fffbe9;border:2.5px solid var(--ink);border-radius:18px;box-shadow:0 4px 0 rgba(51,48,59,.12)}\n'
              '.a2hs-bar.show{display:flex}\n'
              '.a2hs-bar img{width:44px;height:44px;border-radius:11px;flex:none}\n'
              '.a2hs-bar .t{flex:1;font-size:.85rem;font-weight:700;line-height:1.4}\n'
              '.a2hs-bar .x{border:none;background:none;font-size:1.2rem;cursor:pointer;color:#9b94a5;padding:4px}\n'
              '.a2hs-modal{display:none;position:fixed;inset:0;z-index:200;background:rgba(51,48,59,.55);align-items:flex-end;justify-content:center}\n'
              '.a2hs-modal.show{display:flex}\n'
              '.a2hs-sheet{background:#fff;width:100%;max-width:520px;border:2.5px solid var(--ink);border-bottom:none;border-radius:24px 24px 0 0;\n'
              '  padding:22px 20px calc(22px + env(safe-area-inset-bottom));max-height:85vh;overflow:auto}\n'
              '.a2hs-sheet h3{margin:0 0 4px;font-size:1.15rem;display:flex;align-items:center;gap:10px}\n'
              '.a2hs-sheet h3 img{width:48px;height:48px;border-radius:12px}\n'
              '.a2hs-sheet ol{padding-left:1.3em;margin:14px 0}\n'
              '.a2hs-sheet li{margin:0 0 12px;line-height:1.6}\n'
              '.a2hs-sheet .ico{display:inline-flex;vertical-align:middle;width:26px;height:26px;border:2px solid '
              'var(--ink);border-radius:7px;align-items:center;justify-content:center;background:#fff;margin:0 2px}\n'
              '.a2hs-sheet .ico svg{width:16px;height:16px}\n'
              '.a2hs-tip{background:#fff6f0;border-radius:12px;padding:10px 12px;font-size:.82rem;color:#7a7484;margin:0 0 14px}\n'
              '.a2hs-foot{background:none;border:none;color:inherit;font:inherit;font-size:.82rem;font-weight:700;text-decoration:underline;cursor:pointer;padding:6px}\n'
              '.is-app .a2hs-foot{display:none}\n'
              '</style>\n'
              '</head>\n'
              '<body>\n'
              '<header class="site-header">\n'
              '  <button type="button" class="app-back" aria-label="戻る">‹</button>\n'
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
              "{% if request.endpoint == 'index' %}\n"
              '<div class="a2hs-bar" id="a2hs-bar">\n'
              '  <img src="/icon-192.png" alt="">\n'
              '  <span class="t">📲 ホーム画面に追加すると、アプリみたいにすぐ開けます!</span>\n'
              '  <button type="button" class="btn btn-small btn-primary" data-a2hs-open>やり方</button>\n'
              '  <button type="button" class="x" id="a2hs-close" aria-label="閉じる">✕</button>\n'
              '</div>\n'
              '{% endif %}\n'
              '<div class="a2hs-modal" id="a2hs-modal">\n'
              '  <div class="a2hs-sheet" role="dialog" aria-modal="true">\n'
              '    <h3><img src="/icon-192.png" alt="">ホーム画面に追加</h3>\n'
              '    <div data-os="ios">\n'
              '      <ol>\n'
              '        <li>画面の <span class="ico"><svg viewBox="0 0 24 24" fill="none" stroke="#33303b" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M12 15V3"/><path '
              'd="M7 8l5-5 5 5"/><path d="M5 12v8h14v-8"/></svg></span> <b>共有ボタン</b> をタップ<br><small>(Braveは画面下、Safariは画面下か上にあります)</small></li>\n'
              '        <li>メニューを下にスクロールして <span class="ico"><svg viewBox="0 0 24 24" fill="none" stroke="#33303b" stroke-width="2.4" stroke-linecap="round"><rect x="3" y="3" width="18" height="18" '
              'rx="4"/><path d="M12 8v8M8 12h8"/></svg></span> <b>「ホーム画面に追加」</b> をタップ</li>\n'
              '        <li>右上の <b>「追加」</b> をタップ → ホーム画面にラコマンのアイコンが出ます📻</li>\n'
              '      </ol>\n'
              '    </div>\n'
              '    <div data-os="android">\n'
              '      <button type="button" class="btn btn-primary" id="a2hs-install" style="display:none;margin:12px 0">📲 ホーム画面に追加する</button>\n'
              '      <ol id="a2hs-android-steps">\n'
              '        <li>右上の <span class="ico"><svg viewBox="0 0 24 24" fill="#33303b"><circle cx="12" cy="5" r="2.2"/><circle cx="12" cy="12" r="2.2"/><circle cx="12" cy="19" '
              'r="2.2"/></svg></span> <b>メニュー</b> をタップ</li>\n'
              '        <li><b>「ホーム画面に追加」</b>(または「アプリをインストール」)をタップ</li>\n'
              '        <li><b>「追加」</b> をタップ → ホーム画面にアイコンが出ます📻</li>\n'
              '      </ol>\n'
              '    </div>\n'
              '    <div data-os="other">\n'
              '      <p>スマホのブラウザでこのページを開いて、共有メニュー(またはメニュー)から<b>「ホーム画面に追加」</b>を選んでください。</p>\n'
              '    </div>\n'
              '    <p class="a2hs-tip">💡 ホーム画面から開いたときは、最初に1回だけログインが必要です(ブラウザとは別あつかいになるため)。</p>\n'
              '    <button type="button" class="btn" data-a2hs-close style="width:100%;justify-content:center">閉じる</button>\n'
              '  </div>\n'
              '</div>\n'
              '\n'
              '<main class="container">\n'
              '{% block content %}{% endblock %}\n'
              '</main>\n'
              '\n'
              '<footer class="site-footer">\n'
              '  <p>📻 ラジオコント漫才〜RAKOMAN〜 — ラジオコント・ラジオ漫才専門の音声投稿サイト</p>\n'
              '  <p class="note">※誹謗中傷、性的な内容はおやめください</p>\n'
              '  <p><button type="button" class="a2hs-foot" data-a2hs-open>📲 ホーム画面に追加する方法</button></p>\n'
              '</footer>\n'
              '<script>\n'
              '{% raw %}// RAKOMAN front script\n'
              'document.addEventListener("DOMContentLoaded", () => {\n'
              '\n'
              '  // ---- ジャンル選択ボタンのビジュアル ----\n'
              '  document.querySelectorAll(".genre-radio").forEach(radio => {\n'
              '    const span = radio.nextElementSibling;\n'
              '    const colors = {"コント":"#ff5470","漫才":"#5aa9ff","漫談":"#2ec4b6","エピソードトーク":"#ffc830","一発ギャグ":"#a66cff","その他":"#7a7484"};\n'
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
              '\n'
              '<script>\n'
              '(function () {\n'
              '  // 削除などの2段階ボタン(Braveは確認ダイアログを止めるため)\n'
              '  document.querySelectorAll("[data-two-step]").forEach(function (btn) {\n'
              '    var orig = btn.textContent;\n'
              '    btn.addEventListener("click", function (e) {\n'
              '      if (btn.dataset.armed) return;\n'
              '      e.preventDefault();\n'
              '      btn.dataset.armed = "1";\n'
              '      btn.textContent = btn.dataset.twoStep;\n'
              '      setTimeout(function () {\n'
              '        if (!btn.isConnected) return;\n'
              '        delete btn.dataset.armed;\n'
              '        btn.textContent = orig;\n'
              '      }, 5000);\n'
              '    });\n'
              '  });\n'
              '  // ジャンル未選択のまま送信したら、その場で知らせる\n'
              '  document.querySelectorAll("form").forEach(function (f) {\n'
              '    if (!f.querySelector(".genre-radio")) return;\n'
              '    f.addEventListener("submit", function (e) {\n'
              '      if (f.querySelector(".genre-radio:checked")) return;\n'
              '      e.preventDefault();\n'
              '      var first = f.querySelector(".genre-radio");\n'
              '      var box = first.closest(".field") || first.parentNode.parentNode;\n'
              '      var m = box.querySelector(".genre-error");\n'
              '      if (!m) { m = document.createElement("p"); m.className = "genre-error";\n'
              '        m.style.cssText = "color:var(--coral);font-weight:700;margin:6px 0 0";\n'
              '        m.textContent = "⚠️ ジャンルを1つ選んでください"; box.appendChild(m); }\n'
              '      box.scrollIntoView({behavior: "smooth", block: "center"});\n'
              '    });\n'
              '    f.querySelectorAll(".genre-radio").forEach(function (r) {\n'
              '      r.addEventListener("change", function () { var m = f.querySelector(".genre-error"); if (m) m.remove(); });\n'
              '    });\n'
              '  });\n'
              '})();\n'
              '</script>\n'
              '\n'
              '<script>\n'
              '(function () {\n'
              '  var html = document.documentElement;\n'
              '  var isApp = (window.matchMedia && matchMedia("(display-mode: standalone)").matches) || window.navigator.standalone === true;\n'
              '  if (isApp) html.classList.add("is-app");\n'
              '  // 戻るボタン(ホーム画面から開いたとき、トップ以外で表示)\n'
              '  var back = document.querySelector(".app-back");\n'
              '  if (back && isApp && location.pathname !== "/") {\n'
              '    back.classList.add("show");\n'
              '    back.addEventListener("click", function () {\n'
              '      if (history.length > 1 && document.referrer && document.referrer.indexOf(location.host) !== -1) history.back();\n'
              '      else location.href = "/";\n'
              '    });\n'
              '  }\n'
              '  var ua = navigator.userAgent;\n'
              '  var os = /iPhone|iPad|iPod/.test(ua) || (/Macintosh/.test(ua) && navigator.maxTouchPoints > 1) ? "ios"\n'
              '         : /Android/.test(ua) ? "android" : "other";\n'
              '  document.querySelectorAll("#a2hs-modal [data-os]").forEach(function (el) {\n'
              '    el.style.display = el.dataset.os === os ? "" : "none";\n'
              '  });\n'
              '  var modal = document.getElementById("a2hs-modal");\n'
              '  function openM() { modal.classList.add("show"); }\n'
              '  function closeM() { modal.classList.remove("show"); }\n'
              '  document.querySelectorAll("[data-a2hs-open]").forEach(function (b) { b.addEventListener("click", openM); });\n'
              '  document.querySelectorAll("[data-a2hs-close]").forEach(function (b) { b.addEventListener("click", closeM); });\n'
              '  modal.addEventListener("click", function (e) { if (e.target === modal) closeM(); });\n'
              '  // Android(Chrome)は「追加する」ボタンで直接追加できる\n'
              '  var deferred = null, inst = document.getElementById("a2hs-install");\n'
              '  window.addEventListener("beforeinstallprompt", function (e) {\n'
              '    e.preventDefault(); deferred = e;\n'
              '    if (inst) { inst.style.display = ""; var st = document.getElementById("a2hs-android-steps"); if (st) st.style.display = "none"; }\n'
              '  });\n'
              '  if (inst) inst.addEventListener("click", function () {\n'
              '    if (!deferred) return;\n'
              '    deferred.prompt(); deferred.userChoice.then(function () { deferred = null; closeM(); });\n'
              '  });\n'
              '  // トップの案内バー(スマホで、まだ追加していない人だけ。✕で非表示)\n'
              '  var bar = document.getElementById("a2hs-bar"), KEY = "rakoman_a2hs_closed";\n'
              '  var closed = false;\n'
              '  try { closed = localStorage.getItem(KEY) === "1"; } catch (e) {}\n'
              '  if (bar && !isApp && !closed && os !== "other") bar.classList.add("show");\n'
              '  var x = document.getElementById("a2hs-close");\n'
              '  if (x) x.addEventListener("click", function () {\n'
              '    bar.classList.remove("show");\n'
              '    try { localStorage.setItem(KEY, "1"); } catch (e) {}\n'
              '  });\n'
              '})();\n'
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
                   '          <input type="radio" name="genre" value="{{ g }}" {{ \'checked\' if post.genre == g }} style="display:none" class="genre-radio">\n'
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
                  '    <form class="inline-form" method="post" action="{{ url_for(\'playlist_delete\', playlist_id=pl.id) }}">\n'
                  '      <button class="btn btn-small btn-danger" data-two-step="⚠️ 本当に削除する(投稿は消えません)">🗑️ プレイリストを削除</button>\n'
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
              '    <form class="inline-form" method="post" action="{{ url_for(\'delete_comment\', comment_id=c.id) }}">\n'
              '      <button class="btn btn-small btn-danger" data-two-step="⚠️ 本当に削除">🗑️</button>\n'
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
                '          <input type="radio" name="genre" value="{{ g }}" style="display:none" class="genre-radio">\n'
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
                '    var h = document.getElementById("img-warn");\n'
                '    if (!h) { h = document.createElement("p"); h.id = "img-warn"; h.className = "note"; this.parentNode.appendChild(h); }\n'
                '    h.textContent = "写真は4枚までです!先頭の4枚だけが投稿されます 📸";\n'
                '  }\n'
                '});\n'
                '</script>\n'
                '{% endblock %}\n'}
app.jinja_loader = DictLoader(TEMPLATES)


GENRES = ["コント", "漫才", "漫談", "エピソードトーク", "一発ギャグ", "その他"]
GENRE_COLOR = {
    "コント": "#ff5470", "漫才": "#5aa9ff", "漫談": "#2ec4b6",
    "エピソードトーク": "#ffc830", "一発ギャグ": "#a66cff", "その他": "#7a7484",
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
            nxt = request.args.get("next") or ""
            if not nxt.startswith("/") or nxt.startswith("//") or nxt.startswith("/\\"):
                nxt = url_for("index")
            return redirect(nxt)
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



# ---------------------------------------------------------------- ホーム画面に追加(アイコン・manifest)
# アイコン画像はこのファイルに埋め込み(app.py 1つだけでデプロイできるように)
APP_ICONS_B64 = {
    "32": (
        "iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAMAAABEpIrGAAABIFBMVEX///7///z///r//fj//Pf/+/T/+PL/9dj9+PP79vH+9fD9"
        "8+378+368ez18uzy8Orx7enm5+m6697i3t/v2HHS1NCo3N3JxsfZwHSwwtStqq+wnnKYhUb/XHn/XHiAgHl0alJyYkZaYGb/W3f/"
        "Wnf/Wnb/WnP/WXf/WXb/WXX/WHX/WHT/WHP/V3P/V3L+V3O6WWVTW2FRWV//VnT/VnL+VnL+VnH9VnL9VnH8VnG1Vlv+VHH6UXH0"
        "UXDiUGnhS2nVTmbSTGTLS2PGS2LISWHASmC6SmDERF2+RV6tR1yfRFioPlSYOU+KSFF/QFBwS1iPOEx4OkuONkuNNUqFM0dyNkhh"
        "T1lcSktLTlZHSFFESFA+RUxkPEpgNENGOEMvKTVpjLfZAAACDUlEQVR42o2T2XKiQBRAkcVKMMYVmepyYnBJQBZriBgog4ALBkUd"
        "RR1NEP//LwZxz+LMeeh+6FN9l74NcQJ/AYGDhOrX1KRgEyD+63PpQQgM/htBeNJU7oIgV3rUQK1InwRZ8ZGrVe6FSmdfS/IHQZFY"
        "+vGRZiVFeXI/3yBXaFa3BgNLZ8vFwVB7Oc1BkjmO5i3Pc4dD1/NM02Ue5JMqamxRVY2V19PqPlrPW3dVviAfhBrTmM3ny/f5aDT3"
        "8dflYu52S/WdILGNPyAWw2AYu43d+sRxLBojxO6+CuWnAyAMJgAgMRgPh8NwgkAxiHD5563wTI+JUCq/mjizBQlHIgigsvnUVXSh"
        "MfJWYMZEYmRbRqdjj0kUJf0mrXJo9K1b3An0LJWbqi3NMBr9xQ0EsmkqfZ/A3zZJBEJ5CEZ93WqaZttckRsh/eP+OnIU+EHONnXT"
        "aLWMjg1C1zkqS5FI9FQAdkfr6M2m3rIBFIZJEA/hkfMQPcNqm2bLDxFKZpLJTOY0RJCk0mzohtoXr8KJTMZXzoQxER85PT9JZ0yg"
        "+EZIYHhkuS9TuZsCyG+UM3XzBHKDB0Th1LpNb4Uaoy2IEJQiAQFBGIIgqA8Sz68brLR7zVLTFcW8jyj+2vO+tsqHkZNLdWsycZzJ"
        "7yO2UZaOEyXzhbsPFJja2dgrnwgG6tuPc+A/BOGyIED/+v5/AQGqwlQrT6FXAAAAAElFTkSuQmCC"
    ),
    "180": (
        "iVBORw0KGgoAAAANSUhEUgAAALQAAAC0CAMAAAAKE/YAAAABIFBMVEX///z///r//ff/+vP/+PH/9vD/9u//66/+9/H+9e/99O78"
        "9O788+307ejR5OX/0C//yDD/pWX/gJf/fpT/fpP/fZL/e5H/eI7/dYz/b4f/a4P/Z4D/ZH3pyHPJqo5Pts2If3X/YXv/XHf/WnX/"
        "WHP/V3X/V3T/V3L/VnT/VnP/VnL/VXL/VXH/VXCYXGj/VHH/VHD/VG/+VHD9VHD9VG/3VG//U3D/U2/9U2//Um//Um7/UW79Um78"
        "U2/8U278Um7yUm3UTWXIS2KvRluPQVNmO0hEP0ZDNUA8Mj02Mz41Mj03MT02MTw1MTw1MDw0MTw0MDszMDwzMDs0MDoxMDswLjot"
        "LzkqLjkmLjgkLTciLTcsKjcpJjIkKTgmJDAkIS6Z4CidAAAWdUlEQVR42u1da1faWrcG1DMEAR27F7dthwfbXTQkVU4I1d02bwMk"
        "JCEhpGluXMT//y/Os5JwFRAQL32H80uXuIgPi7nm7ZlrNVb8AyX2AvoxQf9bvBz8fFm8HIwxGHv538HwGUwmoP/9cPhu8OrHv49O"
        "wzmXp0d/fxxMf3f4IXr2c5hMQH85fPPmU/jOb0evX334zmDEfP/w6vXRt/Bxn968OYze9xwmByv97s0RE77v28nbw0+X0ZTDtyff"
        "vgRj5ujNu8F6zJx8ucrkez853IifmKEGffpnOPzn03DIfBrugv97+smxaAsMZbgBJobjM55+8oudfgH93wn6y+iFL19mDYtzhk8z"
        "OQB9+f3bcKuOhsVv34b79tv3yxkznmpy4Fw+Hp1Er1+evns/nP3+3eng5ZOjjwMX8AwmByv99+u3oQH/8u3d69cfvpMv4cv3D69f"
        "vwtd0eWnt6//HjzjGUwmoC+PXh2eRrPfv46cJlzpm9fvo9mnh6+OBp92zuS3q0y+55MD0Kcfhp6yeHIydJonJ0MV+/Rh+BU9g8nR"
        "Rhx5yokdMHKloxlfH2gyy14tOzk0ecxMszM+ZmYONzaZ5bkiwzAlbqknPw/nwhXPqLIgsBTFsn+KR7yi+JokK7IsVmmG+zNAc1RF"
        "bnu2Zbm+JwkFbknQT6rTHFV1PO3X9fV1V9PaskBzS+n0Mtbj6wzbsJHJP+iK7WjXinR+LjldxZfLJfaOJz8DO/2P5GnX0sE+5KDe"
        "VTpinl/CThNX9M8sV/Rm4Ir+mfRbG538V7WtdSUAhuwfyI6lCPT3xU++FXu8en0SOf2T16/uihA2MfkvsW00DwLMQH1+rfm1/M/F"
        "T34GUZ7kYqEPBqL88qEfS0R58wLZ76tEvetNZr/9lO1rcQS67vgixS9+8tNnLiXZvQ16iczlKYUtSJ5TH0DeP3A0PzAfz9oj8nmx"
        "rV2fDzaieK15VYp75qBLdMWybf2A2Lz9/fOu7kkl9tnHHmSpdcc6JwstdZtN/86FfvpaHvuTljyjZV7bsty91lodkbpaqpb3dYly"
        "5SgZ2exk/kTsGJZp68avX7rueyJVuvPJgRsfFYb/nSoM/3urirzhyaXDc79pmY7s+n67bUlVgvmuJ89kAqLcfbl6/b0m/zip2Lap"
        "+VK5WhPPz48+XnBLPHnAuVwuJDsuJ5mRhZPZq3eHJz9LPMfxpZ8nh++u2PmTOUaQ3abhyWWmkKffvzq64paBsVF2i+V4vsjQdJ4+"
        "o6gCRZ3lMaQZluc5dtaT2VJJ8nXTUSo0PiL/k/+xPLu1IddW4ouFPFUUKvimRVGC4J9atSLQ+bNCkZ9hfXlK7GiW6VXP+Kco9aIE"
        "wFBnfKUmSort+W0/krbv2bIk1ir8GcVwPDtloWtt3dLbtTz/BPVpjmcoSqiJsgOQjmXoEMMI/tENy/HaviOLNYGiGL40vs5V17K0"
        "NomPHh00xxXOhJqk+G3XBEjTmhIT6C237StSTTgrcAN3x9GC4hg6DEeJfWzQHCosFVH2fdvQzRDjYKWDgRF+CkM3bN+XxQrqMVy4"
        "BcrwhIYbZd+PCfqKpZiq5LSdcIVNgs2Fl4A6e55H/IXv4tMMfomJUpWh2CuiHFJbM22nurJy3NPk/bjKA7LnW8Eam7rh+G1Pw8YT"
        "a7UqEZgRSdaIThvRFAv1mCqTv/pJIlJL92s0/6iEPvvz5C0g4zsO4DRRHwLeqsC/e/uezlOQU/r923e8UAVyz3ebAW7D8AD78KTq"
        "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"
    ),
    "192": (
        "iVBORw0KGgoAAAANSUhEUgAAAMAAAADACAMAAABlApw1AAABIFBMVEX///3///r//PT/+PL/9vH/9vD/0zn/yDD+9/H99e/99O79"
        "8+388+788+391mL27+mc09X/jIX/fpT/fpP/bYb/aoP/aoL/aYL/WXb/V3T/VnT/VnP/VnL/VnH/VXL/VXH/VXDmv1anoaLqam1h"
        "pLlxamb/VHH/VHD+VHH+VHD+VG/9VG/6VG//U3H/U3D/U2//Um//Um7/UW79U2/8U2/9UW35U27xUmzlUGrNS2OzR1ykRFmYQlWD"
        "PlBqOkpMRk1UNkRFM0A5Nj84Mz02Mz42Mz01Mz03Mjw4MTw2MTw2MTs1MTw1MDw0MDszMDwzMDsxMDsxLjovLzouLzorLzknLjgl"
        "LTckLTciLTctKzcqJzUlJjQlIi8kIi4kIS0iIC9caPqPAAAWh0lEQVR42u1dC3ei2LL2cdMdTLLM6k53gnhgkjlqCJ6+tydEQYGA"
        "TxAYUMB39/3//+LWBjS+YhKj3ddZ1po1s8ckuou9q+rbX1VtI7k9l8g/Q4E//nh6Zc/GvgLf/vrr2+T1fRsjBb796/LyX+FP9m4M"
        "Cvzx/cunT1+++yuyf2Nfga+fPn2d/GDfxsEW+nqZnlmap/Fzr29rvIX3/0cY8f670UMkPihwwEIHLHTAQgcsdMBCByz0T8FCDIuE"
        "3lcsxOYIHITIzqiwR5GYZogcXxaEMl/Ac3f7pwCdI0qy0wVxFaFA3u+bAjSVF7tuq9pUq81OX+bSzJ5hISYv9dXmYDRwhl5L9RSO"
        "vNsnLPT9gRD7qjl8LF9fX0uDturJeZreJyz0hXcN3ct8/PAR/rm2bLVfTrH7g4W+fv4kdqvDDEwfyYfrQdNRCtRfe4OFLj99Vjpt"
        "5eNUJNCAJx72BgvdXvzZbg3F6fw/lEbVbgln9wYLMf/h3eZosoNAYA/1BJzdGyzE4IsKeGqvjLN7g4UYkjNaA+lpC2VGVa9EsPsT"
        "iWlWdvTO9VQDxTEtjmT2RwEWF/rqQP4YbiJxWPUk8m6PsBBNFRWnOZCvP34AHaRhy/B44n6PsBDF4pIHZuA8ZjJS02uqfZFg9ggL"
        "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"
    ),
    "512": (
        "iVBORw0KGgoAAAANSUhEUgAAAgAAAAIACAMAAADDpiTIAAABIFBMVEX///////v/+/X/+PH/9vH/9vD/9u/+9vD99e/88+3/zzL/"
        "yDD+yDD9xjD79e/78u378uz78ezv6+jHtZGZk5VotfUsw7b/fpT/fZL/fJL/epH/epCjhXn/eZD/a4T/aoL/ZX//ZH7/ZH3/XXj/"
        "XHj/W3b/WHT/VnP/VnL/VXL/VXH/VXCjZWb/VHH/VHD+VHH+VHD+VG/9VG/tVGz/U3D/U2//U27/Um//Um7/UW78U2/2Um3kT2m0"
        "R1ycQlZ5PE1QO0VEMz88OEI7ND43ND83ND43NDs3Mzw9Mj43MTw2Mj02MTw0MTw2MDw1MDw0MDw0MDs0LzszMTwzMDwzMDszMDoz"
        "LzsxLzouLzoxLjorLzknLjgsKjckLDgmJDEiICzhdSf2AAA1r0lEQVR42u19i3baWLK2gd9BJHE8sZlJJ20nPZMZCwhWFNx9elpc"
        "JNz2xCAgOnMUS0hA3v8t/tritiUESEICSa5aqzuxy3Yw9al27bp8dcShPGk5wrcAAYCCAEBBAKAgAFAQACgIABQEAMqTBcCnT5u/"
        "HvUp0zsA8Nsff/y26ftRnza9DQC//v6vf/zjX7/9uu7bUZ8+PQ2A3yoffn779ucPn9aACPUp1NMA+P39m59Bfnr/u/sPQH0K9RQA"
        "fv/47mdL3v3z367fj/oU6pcAqPzxy0+XRH/50y9/VFa/H/Wp1NMA+Pv8C/7u/gNQn0I9dQT8z79+nsm/XKOI37bod/3+pOuT+fvb"
        "gsAPVpDw5sO/1wQRqE+f3nYNLL2/fPv28n1l7TVii37X70+6Pom/vy0R9JuVKPh9bS4J9enTYyoYU8FYLOGwGITCYTkYBQGAggBA"
        "QQCgIABQEAAoCAAUBAAKAgAFAYCCAEBBAKAgAFAQACgIABQEAAoCAAX5AVDPIT8A6jnkB0A9h/wAqEd+ANQjPwDqkR8A9cgPgHoO"
        "+QGQHwD5AVDPIT8A8gMgPwDqOeQHQD3yA6CeQ34AFA77AVAQACgIABQEAAoCAMUSnq8JltR4HgHw5Kwv8FyZZdmrqyu2VLE+RAA8"
        "HanVKldlodFsNlutVrPZEMpspVZDADwV83NsqdESpY5umOOxaX7vSGKrUWL5GgLgSdi/dN0UH0xTV5XBoNORB6qmm+aD2CizNR4B"
        "8AQe/4ZomJrcVxR1Jooi9zVTE5vspxoCIO2Pv9BSzYG8MP4CBLJq6mK9VEMApFkEtiGZal91lb4ylhqsgABIsf2vmg/G6tO/ENl4"
        "aO4DAQiAQz3/TUXvqxukryv7QAAC4FD217QBZe6eLH/9Kss96lMDTdsDAhAAh4n/Gh3K/j1Z1UdjkJGuUhgY6J1GSUAApE/4zzdt"
        "o780vz7WJVGsVkVRgr8uA4O+0b75zCM/QNr0fK0smvIi2tPG7erJyXNLTk6q7fHjQtcxxbI9I4T8ACnQ19gmZf/Rf6pg/RcvT0Be"
        "vgAMVL+OllrTHgYgP0AK9P/mb9r6PACQx9LJ8xfE9JYADF48P5EWCBjo9CGA/ADp0F+1Fg5AHoH959afY4BGgGy2Fi4A+QFSob98"
        "88vCAUzt/8IhNAIUvV3/xCM/QIr0l2+qcwfQ09su9rcQ0NZ7zigA+QFSon8rLgHgan+CgOrcBcimWOGRHyBF+neXD5oyOwBEd/tD"
        "HPByfggo2sONhQDkB0gHPwCcAPq3+fm+xgFYh8D8DFD02RmA/ACp0AMAxtNnW9alNea3ICDpsy8bt64E5AfgUsMP8G4eAnwdV5+v"
        "RQBEAeOOPQhAfoCU6CVjMAsBNgNgND0DBoYkcDzyA6RGX5f0aQyofT15/nI9AE6Ux1kMsAAA8gMkX8+X6+0pAJThnycv1gLg5fOT"
        "/wyVeSromkd+gJQIX6nPboG9zQB4cfLnsDe7B9YrPPYDpAUA17QHeO7RAyAA0gSAeQzwGCAGQAAkHgBcbX4LGHi+BfAIgBQhYNEN"
        "JPvNAyAAuFT0A7fmlh1JL71lAqPsDUYA7L8hfF4LUIcbawGqoxaAAEjJPbCxrAZKjm4gqitIdFYDEQBpYYOpiGZf3ZwMpvoB+iQE"
        "QACk6wxYNISQVIDnjiAEQEpcwKebWSrIS0/ggOoJRACk5h4QrCsYAZAOqX2m5wJGG+cCFDIXUEMApC4KGA+CTQYhAFLiA0RjiYDH"
        "9bOBkAX8HDFbFALgIOwgLZMeDtfHj/Pp4EeYDu4tOSLajcoXDgGQviPA+K7a2CHUkRs/gKZGzxCBANi//UuNgaZomqrGkSEEW7oi"
        "1lf4CrBDwAGgqZulrw9c7I/8AInXC8KsHvz4uMH8imy6sYQhP0Dy9R8XpYDH9U6gr7rxBCI/QPL1Py9ng0G+f1fXMIUOWsIKPxTy"
        "AyRff/mmoamUxbUBcAX3ZYorWJZl3VTFBsvV9vL6kB9gn/rLn963dZnmAzXFVhvYwrUpW7isasbYaANbeGk1/4P8AInXv/35UjJt"
        "9jekOnvTnO8LGJvaV6lVvfzwq8u+AOQHSL7+7Vtx1g+4qPU2KkKFnW8MqVYb7y/fvHnzjz2+PuQH4PbFD/A//1pMhs/O+0cr08ML"
        "NbIz6Kr8EWwPTuJyr68f+QH2picZYDoApEp9s61hH366BPPv9/UhPwC3J34A2A/Q0Wn798ei/aZ/kNeP/AB70kMGWDL69guA4Aj1"
        "D/H6MBW8Hz1fq4m2CwAhgl5t997/63tyxSA4bmdbOoUa2dPp+Diqf58MBNHPv6INXFfC7P39OXpa61nhel0hWzqtNZ1suQJSLlsf"
        "wYfw8TXE5FEscCUBIJ3zVb4Ze1kIw2E/gOV+BVjHel0psVdsRaiTOzdZ09kS59KylnbC2s6bOl9myQLXa14QQuzFggBQ0WwBYNTN"
        "vgiA+WMPtifPfIWvNxpNsLn00Ncg7Wbl3eZi/d3QdeWhDYs7W81Go14Bf3DNhYSCeQsAHQB+FngEQORbmWtchb2q1InlpXZHNYid"
        "oQYLiXdZhsy73B8MBn34kyztHEBFRrMysobaaYsAg/o1ORU4YVdTgQeSHAGgVP/M4/r4iN0+Sa8JxPZtxRzDA65B6XVq5/VtGArB"
        "AwGCOTYGUxRw4D64XTwBL5QWLQCzZv9OoyxwCIAoH314eLkGVFke9DFs5h10+hsN7wIE2OOrg8dQ2qLYbFxfsde1oI6AngSyfrga"
        "lwAwlQAgjz6UV+rNltQhDl+RBz4s74oC40FqNeolthzIERBCADWeAWD6AECsz7I8PPptbWxog8DGp2AAPwSK9FobHAH8bN8YqJUb"
        "D7ojAKzEJABMGQCm1hemjz402O9ufAoEKqx170itpmBhwM+GuLo9AxynADBVAODn1tetRz804y97tSxHMMcA7/VVVewZ4IH+0CjX"
        "OARA2A9/rWxZXxuH+uivOAJFn2GgXPN0FJAA0HYBUPUYBYBpAQB5+EuNmfUjMj7VsaubgIFGyYsbIBlgxd4C0IqX/VMAgOnDLz6Y"
        "RuTWX2DAMB/EqRvYlgHu2DLAsAmUjVEAmAYA1PgSCw8/PJXyQN2bDGTN1MENsCW+tjED7GwBkOq1eNk/2QAgvr/cIA+/sp+Hn3YD"
        "CnEDjfL6k2ClBYD0gJa/cAiA0Mx/zfJNUd3vw293A6rY5NlrdwistgCojZgFAEkGAF+rsPWmZJh+T34FMnyQ8Z/Xf6YfD6wPfaWL"
        "ZzNcutSss26ZHasFQLUNATTjZ/+kAgDu1+xNSwLfP/CV2u2QuWzdsMrBVgVY03T40Jh9qE0LRj5w0IeTQGrdrEIAAkDV3gIwbsXQ"
        "/slsCZuav23qg4HnG7ysQIkPanxahxT9rSaQJiWkPUSCkjEke8ZkUkv2nE0YDHSzvYDA/PV/KTfazgwwSR3E7v1NYFPowvyefL8C"
        "tlRJB4jWAbu3rLYfMogxbQJbCGkD4qxuIUAC4GBaR+or3k4CCwJXAIH56+dr9ZUWANIDGr/3N3n8AFe/sXWv5ldIOc80VdLo02wI"
        "19cff/nln7/OusSmfaDLllB4gH/95y+/fCxz0w6SjlVJ7vcVrxCos7/NXj8vsKLZsQWAnQZbi+P7mzR+gHdv3/xCzL/dLLMKzgBs"
        "T7o6oB2Qq3wggxEf+DVXsd8+k3//8sMn4iBK814Sb3UlpU8g8OHN23fk9a+0ACgkAIzl+5ssfoCfLt+8q0oezE9KN/DkS1DDFcpX"
        "4N1JX6j3fx8cxLybrEUqy6aH8hKBgFR99wZGwIUr1xaAWL6/ieIHuHz7piGaxjZbTK3/QJ58GLmEVp5p9s3nv0/ayPnrstVbIj4Y"
        "HjCgyIYpNt68vfy42gJQBvzF8v1NFD/Am/eiZsryFivAeWxAqr5RuSotjB/03ycgIJ4AZvjbBsQdWzAgy6Ymvn/zd7cWgJi+v4nh"
        "B6jx1x+rD5D22WKB76YJzTs3pZVOzsD//rTJrEQwAHeJLfiD1NCfVXHs0gIQ0/c3IfwAvFC+bkpjTd5Wpht/FauXH8sVfjU3t9u/"
        "D9MFHy+r4tfxtroDqRPJbi0A8eQ3SAY/gPCJhcN/881v0NegUF99//bN+z/ck/O7vT5e+AOC/PdVUnnsb0pAPcrfVNcWgFi+v0ng"
        "B+BrcPOXzY3veh/otoBcCQhW4JoX1Xw9/wF+/s9W+XFDDtLO/ke1AMSS3yAB/ACQ+GtKptrfXJQxSEa+vI/Xx5IGBK9FKFsLQBzf"
        "39ingms8eyPqm65+Cpy6CmnQqdRq+3h9sxYkzRUCDvbPgWFvAYh5KjiGxSChXG62zQ01P2L+zrIxY0/FKKsRpQPBgBMCdv5fyAA7"
        "SsBxLwbFrug/Df62ZGCt1ix+v+VoHk4CCAa2BKZm6ypmPYCJ6gcQKqXmg7k+ET+twTS2NmdyUTWjNqAsoW2CgNZulioCAiDo438j"
        "gpfd5PytQvyh+ixJU9JN68HlIFgeCLop3rA1HgEQ4AmD4L+94fGHa/+DWyvOvhuTGhYE1gFAGZjtJmAUAeDb/qW6aOj99YT6YP4G"
        "e/AxS0hRWrGAOnAGgPOEQF83xHqphgDw2e5P7v7fBmvbsKDoAmd/HAKsKQTgUrguIzT4ZkpNlq8hAHxEf+VKSzPktaE/KbvGw/zT"
        "WIBAYMMGmI6hta7LAgLA8zNFLn/qYH21RWpexyqy4oWrRsfxMunFcAOVIDaWF8Kjg1H2rReeRH9rI2tt3GnVy0K85DMMgQ02tguR"
        "WJB3fFctfELC2APAarbigLJvys7oKnxLXx/9qQ/izT+v1n/zYaRsp4Fy3QKnt3jb98yYKWvCQX3ZXgFAOitKwLck3DRmXI2ussH9"
        "A8OW1IqhiMbWCQVyDNi+Z8pMCe2qpd1YyJICAIu37Zp0WQJ3lzrjanQVY1PPJ1A0xFBMDxMqELvavoVMHljMlM2ba7bki3gmeQDg"
        "ifVrpMVWtUawLK7GzhrZ/GYqnRhK39sQEf0t8mA6pgZtZqR/VSAY4FMKAJIw46GIrlpN9rLfGcwUC5lXhFVhpkU6wh8ir3W0n2sy"
        "DHIOCIXHAE2/doZFlVr1q/K+g4GjvSTKoGhGrI+m3kI8Y5U29+sFjiKv6E7L5n20/vYQAZobgHSE3Wv9+CjqlH6dFMtk9Pwe3QAp"
        "cdb3WTiItCWsRpr50fx+IQCJ7rWFgyTxA/C1qwZUdNH8fiFASl1X7sFgkvgBatN+Ljz7/ccCA/PBtYkkUfwApKFjbadMr9ftdu+f"
        "tnSJ9NZ2O7k0kSSIHwBKHGxDcu3nIrZXh6PJ5MdTl8lkMhqqgALXzIAprXDKJYkfACgS+sbq4w/G18D26q1UvSg+ebmoSrdDQIHm"
        "hgHZ6DtGChLFDwAUGauTvL2uNpncSxfF87PTbCaTOXrSkslkc4Wz8+KFpBIM9FaPAZgqriWSH+Dt339tGSsV3W53NLkTi2enGfKr"
        "M0yhcPqkpcAwxznyHLw6K4rdyWjFDQxUo0UhIEH8AJcfW6az3iOD+aXiWY7YHn71/DEKSB6eAwZQkDsrSgABh89UVJNGQGL4AX56"
        "33KGfz1i/vPXmexxAW2/ioLCcTZzdk4gYD8IlG+29QKJ4QdoGqrd/t0hmD+fyRUYNLe7MIVcJg8QGHYdPoDmF04IP8DHpmY//3vd"
        "yZ/Fs8wxmn8zBI4zZ8W7id0JDFSNRkAS+AF+hSUZNvt31Un1DJ5+tPE2AS9wVp2oNicwAIrRkpAcfoCVLWlqdzQsZrP49HvzAtls"
        "cTSyIcCxZi7m/ADWmtyO3f7SeYZB83uFAJM5l+wIAJKhkpCUfgBYkmDjyFXvJ9JZBr2/d3lWyJxJk3s7zVCUiyZCBQCsSbVvybqf"
        "iGfZUzSrHznNnok2BBCm8eh2TR6F2v352b4lCez/OovPv99Y0IkAoBr+HFmv6FGEBwDx/1k8/v0HAlnHKRDlIRAiAPjPN7YtKRD/"
        "neHzH9AH2CJB2DcX2cLpozAdQIu+AXRHtxj/BUVA5uyWRkA/uo2zRyFyujT6VAq4p47O0f7BEXA+UnpUShjSQbWYA0Ao2yLA7qSI"
        "9t8FAcVJ17FyIt4AAAdAZ4C6E/FVHgPA4IFg/pVoSwhF5QKOwowAlg6g99jFC8BuCMicddVe9HvnwwIAbMpuUzkgPABCOQTuKVqE"
        "Ntk7GF8A2B0AuQHm0AHs5gJytrtgVC4gvCOAZknqTvAGEMZNgIoDB4YU5xgAxgA0Wwoon8fWrx0ln2ds6aDvDbYWWwA4TgCMAMK/"
        "CsqEej7GMQB1AvRIBJAPvX+WIa3k0ExO/md9lHYfkydRQI86A+IbA0AZSI8qB2SZncnlsqSH3pomsf7MZnM5S8M8mWyQ1oggDAyn"
        "JQxOAGpX4mMvrBwAWHg6PJEtnJ2dnYNYM1XkL/BxwdLkjgtpbTiDsuB/lwzE8hjuATHlB+ArFFNidySGcQAQ44OFc2D4YhGm6O57"
        "w9FoRGZKJ/DnsHcPA4aAhTMYNiHzBqkEQT5PhYEDU6x8iSc/AH9db+tKmCeANSuRyYPtxVsYKgGbDzVtNlVOpqp7qqYNrc93b0VA"
        "Qd4CAZPqMwByQfWY8gPUWJgFWABA2zULzBSekWmp86J0O/oBlu91pzZ34Rjo9gAHP0a3EoAAxs6eHRYD+Wmceno6DVPzYZwBXW1Z"
        "Ehw23saTH0C4oi6BkAQo5HaxPpPNZGFe8o4YH4zc20wxo5AvISAgg6fwncyBMGBN+VnxSmYaplpB6q4haq4gjRbvbGdcfXMZS34A"
        "nq4EdycXwR0AGZGyrG9Nza8j0HDjHSDEA1MMHGACbTrimWVen83iVBKlviZIzu0GSCZ7sTwDZEOKKz8AT8eAEAKcBn2KspnX59Xb"
        "yQSs75dbipBPTCa3VTKDut+7IcNAHPr6DCb9pTvVilMhTFXvJGBCOHsNYewOr8aZCyIuIH78ADwnLGPA3vegl0BifjImDROSnh/9"
        "FQwA4wZMoe8RAmSmD0Z7L6QecH0A5UuPkB+RXwDuLJNJT7o4P8sEn4uEIKC3LAqDC7iMIz8AX6HGAXrD20AAsMx/cUuIEno7MGz1"
        "CA/F7cW+IDCd6r2QRrMjq+cIUuFcGgEGAk9GAwBuhz2HC4gdPwBUgpbpCsgDv/ZfCYapODB/Fx7+3s4saz1wA10CgehjATD/axjl"
        "mkCw2lv3YnpDwACcS4HGY5ncayobTHaRv4shPwBJBFNZADH3zH8ftGV+bYP5FWBWHwz6styR5T78TdnAOU/IiB4tCDyLeJDvlDB7"
        "9DajFtSEHaUQaETyWU6ks8GKUX3zIXb8AAAAOgb0fQlgyGR8F+ailXVk6p3pbgVYrmBauzZMgyydgAUM6/jnezCUfgexwP9jouze"
        "z1isHt3tTqlrMaRkAkxJ2K4B0B8+Fj/+ETt+ADIRRAMgw/h8jnLwHGndNcZXNMMcA+HwgySJIGRBD4gkPQCr7pisXVkDAjgIbotM"
        "JqpzgExxXoxWeH02QGB0EWBOgsnYAADbqG/KfNz4Aex5oB/+EsFwjLqw40yT38T4Y/2BrNVpNurAo18pw7IxsmwLBtHrsHiqBeuH"
        "9LEFAvdYAB67aKgpmDx52b2u99Ck2yOvxm+nNNwDf3R9TIkdhB8AADBetITf/ygenfr5BV8TSoSeC2eyQoxPVipx5anRyfhpbbpu"
        "j1xrCBjK3A2ggIBAcSGl7hF2CnjsnkXQsJcrDkf3q2lJWZa/gsAfqxnMe8KV4TNAPj0q/nAMiobbG3pYAMBzBHOQ/9d1sb5uwoI4"
        "sk+LrcDCsdUdi7wFhhpXYdlrAIEEX++CAQgFiBNgQj/+T6s/VMfLBuM/6qP5UrCR/gggWHk11VN/gYATAIr2EG538EEBQBhRvo+6"
        "bpz5RltsCsT42zbqwTZOAgKhKbYNt9UE5LHLhzyjOh3gtlkXVj+NxiMZtsBVLRGltgyfUO0Y6FmECcwOAICaYLiTwocEQGGVE8ki"
        "S9fNjtiss6yr8XmXbauwjpRj2XpT7LjspoHHTgx3SrWQXSHxAGM/gu1PTl4+n8nLkxNAwRBAsUKZ4geOKwCw2kJSAQCI/uF9dJ7+"
        "A8W0VieVuJqb9QXuGratCm4YqHGl6XYqxQEBeOxuw+Qpsuzftfn+0UgC44PZX7w4mcmLF/AhgEAajWxeoOsPASsAGBjip1TEAFBA"
        "Kfac7h92LOtSswG7Etz2JcAOClg9Wq9fX61Rwn+wndBY2VIBV7BiaIGARd9wRz+TOjE/GB/M/vLFQl4SFAAGAAK6Sq2Wv/NFm7F6"
        "BIQcBBwKAEwuf7HCiynrY9gMDFe7tti6WW2Cr8H6QbHd3qQkV0bYPaw7ls/CMXARUiDA5E5F2v6yOpaqL4j1KeNTIABVVXqkX84d"
        "zM16RuMKAMh8QJiMQQcCAJN9Vf3hcP99FVasw5IpU9d1k2xbr630HbW9KKUm/FXtOy6EJPoqhNH0A6k5yiLy6BGe/hdu1l9g4Hl1"
        "1LPHAZAszQcFgGKEGgUeBgArPEjW4d9p1Zum0Sdp/oGsmy37PHSt1DJ1ebuyb5hNodVx8lWHRFjnnNsfS8T8LzbIyfOTP4d2qPvo"
        "mlwFAESBV0kHwGoYrfZ1HVZlNZeL4wcE6TXbI74M7zYrVbNp7Svrh48AuLioGlWdG4tg35db7E91dc38kfZfry/FBQCmyH5JNgBW"
        "uRAh+Gs3YcMwTTIFzEg31/yy8difkq3AOWCPBMjI8o4IsE/sKmD/l883Pv4vXr4E+39dyU95np5eBQBcAxJ+C7Ds33UuybphHSRT"
        "wJFK+Tq/SvhpDdG005bvjgCSmb+nzv8qXPe32P+lOP66Whi491oxcQMAjIjxCQaAkwON8CF3mmXYnA40k7TX7tNpb/9KoVxu/a/h"
        "JC7eKRKEG6DtMAb7v9xs/5PntP179FHg7S7oAgA92QBYuUZbG9JgUaZ9usRKekrC3M0HUfL8lXN13W7Ulfl8lurOAP+/zf4QAFSp"
        "kbmeNqJ6p0VPNwGXWwDMh1wnFwBM7pXtGk1CNlEgDFjEjJqy5jcNphTI8krbMQB38NeBM0I2xgZy/nuw/2hZFOzpf0o0AjxxaKQN"
        "AEw+W7XFfxD9t9jPNcuMgrThIQ+khOxgS7etL/WVhXFOaZwuzy5Zh/vfyTb7nwwfe8tS8ah60tbl5XH0KhcIANpDvZJUADCODifr"
        "+J/vSYYJUxvVsK30HVAJC6ybiu0+aGVhmF0dAMwmerH/f3TZFjIAIhatjF1PRJopA4AjjQLRGrUg1fZjps0vVKAfVAm3gQdbKOi3"
        "ZYnia1hGAF/BmtvtL1H2/wohA0kKLmJCKwqIHwACtoR5AwB5hujWedm2IJfn4Dbfpw6H9s0y2g2uFMgW4z7drx+MwxZ2eSwyuuQA"
        "2HYBsCcAvlohA/nkAhTK8Hx796RfAByEH8ArABxTDnBdl25oAlSSz1vk8PvqarIvmFJgbyQ6TRBwdIW0Z36lMgC+EgBfR1PEkLBQ"
        "9tM+6xMAh+EH8AgAuADYEgBg/3plNaPfsTL6Hfd0fzBlpS7ZecwDzK4wFGGPPJK23AAcCYBFyGj5BXkORA93Ul8AOBQ/gEcAOAKA"
        "jgHPv7OmV2q2x1ZNbwyp4fCU5RuJjgP8lONo/u6eZwdgTwDI+p/zkNHuArafRX4AcDB+AG8AIO9g17YOzYX+uMbWZyX/OhumstRo"
        "09vsApCYUPeXHjzPvhIAj0PqygBRQG+Bw0yYHuBg/ACeAOAIAKBg03DbhlarXG1q+gmqFAABVLmoN/TLYkIP6cnbrgCrCQDK/kvf"
        "YB1F+SAAcE0FH44fwAsA8kB/Th0AZBOWe1vD+ra/nZRwF+jYyKzFnK9DgC4DPPY25wBcEgAntJKa89kKQxcADG//8TvPxYkfwAsA"
        "7AGAIm9qa3Fr/N1ZSQYY5eB05tTrJyGg3wQA/Q0vJUP2/CJcAfDRHQAH4wfwAADHAdAftyLchbiWzXbcD3wXpEKALUkg1wSAIz78"
        "6vki6OMIOBw/gBcA2GYcIVUrRLYIb/1WQ0G08RlXfdwEGMLW1PNyB1iTALAHiMsggNkSBPgKAg/GD7AVAHQWbdqxU9m3/TnuS8UW"
        "CPqitIcswNyDKcP/nDx/6TcBQH0FRAizLmHihrYkJPxdAw/FD7ANAPn8qS0FpDX3fgCsEFn4W2oBR9j9DAA9vX3y4qXvBMASAC+g"
        "Jjj7UdrdtnPIVyLoYPwA2wBgjwAjXILngdS+HygOhCTGkEoDrgXApgTAEgCLZOD2csB+U8ERFYPsESD0tNV5/iAA4Pk6zWrvIw6k"
        "slhWJ1CABAB1BohzJyFvrUvtuxgUSTnYHgF+I+Otkdz0tivJIfAtiAugb4HkWrfhArAuAUChZAGA7a8gDf0A4ADuNLphsxxNrseT"
        "kuY09eECbABYewkAB6D31icAXHKBk+LREwAAHQGQG0B584hnlEq2TE8QkAeQ8Tuf8XUTAJaVntUEgEsiYHsPfQoAYI8ASLPO1hHP"
        "KJU0n5G6PQr3C4DFFXA1AfBUAWC7AkAEWPY24hmZsiIZ/l1A4WjB1bQRACdzD7ChaZROBf5I/xGQt01TgQNoehrxjE4JL8B/FOAt"
        "BiC13tF/LJS4JADcY4DUB4F2B2CKtvlPO+cZ4RtUolbC5KhoDvxeBMg1UPZ0DXwEXiC5N9pQMKSugb3Qr4HxAwCpoy/vgHpTohoz"
        "dpv/DKaERhRqw5lVkvfWETpUPSWCTiRgixpuGBqAb17eFcNOBMUPALZpGnAA9HYx54ino7k7IiXM19MuwFuLsLW7ZZa/HW5OBb84"
        "qVZPNgwNk1TwMJpUcBwBYJsEGRi0+3UZ8TT60SutY8gvtTF1lVEeNxWDXhBeoOebOCMAG1/nxaDt3alJB4DtDkiSwOHOfwZUUglh"
        "j2Egk2M8loOnPGEvN/cLyssFeymfDLLPU5rN6wc93PnPIMqHCs1tPPF4BnhtCNkmjoaQwnHKPUB1AQAwy82X0Oc/gyi/3CwxYTWG"
        "hNoStk2WMaCH9UoJB4DtBACu+9Kn8Oc/Ayg/sUtCCa9nQHZxDVAflZPgLgC+tTdnDdTUIE2hSQKAY/Nls8RGMf/pW8mWqKKgt1RA"
        "3k9buMeRES8bFhMOAJpSgxzMXDTzn76VXH15LHg8AxyDIcEPAXowpBjqZFD8AGA/AYDeTBCimf/0qYSX4fsMoAebto+GebkDhD4a"
        "Fj8A2KfBLJ7zqOY//SlJYwi158zLPYAMh1JdYdumw19sbxkJfzg0dvwA9L4Ti9wqwvlPn0q4Ggz8MUbQfU2BXQDdMxrFeHi8+AHy"
        "x3lx4e/keStoVPOfvpSkPXTJ1gPpmLyncsA37wQRax1ApAQR8eIHsIUAy00XEc1/+lLSHeJea8JM1hdFzHYHEDpFTNz4AeiRekJz"
        "v8jNHLAncJEeunlYbrv1VhCiI5r/qnqAXADpGVTUyEiiYscPYAsBCMMtv4fGX29Knvu0XHjulTaKZjjxQhO3cWo0Apq4uPED5Gla"
        "LXl8qGmQ9aOilDPO5X0TRY62E0WuTA1K4xCIIhPDD0DN08E0gNGMGQCaxjcqCPAyJOafKtZu/2UnkNcIINn8AKSJYr4rRdH+bFT4"
        "GAEAVt4vgoCe5pEvBH4jzRdZtN3+1XEYZNHJ4QcgI8H/Xew5keJkfutiIBmLgGx07q05GEYcftz5oYtfnv8v6ZmBXejik8MPcEpV"
        "ggZhbzwNwQUsm5M8lGWDLoxYxH8vKf+/08KI5PAD0NsVOuEuugk5f+35eSRxoOZvZcyMNOBEsvHGq8FXxiSIH4BqBunTBdoYXAPJ"
        "i24u6kGkIBhwadSovW1plNUmeNKm9wbttDQqMfwANKsK4YRYksLFIBFEiOOa2rIcBIV5JtjaOH24bW0cmL86pFijdl0blxR+APoW"
        "qHzvLC8BEc9/elTCNaDzXfF3Dwy8OHKsyqEtjkwMPwDFqmLr0ox+/tOTku4W7g3vvFOGMc6ddx5Wx8pqaKtjk9MPAG+UQs2E8rOr"
        "yz7mP70oeXIPXLKF+LDJKgK2LY+WQ1wenSAAQMC8uutuL/OfHpXLaoA69JgI2LA+XnFbH6+Odfv6+Ltd18cnBwB0LXCRBvCx/zNy"
        "5TU1pTTyAwDiA0TH4nvYCDcaj+Q2oMASUWoDKGBQtLe6wtgPSXHCASBTvDD83uY/vSlJJqjvryBM+YBXFxOt61gIK8uP+mg8k5H+"
        "KNutD+5fm1yc+ltcmGwALGuBpmg53lCXg+6orJWXAOj63SLD5DLF7ujeuRBUARDIX0Hgj56ysi50dF/M+NxUkWgAFKlisGj53ZCX"
        "g+6krLHLgRH/+wMYhizAVbuqZ+mqZHu134VlSQbAklVl3g2wx/nP7Up7R4D/TWKwArk4nHQ9QqDbnQyLATYXJxgA9EuflQL2N//p"
        "Za2ovRhwdOrXNoVcBmLBkRcIdLsjiP4yOf/LypLtASYrHkCIxXComwfwDwByDGTP4Z7f6/Y2WR/UkCc4z2aC7KtMSwxgzmKASiyG"
        "Q+cxwE5HgAWB4wxzLo4mw+46DPS63eFkJJ4zmWeB1pUm/Bq4cgu4isVw6O63gOU5cJzJnV/cTiZD8POO1AB8Qh1OJrcX57nMccCt"
        "9SlJBM0jbz4mw6G75gEcEMicnVdvwdSjoUasfn9PsKANRwCL2+r5WSaw+ZOeCh5SvDyV/c5/elAGzwSursTOZM/OixfSrQxGn/z4"
        "Af8bybfSRfH8DFRM8B+dGgAY4vWe5z89KKlagLYLAOB3LQAGMtnCGcBgJudnZwXyOVDt8IMTXg2kdwTU5tXAeAyH2quBj90g24Qd"
        "bqDA5HJg8swRCPyRzeXgUzv+1IQD4M69HyAGw6E79ANsbBdiCiCnp+T/jN/ltKkDwPqOoMMPhwbvCNqzJJgfYKUnsBbnnkAmJQCI"
        "FT9AorqC88dpAECs+AHSOBcQbwDEjB+Angzqx34yKAUAiBs/AD0bSHWFcvGcDUwBAOLGD2BNBy9fdQqmg2MDgCTyA+jJ5weICQAS"
        "ww+QP04ZQ0hsAJAQfgAHR5AtCDg8RxAv2TiCTo8TfwTEjh9ghSWsEiOWsIp/lrD4B4Ex4wdYzxN4+OHQIDyBCbgGxowfgFnDFBqD"
        "4dAATKEJSATFix9gHVdwPIZDab74+OYBE80PsIEt/ODDofQJ4LkhkGFehS1MmvkBHC0B1r6AmhCP4VCyL6DjLwQA2sts6LL96EnV"
        "xhBpujHk8MOhnzhqWohQNuY9rIzJnZ39NWw5y21LQKRsZ1A5HsOhbHmZBvRWCYIV2H/9WwQCEMg/na1h5AyIxXAo73djTD736m8R"
        "yavNCEjV3kDIBQlxGA5tC1QWyNPOKCb316gA8NfNVYh0bQ4dt64fYjAc+nDte3No/m+RSf4J7Q7WpZsYDIcaEhUVHvoE2HYGpGB7"
        "eNW2PFgc9w88HAoLTJu0A/C2PTw6AKR8fbwtFwQTYi2HpQ4xHNqiZsK8ZYHyUcYAqQ4CYc/KKcWvDW0hknHg4VBDou+AI+nUw+KW"
        "fO40KgCcph0AtlQAuIAYDIfSDsBjOyjmAQIDwBYGEufcPPBwaJOKALxXgjETGBQAZMsG5QLgEn7g4VCBSgwTB+CxEwBrAYEBQCpC"
        "VB6udXVzwOHQm6sWlRf0NRSaT0I1MIYAsC3dhZffabDswYZDWbbRWaaFyPbe2HYCpAgAMB+g0Xf08sF6AnmhLAaJABAAuwDA7gJm"
        "EwIH6Qq2pgEG1OaOYtwdQEoAYLsIQEK4/vkwQ0L85/pyazwZCo+9A0gyP8DaTUukLCwcAgH2AyDOI6Ep4QdYs26PJAMOMiUEB4Dp"
        "2N2XTxkAYsUPsG7tsnUTKNf2bv9aib4BeN3ejPwAXFB+gLVrl1XZkITavg8BvlaXDPoAqGZ90jjlg8oT5QdYuQr26HTQ3g8BMg66"
        "TAH5vwLuQPqVZ54kP8DGjZubtslHcg0kN8BgyzsXxYDACb9c8FgjyfwAjufnFX0IKOo6voCIEkFkFESlAwDR3wEAcexORR/mCfID"
        "rOxau6cOgQFJCQt7Gw4VSAp4QB0APjlB8rmzHct++SfID7DxEIC6YKO0r+FQodygh0N8HwBM7mznwi/z9PgBVji1qzQCOtCcWd7T"
        "cGj5hm5E8rW9ed4WvquECoCE8AO4rFwd0QgwpXplL8OhlbpEDwdBCui1L3vkj1/tDIBXwSbQE80P4JIOehz2aASI9XL0w6FC6cZm"
        "f/83wIQAIH78AFvCAOIDbpaRYETDoRD/SfRsWC/Afph8CEdA/gnyA2xFQN+UlneBaIZDwf5t+vwPxAubDyEIzCeiGBRJOZjOBkAg"
        "eEcjwHhozkuDUQyH8nD/f7Dbf1LN+V/jEKdrYPL6AWzh9GvJjgBda7J8LaLh0Bp/1VT0vm19u/gqSEAeo0RQogFgXQVsp8BANVrl"
        "SjRrRYVyraVT+R/L/gGbQGKVCk4wAEhG0HYZVBWYFmmwNT7k4VCoC9TYhmiqis3/B28CYnZZK5b6ljBq2nJbjAVLl+0IgCMbcjeV"
        "WsjDoZAabj7YQgOrByS7Qw/A/qvBNqK1+AIAOm0GdKs1s23ttv0UgEDAEG9KpF4b2nAoK7B10dBX7J+AHpANDbXxBYDhAwBTBNj8"
        "GhwDUpMthTgcWio1pPE32v1b/j9p9oeYKRkAoFj3gHp7q1/Lwt51+8nWMTSxAWt8Qpn/BO/QEDW6/J9U+x/TjOuxBQAEW48q1Wz9"
        "l62XnkL2ddXxew1U86FVaZqGvOP8Z98wm+XWg6kObD+/S+L/xNk/D9fmUS/uACAr+DR/1MtM7hW4NvtvJmtwDjSlXec/rR9iavbH"
        "v9ebXJwmz/6OkYrYAoCjyL96Ws/LTYvJZYuTocO5yQbwB0BV/yHw/OeDJLaaomHIiv3xH06K2RxznEQAqFrsAQAQEA2/nAtMPnN+"
        "Z78OwjkwMDWxeXNd49hrwef8p3DNwhc0gILEVOzeH8L/u/NMPoH2XymexBQANVa00S55mrl/Nr0O9lRnKGC2Ww22dF1zae5b3/bH"
        "C7XrEttoQVeI0/y9rhX+PUug/V0uAbEEgD0TNJIKOY/wPqtONMfvB15ANx/ADbCQGxJWu3x5t08JkPUp1Ztix9QHDvMT919NYvg/"
        "vQMUpFESPEC5oS1Trt6XsBWy2WJ3xQmoSl8zjbbYrLNsmXMDgW3cQ6hxZZYF67cNCP0UdeXxv4XjP6H2t0/WxxcA9nKcj45LhslA"
        "RmDFCUA4CG6AYKAhAAiuAQUwScQ7HnvySe66fMUKDcv6+mDF/OTxF88yDJNM+7uFADENAit0FDjysYWtkGGK8qS7AgHAgAIY6EgA"
        "gjpXumLLFet5B6sLNWusrFJmr1iuDsaXOmB9ZdX6arc7uSvmsgl9/K3iw8oJEE8A0Fv4VPWx56PkxuSIExitnANTP6AZpim3Rbjb"
        "NW4g9AOjg9UJGHjhpgE3RrEtm6ahuTz7Vu8XOf3zTGLtTy6Bq+8KVQiPCT/AbO4mYNf9M4gEziU4B1wgAEUCeaDqhjk2lAdJEkFa"
        "rRb5Q5IeFGNsGroKX+FifTD/cCKdZxP8+LufAFsAcBB+AAsCyz2MFvWGnxYIEgkU79ZAAH5jQAE84ZpugDswx+Mx/N8wdA1MT9LG"
        "rt9DzH9bfJ3c03/Wh+bMA09XcApcvPgBnBdB/5OXBTgHLtZDYI6DwaAvdzqy3Ie/rbE8Zf6zTC7Jj/8aB0AA8MW3faLlB5jWg77b"
        "Cu+n/rqgmEIWIHAPyeENEPAoXTj7ifmzBSbR9rcKQW4AEDnf9omWH2DlDAhCvzOFwC2EgzthoEfML6XA/OscgEWxxHOx4gdwruKc"
        "8e8wvjvnAAJFaQJuICAGwPrDSUrMvzJJt9y7Uv27wMWKH8DKBJRv2jYCniAMXAQCr8+rtxOIBnxjYGr92+r5azj7E2/+tQ4ANp5U"
        "3/u3T6T8AC4uACAQKP/OQDiYPSuKd5Yf8AwCMD6x/p1YPMumw/ykUPJ/7r/sY+NDAPtEyQ8w5+Dq2yqw4qtAKRimAG7AwsDox2jY"
        "2w4C8iVD+Nqp9bNMKsxvMarYD4DHRSLw/ccvXKz4AeYkDLbe7B1oGJnCM3iOz86L0i0BgUae7x6Io8enZ31eI8a/lYrnZ+A7nqXD"
        "+hsOAFUeiR9+D2KfCPkBljR81BRGrzfagYePKRxnM5k8gEC87Y0mk8loONQ0y9XfW0eDpg2H1ud7tyIYP5/JZI9TY33n2m17DNj6"
        "lxDEPhHyA7jP6JLmwMzpDk6wUMhZIAAUFKvS7e0deHqw+Q+wOpwNd7e3UrUItreMnyukyPpWAOBsBaQW8JaEQPaJjh9g7gI+39iJ"
        "eHacwyH8egXwBNnMUSb3lzOQ83PAAgj8ST78Sw40WXjyC0z+OE1SWHMDnK1f3VALPAw/ANWdb78ITKQQOrEZhjzdObKwJQNydHRE"
        "/iD7VnLESzDMcdqk4BygXTcWHxd+gGV3zmf7jN59eL34jCUFkFPyv+mHx6kUl7EZNTqi7aNQ6ZjLDftu4G4yp3EOff47n//HR48n"
        "wKEB4CBkXyCAQbN6D31X7a8+0idAKVyS5aOQVzI4BrUhErw9T3pZdp+Pfy5zfuuM/6i20G9G2KsWjsJeymKnZCRtmcPiX9AJeH38"
        "/1IcDp3x36OtGSRkmv2j0EnZbVsZSD5AhdYsdAIeH39povbWmT+SXStHEexlMezdOtCcObTac9ALbCmDnRWHo3tl7fNv7dsKe8/G"
        "URSLGUxHm2YXnECRQQhsNn8BeiHU7qa6l40WJbYAsGb1vynO8cxpn8aztCXtwrH+8bQVZrTR/NMIIP4eAPJB4ANUZbVJX7LqtTko"
        "2CIK5rluK9kNpU/L/Fsq39/0CLatRQAAkhNuGerApVeT1OzzJJGbI7/56ROXApOblruKYpf0Qq6a/LuNRSf0HEBkACBVAU3rr7Zu"
        "aNCzJV1ACe80O03rP2mB7hVS6pR6k5G2vfmJUGBHsHH1KKIVXVfNjoOkad63BxVdFSq5F0WUCwmaHX6A9V3P/u/f7WMRG+rA8QOA"
        "RdJtDhT39j2VoOAHCrS5aN3umsjv8budRi2iTXtH0e3pvBHN1WNg3i5EWnueumzsen18dNwAxWh2bR5Ft6m1Ump2zP5ARfEvDvNb"
        "K7YqX7hEAQCug0DXCJt8FLTnzvYnS/ai2bYcIQBIo/C1RdmHEPAn3532V7XI9q2H2RK2qq/xwN7XMVWEQPCn31qpsLB/uPYJtynU"
        "VS9UgLS/Q1a6oWk9mV9btb+mL4iRQ7dPWPwA6/W8ULbo+wwFIeDh6X9cbQPVB/PnPwr7hMQPsEn/pVaGta6S7pIYQtl49k+bwB7m"
        "9o/EPqHxA2zSQ6cY+xlooBWEgC/jkyWY1GK9SOwTFj/AFj1wvLJCC53ABgC4TYH0db0lzInxo7FPWPwA2/XCHx+q7bE6eERjexTY"
        "fAHLlK5rkdonNH4AD/p/vLlsKSbeB7zJoG8q4g27yP9GZJ/Q+AG8fP/luzeQGzQQAh7MPzDINj2aF/+3He0TNT+AF/1Plz+9q0qG"
        "MehjZmiDAEWqYUjN65K9/BOJfcLjB/D2/e/evvlAdjpogwFiwN36gwGQpUtNYbpRd9f5f25//ABe9b+xfFN8MAEDMoJglRlXM8m6"
        "BJ7lhIje/8j4AbzqyZWwBCTfHWNswJoB4HslvJ9PXQaED1eDt6QD/OgllnOfAIo4FRxFscFVL/AVtmIRvcOvbDH/6tpTFt3ahQaL"
        "7wg7Prw1vBDt+7+vcvDGMVKuwpJVD4TzXZKk9sNTlnabUKEDJ34NFuVwAr9HQxwKABYGBM7i/4ctUEL9iYsAS8+uiPH3av3DAmC5"
        "94WDXWBPWq6vr+FcXFmLk34AUKvAnrwc6K2PBwBQDiYIAAQACgIABQGAggBAQQCgIABQEAAoCAAUBAAKAgAFAYCCAEB5QgDYT0sY"
        "6mOjP0BTKOrjpI+cHwD18dbvgR8A9XHW74UfAPXx1e+JHwD1cdXvjx8A9bHU75MfAPUx1O+VHyDd+mT+/vvlB0B97PT75gdItT6J"
        "v/8B+AFQHyc9poIxFYzFEg6LQSgcloNREAAoCAAUBAAKAgAFAYCCAEBBAKAgAFAQACgIABQEAAoCAAUBgIIAQEEAoCAAUJAfAPUc"
        "8gOgnkN+ANRzyA+AeuQHQD3yA6Ae+QFQj/wAqOeQHwD5AZAfAPUc8gMgPwDyA6CeQ34A1CM/AOo55AdA4bAfAAUBgIIAQEEAoCAA"
        "UBAAKAgAFAQACgIABQGAggBAQQCgIABQEAAoCAAUBAAKAgAF+QFQzyE/AOo55AdAPfIDoB75AVDPIT8A6jnkB0A9h/wAqOeQH4BD"
        "fgAO+QFQj/wAyA+A/ACoR34A1CM/AOo55AdA4bAfAAUBgIIAQEEAoCAAUBAAKAgAFAQAik3+Px1V+cEkqNukAAAAAElFTkSuQmCC"
    ),
    "maskable-512": (
        "iVBORw0KGgoAAAANSUhEUgAAAgAAAAIACAMAAADDpiTIAAABIFBMVEX///r//Pb/+fL/9vH/9vD/9u/+9vD+9e/99O/79e//zy//"
        "yDD/xzD78+340WvO19U5x7n/fpT/fZP/fZL/fJT/fJLIu6Sjj3tQrOL/e5H/epH/epDVeof/eZD/eY//bIT/a4T/a4P/aoP/aYL/"
        "ZX//ZH7/ZH3/XXj/XHj/W3b/WHX/VnT/VnP/VnL/VXL/VXH/VXCeZWv/VHH/VHD+VHH+VHD+VG/9VHD9VG/4VG//U3D/U2//U27/"
        "Um//Um7/UW7/UW38U2/3U27eTme0RlyVQVSEP1B8PE1YPUdBNEA+Mj43MTw2Mz41Mjw2MTw0MTs1MDw0MDs0LzszMTszMDwzMDsz"
        "MDozLzsyLzovLzopLjkmLjgvLDgkLTcpJzUlIy8XoWkhAAA4aklEQVR42u19C3viRrI2xl7DjM3jTHJiJzvZyW4um00QKCBrJCdf"
        "shE3CYSQdHKU0QXw//8XX7WEpJYQIDw2F1F1zjOZVdseQ710V1e99VaJQztpK+FbgABAQwCgIQDQEABoCAA0BAAaAgDtZAHw88/r"
        "vx7XC7aeAsCv//3vr+u+H9eLtp4AwC+//fjvf//46y+rvh3Xi7dOA+BX9pu3n3/+9pufV4AI1wu4TgPgt3+9eQv26b9+y/4BuF7A"
        "dQoAv/3w97e+/f0/v2d+P64XcD0GAPvf7z77B1n/x2ff/Zdd/n5cL+Q6DYDvwy/4PvsH4HoB16kj4P/9+HZhP2ZGEb9uWP/Y7z/2"
        "9eN8/Ykg8Bs/SHjz7e8rgohvN6x/7Pcf+/oxvv7ENbDx9T8+//wf/2RXXiP+uX79Y7//2NeP8fUnEkG/+omC31bmknC9eOuYCsZU"
        "MBZLOCwGoXFYDkZDAKAhANAQAGgIADQEABoCAA0BgIYAQEMAoCEA0BAAaAgANAQAGgIADQGAhgBAQ30AXOdQHwDXOdQHwHUO9QFw"
        "HfUBcB31AXAd9QFwHfUBcJ1DfQDUB0B9ANQHQH0A1AdAfQBc51AfANdRHwDXOdQHQOOQD4CGAEBDAKAhANAQAGgIADQEABoCAA0B"
        "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"
        "Udj/B9tarD/RhmHdAAAAAElFTkSuQmCC"
    ),
}


def _icon_response(key):
    import base64 as _b64
    resp = app.response_class(_b64.b64decode(APP_ICONS_B64[key]), mimetype="image/png")
    resp.headers["Cache-Control"] = "public, max-age=604800"
    return resp


@app.route("/icon-<key>.png")
def app_icon(key):
    if key not in APP_ICONS_B64:
        abort(404)
    return _icon_response(key)


@app.route("/apple-touch-icon.png")
@app.route("/apple-touch-icon-precomposed.png")
def apple_touch_icon():
    return _icon_response("180")


@app.route("/favicon.ico")
def favicon():
    return _icon_response("32")


@app.route("/manifest.webmanifest")
def manifest():
    data = {
        "name": "ラジオコント漫才〜RAKOMAN〜",
        "short_name": "ラコマン",
        "description": "\"音\"だけのお笑い、それがラコマン。ラジオコント・ラジオ漫才専門の音声投稿サイト",
        "start_url": "/",
        "scope": "/",
        "display": "standalone",
        "background_color": "#ffffff",
        "theme_color": "#ffffff",
        "lang": "ja",
        "icons": [
            {"src": "/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
            {"src": "/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
            {"src": "/icon-maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
        ],
    }
    resp = jsonify(data)
    resp.mimetype = "application/manifest+json"
    return resp


@app.route("/robots.txt")
def robots_txt():
    body = "User-agent: *\nAllow: /\nSitemap: " + request.url_root.rstrip("/") + "/sitemap.xml\n"
    return app.response_class(body, mimetype="text/plain")


@app.route("/sitemap.xml")
def sitemap_xml():
    db = get_db()
    posts = db.execute("SELECT id FROM posts WHERE is_public = 1 ORDER BY id DESC LIMIT 1000").fetchall()
    root = request.url_root.rstrip("/")
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
             '  <url><loc>' + root + '/</loc><changefreq>daily</changefreq></url>']
    for p in posts:
        lines.append('  <url><loc>' + root + '/post/' + str(p["id"]) + '</loc></url>')
    lines.append('</urlset>')
    xml = "\n".join(lines) + "\n"
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
