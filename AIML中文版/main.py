# -*- coding: utf-8 -*-

import Kernel

alice = Kernel.Kernel()
alice.learn("cn-test.xml")

while True:
    print(alice.respond(input('>>>')))
