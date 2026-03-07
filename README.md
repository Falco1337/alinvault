<p align="center">
  <img src="assets/vault.png" alt="Alin Vault Logo" width="120">
</p>

<h1 align="center">Alin Vault</h1>

<p align="center">
  <strong>An all-in-one productivity dashboard and system widget built with Python.</strong><br>
  Inspired by system management tools like Huawei PC Manager, optimized for Linux environments.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Version-1.0-blue.svg" />
  <img src="https://img.shields.io/badge/Platform-Linux%20%7C%20Debian-orange.svg" />
  <img src="https://img.shields.io/badge/License-MIT-green.svg" />
</p>

---

# 🌟 Overview

**Alin Vault** is a lightweight desktop productivity dashboard built with **Python and Qt**.

The application combines several daily tools into one interface similar in concept to utilities such as **Huawei PC Manager**, but tailored for **Linux users and developers**.

It integrates:

- a Chromium-powered web hub
- a persistent notepad
- clipboard capture
- system monitoring widgets

This allows users to manage **web tasks, copied text, notes, and system information** without switching between multiple applications.

---

# ✨ Key Features

### 🌐 Integrated Web Hub
Multi-tab browsing powered by **QtWebEngine (Chromium)** with automatic session saving.

### 📝 Smart Notepad
Built-in notepad with **auto-save functionality** so notes are always preserved.

### 📋 Clipboard Capture
Automatically detects and stores text copied via keyboard (`Ctrl+C`).

Useful for storing:

- URLs
- Code snippets
- Terminal commands
- Notes
- Temporary text

Clipboard entries can be quickly accessed from the dashboard.

### 📊 System Monitoring
Inspired by utilities like **Huawei PC Manager**, Alin Vault provides lightweight system widgets such as:

- Real-time clock (Asia/Kuala_Lumpur)
- Battery / energy status
- System indicators

### 🔔 Notification Manager
Internal notification system for alerts and application messages.

### 🛠️ Optimized Chromium Engine
Custom Chromium flags for improved performance and compatibility on Linux systems.

---

# 📥 Installation

## Debian / Ubuntu (.deb)

Download the latest package from the **Releases** page:

> https://github.com/Falco1337/alinvault.git

Install via terminal:

```bash
sudo apt update
git clone https://github.com/Falco1337/alinvault.git
sudo apt install python3-pyqt6 python3-pyqt6.qtwebengine
sudo apt install ./alinvault.deb
