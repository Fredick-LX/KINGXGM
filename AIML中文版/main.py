# -*- coding: utf-8 -*-

import Kernel
import sys

alice = Kernel.Kernel()
alice.learn("语料/cn-test.txt")
alice.learn("语料/cn-data.txt")
alice.learn("语料/cn-history.txt")
alice.learn("语料/cn-bye.txt")
alice.learn("语料/cn-苏联笑话.txt")
alice.learn("语料/cn-emotion.txt")
alice.learn("语料/cn-attitude.txt")
alice.learn("语料/cn-owen.txt")
try:
    flag = input("操作>>>(read/pass)")
    if flag == "read":
        flag = True
        alice.loadBrain("brain")
    elif flag == "pass":
        flag = False
        alice.saveBrain("brain")
except:
        sys.stderr.write("err\n")
        flag = False
while flag:
    word = input(">>>")
    if word in ["再见","结束"]:
        print(alice.respond(word))
        alice.saveBrain("brain")
        break
    else:
        print(alice.respond(word))
input("按任意键退出>>>")
sys.exit()
