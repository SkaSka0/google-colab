![](https://user-images.githubusercontent.com/125879861/255391401-371f3a64-732d-4954-ac0f-4f093a6605e1.png)

<br>

<p align="center"><strong>「 A Pyrogram based Telegram Bot to Transfer Files / Folders to Telegram and Google Drive with the help of Google Colab With Multi-Functionality 」</strong></p>

<br>

## 🙏 Credits

This project is based on the original work by
[XronTrix10/Telegram-Leecher](https://github.com/XronTrix10/Telegram-Leecher).

This repository is an independently maintained fork/rework that includes
bug fixes, enhancements, and additional features while preserving the
original GPL-3.0 license.

Special thanks to XronTrix10 for creating the original project.

## 🚀 Project Status

This repository is actively maintained and includes fixes, enhancements, and documentation updates that are not available in the original project.

### Notable Improvements

* Fixed a workspace handling bug that prevented running multiple tasks sequentially.
* Updated and rewritten documentation to match the current codebase.
* Improved upload and download workflows.
* Added various bug fixes and quality-of-life improvements.

This project is independently maintained while preserving compatibility with the original GPL-3.0 licensed codebase.


## 🧩 Codebase Structure

```
main.py                          => Colab launcher / setup script
README.md                        => Project documentation
LICENSE                          => Project license
requirements.txt                 => Python dependency list
custom_thmb.jpg                  => Default bot thumbnail

colab_leecher/                   => Main bot package
├── __init__.py                  => Initializes Pyrogram bot, reads credentials, creates client
├── __main__.py                  => Main bot entry point and command/callback handlers
├── downlader/                   => Downloader modules for various sources
│   ├── aria2.py                 => Direct link downloader using aria2c
│   ├── gdrive.py                => Google Drive file/folder downloader
│   ├── mega.py                  => Mega.nz downloader via megadl
│   ├── manager.py               => Router/manager for download types
│   ├── telegram.py              => Downloader for files from Telegram messages
│   ├── terabox.py               => Fetches Terabox direct link then downloads
│   └── ytdl.py                  => YouTube/other sites downloader via yt-dlp
├── uploader/                    => Upload modules for downloaded results
│   └── telegram.py              => Uploads files to Telegram
└── utility/                     => Utilities, state, and orchestrator
    ├── converters.py            => Video conversion, zip/split, extraction
    ├── handler.py               => Handler for leech/mirror/upload/cancel processes
    ├── helper.py                => General helpers, status bar, link detection, thumbnail
    ├── task_manager.py          => Main task flow manager
    └── variables.py             => Global variables, paths, settings, bot state
```

## **📖 Click To Open The Notebook**

<a href="https://colab.research.google.com/drive/12hdEqaidRZ8krqj7rpnyDzg1dkKmvdvp?usp=sharing" target="_parent"><img src="https://user-images.githubusercontent.com/125879861/255389999-a0d261cf-893a-46a7-9a3d-2bb52811b997.png" alt="Open In Colab" width=200px/></a>

> If the Google Colab notebook link does not work, simply create a new Colab notebook and copy-paste the code from [`main.py`](./main.py) into a single cell, then run it.

## 🎓 **How To**

### Deploy

- <h3>Read <a href="https://github.com/SkaSka0/Telegram-Leecher/wiki/Instructions">INSTRUCTIONS</a></h3>
- <h3>Watch YouTube Tutorial</h3>

[![Watch It](https://img.youtube.com/vi/6LvYd-oO3U0/0.jpg)](https://www.youtube.com/watch?v=6LvYd-oO3U0)

### Google Drive Authentication

- <h3>Read <a href="https://github.com/SkaSka0/Telegram-Leecher/wiki/Google-Drive-Authentication">GOOGLE DRIVE AUTHENTICATION</a></h3>

## **💡 Features**

- Easy To Use With Bot Commands ( Update 🔥 )
- Powerful Video Converter, Convert Videos to mp4 / mkv ( New 🔥)
- Get Restricted Content From Telegram ( Beta Stage )
- Added Custom File Name Support 
- Download Multiple Files or Folders from Multiple Links 
- Support for Multi-Part Archive Extraction of all Type Extensions
- Upload Directly From Colab Container
- Auto Generate Thumbnail From Video Files 
- Download Directly To Google Drive / Mirroring
- Zip Folders/Files
- Split support for all files > 2GB/4GB

## **🔗 Supported Links**

- Direct Download Link ✅
- Google Drive Link ( Auto Authenticate ) ✅
- Telegram File Link ✅
- Video Links ( YouTube and 2000 More Sites 😉 ) ✅
- Mega.nz Link ✅
- Torrent / Magnet Link ❌ ( Intentionally omitted 😔 )
- GDTot, Sharer and Short Links ❌ ( Coming Soon ♨️)

## **🔥 Benefits**

- No need of VPS or RDP
- Immersive Network speed in Google Servers
- Unlimited Storage in Telegram
- Upload Files of size up to 2000 MB
- Premium Upload up to 4000 MB ( Coming Soon ♨️)

## **🚀 UPTO 200 MiB/s Download Speed and 30 MiB/s Upload Speed**

![Image 1](https://user-images.githubusercontent.com/125879861/245217970-aa132967-c304-4b6d-a594-8c57a8f3d066.png)

## **🦉 Problems**

- You need to be aware of Runtime Disconnections
- Limited Disk Storage in Free Colab Account ~84 GB

## **🚨 NOTE:**

- Video splitting is now automatic and can be configured via the `MAX_SPLIT_SIZE` variable in `variables.py`. Files exceeding this size are automatically split into parts.
<!-- - Magnet or Torrent Links are supported, But avoid using, because `Google Colab Strictly Prohibits Torrents` -->
- **First-time setup:** after running the Colab cell and seeing `Colab Leecher Started !` in the logs, send **at least one message** to your `DUMP_ID` group/channel before starting a task — even if the bot is already an admin there. Pyrogram cannot resolve a peer it has no prior interaction with, so without this the bot will fail with a `PEER_ID_INVALID` error as soon as it tries to send the task status message.
- Downloading `YouTube Video without permission of the owner` can lead to copyright issues. Use with Caution

## **🤙🏼 Connect With Us**

<a href="https://t.me/Colab_Leecher" target="_parent"><img src="https://img.shields.io/badge/-Channel-blue?color=white&logo=telegram&logoColor=vlue"></a>

<a href="https://t.me/Colab_Leecher_Discuss" target="_parent"><img src="https://img.shields.io/badge/-Group-blue?color=white&logo=telegram&logoColor=vlue"></a>


## **⚖️ License**

<h4><a href="https://github.com/XronTrix10/Telegram-Leecher/blob/main/LICENSE">GPL-3.0 license</a></h4>

<br>

## **⚠️ You Should NOT use it as it goes against Google Colab's Policy**

> Resources in Colab are prioritized for interactive use cases. We prohibit actions associated with `bulk compute`, actions that negatively impact others, as well as actions associated with bypassing our policies. The following are disallowed from Colab runtime:
>
> - file hosting, `media serving`, or `other web service offerings not related to interactive compute with Colab`
> - `downloading torrents` or `engaging in peer-to-peer file-sharing`
> - using a remote desktop or SSH
> - connecting to remote proxies
> - mining cryptocurrency
> - running denial-of-service attacks
> - password cracking

<sub>Source: <a href="https://research.google.com/colaboratory/faq.html">Colab FAQ</a></sub>

<br>

<h3 align="center">Please Leave a 🌟 If this repo Helped you</h4>

<h4 align="center">Pull Requests are welcome 💗</h4>
