@echo off
chcp 65001 >nul
title Yapay Zeka Merkezi
cd /d "%~dp0"
python sunucu.py
if errorlevel 1 pause
