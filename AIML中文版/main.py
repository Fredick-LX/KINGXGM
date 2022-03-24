# -*- coding: utf-8 -*-

import Kernel
import sys

alice = Kernel.Kernel()
alice.learn("语料/cn-test.txt")
alice.learn("语料/cn-data.txt")
alice.learn("语料/cn-history.txt")
alice.learn("语料/cn-bye.txt")
alice.learn("语料/cn-苏联笑话.txt")
try:
    alice.loadBrain("brain")
except:
    pass
while True:
    word = input(">>>")
    if word in ["再见","结束"]:
        print(alice.respond(word))
        alice.saveBrain("brain")
        sys.exit()
    else:
        print(alice.respond(word))
