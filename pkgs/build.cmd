pip install pyinstaller
pip install fire
pip install requests


pyinstaller ^
    --uac-admin ^
    --add-data ./apps;apps ^
    -F ^
    install.py

