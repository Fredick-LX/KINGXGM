# -*- coding: utf-8 -*-

import Kernel

alice = Kernel.Kernel()
alice.learn("语料/cn-test.txt")
alice.learn("语料/cn-data.txt")
alice.learn("语料/cn-history.txt")
alice.learn("语料/cn-bye.txt")
alice.learn("语料/cn-humor.txt")
while True:
    word = input(">>>")
    if word in ["再见","BYEBYE","byebye","结束"]:
        print(alice.respond(word))
        sys.exit()
    else:
        print(alice.respond(word))
