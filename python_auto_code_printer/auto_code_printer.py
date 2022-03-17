import time
import pyautogui as pag
time.sleep(2)
f = open("code.txt","r",encoding="utf-8")
data = f.read()
f.close()
pag.typewrite(data,interval=0.1)

