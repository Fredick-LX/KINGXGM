# -*- coding: utf-8 -*-

from __future__ import print_function
from LangSupport import splitChinese
import copy
import glob
import os
import random
import re
import string
import sys
import time
import threading
import xml.sax
from collections import namedtuple
from configparser import ConfigParser

from constants import *
import DefaultSubs, Utils
from AimlParser import create_parser
from PatternMgr import PatternMgr
from WordSub import WordSub
#输出LOADING在216行
def msg_encoder( encoding=None ):
    """  返回一个 with a pair of functions to encode/decode 消息  的命名元组。
    如果 encoding 为None , 将返回 a pass through function 。    """
    Codec = namedtuple( 'Codec', ['enc','dec'] )
    if encoding in (None,False):
        l = lambda x : unicode(x)
        return Codec(l,l)
    else:
        return Codec(lambda x : x.encode(encoding,'replace'),
                     lambda x : x.decode(encoding,'replace') )


class Kernel:
    # module constants
    _globalSessionID = "_global" # 全局会话的key  (duh)
    _maxHistorySize = 10 # _inputs 与 _responses列表的最大长度。能记忆最近多少个问答对。
    _maxRecursionDepth = 200 # 在响应中止之前 <srai>/<sr> 标签允许的最大递归深度
    # special predicate keys 特殊的谓词键
    _inputHistory = "_inputHistory"     # 最近用户输入queue (list) 的 keys
    _outputHistory = "_outputHistory"   # 最近响应 queue (list) 的 keys
    _inputStack = "_inputStack"         # 在两次调用 respond() 之间，应该经常为空

    def __init__(self):
        self._verboseMode = True
        self._version = "python-aiml {}".format(VERSION)
        self._brain = PatternMgr()
        self._respondLock = threading.RLock()
        self.setTextEncoding( None if PY3 else "utf-8" )

        # 建立会话
        self._sessions = {}
        self._addSession(self._globalSessionID)

        # 设置机器人谓词
        self._botPredicates = {}
        self.setBotPredicate("name", "Nameless")

        # 设置单词替换器 (subbers)，来自WordSub文件:
        self._subbers = {}
        self._subbers['gender'] = WordSub(DefaultSubs.defaultGender)
        self._subbers['person'] = WordSub(DefaultSubs.defaultPerson)
        self._subbers['person2'] = WordSub(DefaultSubs.defaultPerson2)
        self._subbers['normal'] = WordSub(DefaultSubs.defaultNormal)
        
        # 设置元素处理器
        self._elementProcessors = {
            "bot":          self._processBot,
            "condition":    self._processCondition,
            "date":         self._processDate,
            "formal":       self._processFormal,
            "gender":       self._processGender,
            "get":          self._processGet,
            "gossip":       self._processGossip,
            "id":           self._processId,
            "input":        self._processInput,
            "javascript":   self._processJavascript,
            "learn":        self._processLearn,
            "li":           self._processLi,
            "lowercase":    self._processLowercase,
            "person":       self._processPerson,
            "person2":      self._processPerson2,
            "random":       self._processRandom,
            "text":         self._processText,
            "sentence":     self._processSentence,
            "set":          self._processSet,
            "size":         self._processSize,
            "sr":           self._processSr,
            "srai":         self._processSrai,
            "star":         self._processStar,
            "system":       self._processSystem,
            "template":     self._processTemplate,
            "that":         self._processThat,
            "thatstar":     self._processThatstar,
            "think":        self._processThink,
            "topicstar":    self._processTopicstar,
            "uppercase":    self._processUppercase,
            "version":      self._processVersion,
        }

    def bootstrap(self, brainFile = None, learnFiles = [], commands = [],
                  chdir=None):
        """准备一个内核对象以供使用。
    如果提供了brainFile参数，则内核尝试以指定的文件名加载大脑。
    如果提供了learnFiles，则内核将尝试加载指定的AIML文件。
    最后，命令列表中的每个输入字符串都被传递给respond（）。

        在执行任何学习或命令执行之前（但是在loadBrain处理之后），`chdir`参数会使其更改为该目录。
        返回后，当前目录将移回原来的位置。        """
        start = time.clock()
        if brainFile:
            self.loadBrain(brainFile)

        prev = os.getcwd()
        try:
            if chdir:
                os.chdir( chdir )

            # learnFiles可能是一个字符串，在这种情况下应该转换成成一个单一的元素列表。
            if isinstance( learnFiles, (str,unicode) ):
                learnFiles = (learnFiles,)
            for file in learnFiles:
                self.learn(file)

            #  commands 也一样
            if isinstance( commands, (str,unicode) ):
                commands = (commands,)
            for cmd in commands:
                print( self._respond(cmd, self._globalSessionID) )

        finally:
            if chdir:
                os.chdir( prev )

        if self._verboseMode:
            print( "Kernel bootstrap completed in %.2f seconds" % (time.clock() - start) )

    def verbose(self, isVerbose = True):
        """启用/禁用详细输出模式。"""
        self._verboseMode = isVerbose

    def version(self):
        """返回 Kernel's 版本字符串.."""
        return self._version

    def numCategories(self):
        """返回内核学到的类别数量。"""
        #模板和类别templates and categories 之间有一对一的映射
        return self._brain.numTemplates()

    def resetBrain(self):
        """重置大脑到其初始状态。 这实质上相当于：
            del(kern)
            kern = aiml.Kernel()        """
        del(self._brain)
        self.__init__()

    def loadBrain(self, filename):
        """尝试从指定的文件名加载以前保存的“大脑”。
     注意：“大脑”的当前内容将被丢弃！         """
        if self._verboseMode: print( "Loading brain from %s..." % filename, end="" )
        start = time.clock()
        self._brain.restore(filename)
        if self._verboseMode:
            end = time.clock() - start
            print( "done (%d categories in %.2f seconds)" % (self._brain.numTemplates(), end) )

    def saveBrain(self, filename):
        """将bot的大脑内容转储到磁盘上的文件中。"""
        if self._verboseMode: print( "Saving brain to %s..." % filename, end="")
        start = time.process_time()
        self._brain.save(filename)
        if self._verboseMode:
            print( "done (%.2f seconds)" % (time.process_time() - start) )

    def getPredicate(self, name, sessionID = _globalSessionID):
        """从指定的会话中检索谓词“名称”的当前值。
     如果名称在会话中不是有效的谓词，则返回空字符串。        """
        try: return self._sessions[sessionID][name]
        except KeyError: return ""

    def setPredicate(self, name, value, sessionID = _globalSessionID):
        """在指定的会话中设置谓词“名称”的值。
        如果sessionID不是有效的会话，它将被创建。 如果名称在会话中不是一个有效的谓词，它将被创建。          """
        self._addSession(sessionID)   # 如果不存在，则添加会话。
        self._sessions[sessionID][name] = value

    def getBotPredicate(self, name):
        """取回指定的bot谓词的值。   如果名称不是有效的bot谓词，则返回空字符串。         """
        try: return self._botPredicates[name]
        except KeyError: return ""

    def setBotPredicate(self, name, value):
        """设置指定的bot谓词的值。   如果名称不是有效的bot谓词，将会创建。        """
        self._botPredicates[name] = value
        # Clumsy hack: 如果更新机器人名称，我们也必须更新大脑中的名称。
        if name == "name":
            self._brain.setBotName(self.getBotPredicate("name"))

    def setTextEncoding(self, encoding ):
        """
        设置想要的 I/O 文本编码。 从 AIML文件加载的所有内容都会转换成指定的编码形式。
        respond() 方法 is expected to be passed strings encoded with it (str in Py2, bytes in Py3) ，而且也将返回 them.
        如果为False, 那么 strings 被假定不需要解码, 也就是说，文本将是 unicode 字符串 (unicode in Py2, str in Py3)。
        """
        self._textEncoding = encoding
        self._cod = msg_encoder( encoding )


    def loadSubs(self, filename):
        """"加载替换文件。
    该文件必须采用Windows风格的INI格式（有关此格式的信息，请参阅标准的ConfigParser模块文档）。
        文件的每个部分都被加载到自己的替代者中。        """
        parser = ConfigParser()
        with open(filename) as f:
            parser.read_file(f)

        for s in parser.sections():
            # 为此部分添加一个新的WordSub实例。 如果已经存在，请将其删除。
            if s in self._subbers:
                del(self._subbers[s])
            self._subbers[s] = WordSub()
            # 遍历键-值对，并将它们添加到subber   替换者
            for k,v in parser.items(s):
                self._subbers[s][k] = v

    def _addSession(self, sessionID):
        """用指定的ID字符串创建一个新的会话."""
        if sessionID in self._sessions:
            return
        # 创建会话
        self._sessions[sessionID] = {
            # 初始化特殊的保留谓词
            self._inputHistory: [],
            self._outputHistory: [],
            self._inputStack: []
        }
        
    def _deleteSession(self, sessionID):
        """删除指定的会话."""
        if sessionID in self._sessions:
            self._sessions.pop(sessionID)

    def getSessionData(self, sessionID = None):
        """返回指定会话的会话数据字典副本。
     如果没有指定sessionID，则返回包含所有个体会话字典的字典。         """
        s = None
        if sessionID is not None:
            try: s = self._sessions[sessionID]
            except KeyError: s = {}
        else:
            s = self._sessions
        return copy.deepcopy(s)

    def learn(self, filename):
        """加载并学习指定的AIML文件的内容。
    如果filename包含通配符，则所有匹配的文件都将被加载并学习。         """
        for f in glob.glob(filename):
            if self._verboseMode: print( "Loading %s..." % f)
            #start = time.process_time()
            # 加载并解析 AIML 文件.
            parser = create_parser()
            handler = parser.getContentHandler()
            handler.setEncoding(self._textEncoding)
            try: parser.parse(f)
            except xml.sax.SAXParseException as msg:
                err = "\nFATAL PARSE ERROR in file %s:\n%s\n" % (f,msg)
                sys.stderr.write(err)
                continue
            # 在PatternMgr 中保存 pattern/template 对 .
            for key,tem in handler.categories.items():
                self._brain.add(key,tem)
            # 解析是成功的。
            if self._verboseMode:
                pass
                #print( "done (%.2f seconds)" % (time.process_time() - start) )

    def respond(self, input_, sessionID = _globalSessionID):
        """返回内核对输入字符串的响应。"""
        if len(input_) == 0:
            return u""

        # 确保输入是一个 unicode 字符串
        try: input_ = self._cod.dec(input_)
        except UnicodeError: pass
        except AttributeError: pass
        
        # 防止其他线程践踏我们。
        self._respondLock.acquire()

        try:
            self._addSession(sessionID)   # 如果会话不存在，添加会话

            # ?????? discrete ???????
            sentences = Utils.sentences(input_)
            finalResponse = u""
            for s in sentences:
                # ???????????????????????<input />???????
                inputHistory = self.getPredicate(self._inputHistory, sessionID)
                inputHistory.append(s)
                while len(inputHistory) > self._maxHistorySize:
                    inputHistory.pop(0)
                self.setPredicate(self._inputHistory, inputHistory, sessionID)

                response = self._respond(s, sessionID)  # Fetch ??

                # add the data from this exchange to ????
                outputHistory = self.getPredicate(self._outputHistory, sessionID)
                outputHistory.append(response)
                while len(outputHistory) > self._maxHistorySize:
                    outputHistory.pop(0)
                self.setPredicate(self._outputHistory, outputHistory, sessionID)

                finalResponse += (response + u"  ")   # ????????  the final response.?

            finalResponse = finalResponse.strip()
            #print( "@ASSERT", self.getPredicate(self._inputStack, sessionID))
            assert(len(self.getPredicate(self._inputStack, sessionID)) == 0)
            return self._cod.enc(finalResponse)   # ????, ???? ??? I/O encoding

        finally:            # 释放资源锁
            self._respondLock.release()


    # 这个版本的_respond()只是获取一些输入的响应。   它不会混淆输入和输出历史。
    # 从<srai>标签产生的递归调用response()应该调用这个函数，而不是respond()。
    def _respond(self, input_, sessionID):
        """ respond() 的私有版本, does the real work."""
        if len(input_) == 0:
            return u""

        # 警惕无限递归！
        inputStack = self.getPredicate(self._inputStack, sessionID)
        if len(inputStack) > self._maxRecursionDepth:
            if self._verboseMode:
                err = u"警告: 超过最大递归深度！ (input='%s')" % self._cod.enc(input_)
                sys.stderr.write(err)
            return u""

        # 将输入压入输入栈
        inputStack = self.getPredicate(self._inputStack, sessionID)
        inputStack.append(input_)
        self.setPredicate(self._inputStack, inputStack, sessionID)

        # 通过“normal”的subber 运行输入，做一些替换
        subbedInput = self._subbers['normal'].sub(input_)

        # 获取机器人以前的响应，以“that”的形式传递给match（）函数。.
        outputHistory = self.getPredicate(self._outputHistory, sessionID)
        try: that = outputHistory[-1]
        except IndexError: that = ""
        subbedThat = self._subbers['normal'].sub(that)

        # 获取当前的 topic
        topic = self.getPredicate("topic", sessionID)
        subbedTopic = self._subbers['normal'].sub(topic)

        response = u""              # 确定最终的回应。
        elem = self._brain.match(subbedInput, subbedThat, subbedTopic)
        if elem is None:
            if self._verboseMode:
                err = "WARNING: No match found for input: %s\n" % self._cod.enc(input_)
                sys.stderr.write(err)
        else:
            # 将元素处理为响应字符串。
            response += self._processElement(elem, sessionID).strip()
            response += u" "
        response = response.strip()

        # 从输入堆栈弹出顶部条目。
        inputStack = self.getPredicate(self._inputStack, sessionID)
        inputStack.pop()
        self.setPredicate(self._inputStack, inputStack, sessionID)
        
        return response

    def _processElement(self,elem, sessionID):
        """处理一个 AIML 元素。
         元素列表的第一项是元素的XML标签的名称。 第二项是包含传递给该标签的任何属性及其值的字典。
        列表中的任何其他项目都是当前元素的开始和结束标记所包含的元素;  它们由每个元素的处理函数处理。        """
        try:
            handlerFunc = self._elementProcessors[elem[0]]
        except:
            # 糟糕 - 这个元素类型没有处理函数！
            if self._verboseMode:
                err = "WARNING: No handler found for <%s> element\n" % self._cod.enc(elem[0])
                sys.stderr.write(err)
            return u""
        return handlerFunc(elem, sessionID)


    ######################################################
    ###            单独的元素处理函数如下              ###
    ######################################################

    # <bot>
    def _processBot(self, elem, sessionID):
        """"处理一个 <bot> AIML 元素.
        必需的元素属性：
    name：要测试的谓词的名称。    value：测试谓词的值。
    <condition>元素有三种口味。 每个都有不同的属性，每个属性的处理方式都不相同。
        最简单的情况是当<condition>标签同时具有“名称”和“值”属性。 在这种情况下，如果谓词“名称”的值为“值”，则元素的内容将被处理并返回。
    如果<condition>元素只有一个'name'属性，那么它的内容是一系列<li>元素，每个元素都有一个'value'属性。
        从上到下扫描列表直到找到匹配。 可选地，最后一个<li>元素可以不具有“值”属性，在这种情况下，如果没有找到其他匹配，则处理它并返回。

        如果<condition>元素既没有“name”也没有“value”属性，那么它的行为几乎和前面的情况一样，
        除了每个<li>元素（除了可选的最后一个条目）现在都必须包含“name” 和“value”属性。          """
        attrName = elem[1]['name']
        return self.getBotPredicate(attrName)
        
    # <condition>
    def _processCondition(self, elem, sessionID):
        """处理一个 <condition> AIML 元素.

        可选的元素属性：
    name：要测试的谓词的名称。    value：测试谓词的值。

    <condition>元素有三种口味。 每个都有不同的属性，每个属性的处理方式都不相同。

        最简单的情况是当<condition>标签同时具有“名称”和“值”属性。 在这种情况下，如果谓词“名称”的值为“值”，则元素的内容将被处理并返回。
    如果<condition>元素只有一个'name'属性，那么它的内容是一系列<li>元素，每个元素都有一个'value'属性。
        从上到下扫描列表直到找到匹配。 可选地，最后一个<li>元素可以不具有“值”属性，在这种情况下，如果没有找到其他匹配，则处理它并返回。

        如果<condition>元素既没有“name”也没有“value”属性，那么它的行为几乎和前面的情况一样，
        除了每个<li>元素（除了可选的最后一个条目）现在都必须包含“name” 和“value”属性。         """
        attr = None
        response = ""
        attr = elem[1]
        
        # Case #1: test the value of a specific predicate for 测试一下 特定谓词的设置的特定值。
        if 'name' in attr and 'value' in attr:
            val = self.getPredicate(attr['name'], sessionID)
            if val == attr['value']:
                for e in elem[2:]:
                    response += self._processElement(e,sessionID)
                return response
        else:
            # Case #2 and #3: 循环<li>内容，为每个内容测试名称和值对。
            try:
                name = attr.get('name',None)
                # Get the list of <li> elemnents
                listitems = []
                for e in elem[2:]:
                    if e[0] == 'li':
                        listitems.append(e)
                # 如果listitems为空，则返回空字符串
                if len(listitems) == 0:
                    return ""
                # 遍历列表寻找匹配的条件。
                foundMatch = False
                for li in listitems:
                    try:
                        liAttr = li[1]
                        # 如果这是最后一个列表项，则允许它没有属性。 我们现在就跳过它。
                        if len(liAttr) == 0 and li == listitems[-1]:
                            continue
                        # get the name of the predicate to test
                        liName = name
                        if liName == None:
                            liName = liAttr['name']
                        # get the value to check against
                        liValue = liAttr['value']
                        # do the test
                        if self.getPredicate(liName, sessionID) == liValue:
                            foundMatch = True
                            response += self._processElement(li,sessionID)
                            break
                    except:
                        # 没有属性，没有名称/值属性，没有这样的谓词/会话，或处理错误。
                        if self._verboseMode: print( "Something amiss -- skipping listitem", li )
                        raise
                if not foundMatch:
                    # 检查listitems的最后一个元素。 如果它没有“名称”或“值”属性，则处理它。
                    try:
                        li = listitems[-1]
                        liAttr = li[1]
                        if not ('name' in liAttr or 'value' in liAttr):
                            response += self._processElement(li, sessionID)
                    except:
                        # listitems是空的，没有属性，缺少名称/值属性或处理错误。
                        if self._verboseMode: print( "error in default listitem" )
                        raise
            except:
                # 其他一些灾难性的灾难
                if self._verboseMode: print( "catastrophic condition failure" )
                raise
        return response
        
    # <date>
    def _processDate(self, elem, sessionID):
        """处理 <date> AIML 元素.

        <date> 元素 resolve to t当前日期和时间。
        AIML 规格说明 没有对这一信息作出 任何特定格式 的要求, 所以就怎么简单怎么写。         """
        return time.asctime()

    # <formal>
    def _processFormal(self, elem, sessionID):
        """Process a <formal> AIML element.

       <formal>元素递归地处理其内容，然后将结果每个单词的第一个字母大写。

        """                
        response = ""
        for e in elem[2:]:
            response += self._processElement(e, sessionID)
        return string.capwords(response)

    # <gender>
    def _processGender(self,elem, sessionID):
        """Process a <gender> AIML element.

        <gender>元素处理其内容，然后交换结果中任何第三人称单数代词的性别。该补贴由aiml负责。WordSub模块。

        """
        response = ""
        for e in elem[2:]:
            response += self._processElement(e, sessionID)
        return self._subbers['gender'].sub(response)

    # <get>
    def _processGet(self, elem, sessionID):
        """Process a <get> AIML element.

        必要元素属性:
        name：其值应为的谓词的名称从指定的会话中检索并返回。如果谓词不存在，返回空字符串。
        <get>元素从指定的会话。
        """
        return self.getPredicate(elem[1]['name'], sessionID)

    # <gossip>
    def _processGossip(self, elem, sessionID):
        """Process a <gossip> AIML element.

        <gossip> elements are used to capture and store user input in
        an implementation-defined manner, theoretically allowing the
        bot to learn from the people it chats with.  I haven't
        descided how to define my implementation, so right now
        <gossip> behaves identically to <think>.

        """        
        return self._processThink(elem, sessionID)

    # <id>
    def _processId(self, elem, sessionID):
        """ Process an <id> AIML element.

        <id> elements return a unique "user id" for a specific
        conversation.  In PyAIML, the user id is the name of the
        current session.

        """        
        return sessionID

    # <input>
    def _processInput(self, elem, sessionID):
        """处理<input> AIML 元素。

        可选属性元素:
        索引：从历史记录列表到的元素的索引回来1表示最近的项目，2表示最近的项目在此之前，等等。
        <input>元素从输入历史中返回本届会议。

        """        
        inputHistory = self.getPredicate(self._inputHistory, sessionID)
        try: index = int(elem[1]['index'])
        except: index = 1
        try: return inputHistory[-index]
        except IndexError:
            if self._verboseMode:
                err = "No such index %d while processing <input> element.\n" % index
                sys.stderr.write(err)
            return ""

    # <javascript>
    def _processJavascript(self, elem, sessionID):
        """处理 <javascript> AIML 元素。

<javascript>元素递归地处理其内容然后通过服务器端Javascript运行结果解释器来计算最终的响应。
启动位置不需要提供实际的Javascript解释器，而现在PyAIML没有<javascript>元素的行为就像<think>元素一样。

        """        
        return self._processThink(elem, sessionID)
    
    # <learn>
    def _processLearn(self, elem, sessionID):
        """处理<learn> AIML 元素。.

        <learn>元素递归地处理其内容，然后将结果作为AIML文件来打开和学习。

        """
        filename = ""
        for e in elem[2:]:
            filename += self._processElement(e, sessionID)
        self.learn(filename)
        return ""

    # <li>
    def _processLi(self,elem, sessionID):
        """Process an <li> AIML element.

        可选属性元素:
        name：要查询的谓词的名称。value：检查该谓词的值。

        <li>元素递归地处理其内容并返回结果。它们只能出现在<condition>和<random>元素。请参见_processCondition（）和_processRandom（）获取其用法的详细信息。
        """
        response = ""
        for e in elem[2:]:
            response += self._processElement(e, sessionID)
        return response

    # <lowercase>
    def _processLowercase(self,elem, sessionID):
        """处理 <lowercase> AIML 元素。.

        <lowercase> elements process their contents recursively, and
        then convert the results to all-lowercase.

        """
        response = ""
        for e in elem[2:]:
            response += self._processElement(e, sessionID)
        return response.lower()

    # <person>
    def _processPerson(self,elem, sessionID):
        """处理 <person> AIML 元素。
<person>元素递归地处理其内容，然后
将结果中的所有代词从第一人称转换为第二人称
人，反之亦然。这种补贴由
艾米尔。WordSub模块。

如果<person>标签是原子式使用的（例如<person/>），则它是<person><star/></person>的快捷方式。

        """
        response = ""
        for e in elem[2:]:
            response += self._processElement(e, sessionID)
        if len(elem[2:]) == 0:  # atomic <person/> = <person><star/></person>
            response = self._processElement(['star',{}], sessionID)    
        return self._subbers['person'].sub(response)

    # <person2>
    def _processPerson2(self,elem, sessionID):
        """处理 <person2> AIML 元素。

<person2>元素递归地处理其内容，然后将结果中的所有代词从第一人称转换为第三人称人，反之亦然。这种补贴由艾米尔。WordSub模块。

如果<person2>标签是原子式使用的（例如<person2/>），它是<person2><star/></person2>的快捷方式。
        """
        response = ""
        for e in elem[2:]:
            response += self._processElement(e, sessionID)
        if len(elem[2:]) == 0:  # atomic <person2/> = <person2><star/></person2>
            response = self._processElement(['star',{}], sessionID)
        return self._subbers['person2'].sub(response)
        
    # <random>
    def _processRandom(self, elem, sessionID):
        """处理 <random> AIML 元素。
        <random> 元素包含0到多个 <li> 元素.如果没有,回返回空字符串.
        如果出现一个或多个 <li> 元素,随机选取其中一个递归处理并返回其结果.
         只有选定的 <li> 元素内容会被处理.任何非-<li> 元素的内容都会被忽略.        """
        listitems = []
        for e in elem[2:]:
            if e[0] == 'li':
                listitems.append(e)
        if len(listitems) == 0:
            return ""
                
        # select and process a random listitem.
        random.shuffle(listitems)
        return self._processElement(listitems[0], sessionID)
        
    # <sentence>
    def _processSentence(self,elem, sessionID):
        """Process a <sentence> AIML element.

        <sentence> 元素递归地处理其内容然后将结果的第一个字母大写.

        """
        response = ""
        for e in elem[2:]:
            response += self._processElement(e, sessionID)
        try:
            response = response.strip()
            words = response.split(" ", 1)
            words[0] = words[0].capitalize()
            response = ' '.join(words)
            return response
        except IndexError: # response was empty
            return ""

    # <set>
    def _processSet(self, elem, sessionID):
        """Process a <set> AIML element.

        必要元素属性::
            name：要设置的谓词的名称.<set>元素递归地处理其内容,并将结果分配给谓词(由其'name'属性提供)在当前会话中.元素的内容也会被退回.

        """
        value = ""
        for e in elem[2:]:
            value += self._processElement(e, sessionID)
        #print( "@ELEM", elem ) 
        self.setPredicate(elem[1]['name'], value, sessionID)    
        return value

    # <size>
    def _processSize(self,elem, sessionID):
        """Process a <size> AIML element.

        <size> 元素返回当前AIML类别的数量在机器人的大脑里.

        """        
        return str(self.numCategories())

    # <sr>
    def _processSr(self,elem,sessionID):
        """Process an <sr> AIML element.
        <sr>元素是<srai><star/></srai>的快捷方式.

        """
        star = self._processElement(['star',{}], sessionID)
        response = self._respond(star, sessionID)
        return response

    # <srai>
    def _processSrai(self,elem, sessionID):
        """Process a <srai> AIML element.

        <srai>元素递归地处理其内容,然后将结果作为一个新的文件传递回AIML解释器一个输入.这个新输入字符串的结果如下返回.
        """
        newInput = ""
        for e in elem[2:]:
            newInput += self._processElement(e, sessionID)
        newInput = u' '.join(splitChinese(newInput))
        return self._respond(newInput, sessionID)

    # <star>
    def _processStar(self, elem, sessionID):
        """Process a <star> AIML element.

        可选元素属性:索引：当前模式中应该使用哪个“*”字符匹配吗？
        <star>元素返回与“*”匹配的文本片段当前输入模式中的字符.例如,如果输入'你好,汤姆·史密斯,你好吗?'符合模式'你好,你好吗',
        然后是模板中的<star>元素将评估为“汤姆·史密斯”。

        """
        try: index = int(elem[1]['index'])
        except KeyError: index = 1
        # fetch the user's last input
        inputStack = self.getPredicate(self._inputStack, sessionID)
        input_ = self._subbers['normal'].sub(inputStack[-1])
        # fetch the Kernel's last response (for 'that' context)
        outputHistory = self.getPredicate(self._outputHistory, sessionID)
        try: that = self._subbers['normal'].sub(outputHistory[-1])
        except: that = "" # there might not be any output yet
        topic = self.getPredicate("topic", sessionID)
        response = self._brain.star("star", input_, that, topic, index)
        return response
    
    # <system>
    def _processSystem(self,elem, sessionID):
        """Process a <system> AIML element.

        <system> elements process their contents recursively, and then
        attempt to execute the results as a shell command on the
        server.  The AIML interpreter blocks until the command is
        complete, and then returns the command's output.

        For cross-platform compatibility, any file paths inside
        <system> tags should use Unix-style forward slashes ("/") as a
        directory separator.

        """
        # build up the command string
        command = ""
        for e in elem[2:]:
            command += self._processElement(e, sessionID)

        # normalize the path to the command.  Under Windows, this
        # switches forward-slashes to back-slashes; all system
        # elements should use unix-style paths for cross-platform
        # compatibility.
        #executable,args = command.split(" ", 1)
        #executable = os.path.normpath(executable)
        #command = executable + " " + args
        command = os.path.normpath(command)

        # execute the command.
        response = ""
        try:
            out = os.popen(command)            
        except RuntimeError as msg:
            if self._verboseMode:
                err = "WARNING: RuntimeError while processing \"system\" element:\n%s\n" % self._cod.enc(msg)
                sys.stderr.write(err)
            return "There was an error while computing my response.  Please inform my botmaster."
        time.sleep(0.01) # I'm told this works around a potential IOError exception.
        for line in out:
            response += line + "\n"
        response = ' '.join(response.splitlines()).strip()
        return response

    # <template>
    def _processTemplate(self,elem, sessionID):
        """Process a <template> AIML element.
        <template>元素递归地处理其内容返回结果<template>是任何AIML的根节点响应树。
        """
        response = ""
        for e in elem[2:]:
            response += self._processElement(e, sessionID)
        return response

    # text
    def _processText(self,elem, sessionID):
        """Process a raw text element.

        Raw text elements aren't really AIML tags. Text elements cannot contain
        other elements; instead, the third item of the 'elem' list is a text
        string, which is immediately returned. They have a single attribute,
        automatically inserted by the parser, which indicates whether whitespace
        in the text should be preserved or not.
        
        """
        try:
            elem[2] + ""
        except TypeError:
            raise TypeError( "Text element contents are not text" )

        # If the the whitespace behavior for this element is "default",
        # we reduce all stretches of >1 whitespace characters to a single
        # space.  To improve performance, we do this only once for each
        # text element encountered, and save the results for the future.
        if elem[1]["xml:space"] == "default":
            elem[2] = re.sub("\s+", " ", elem[2])
            elem[1]["xml:space"] = "preserve"
        return elem[2]

    # <that>
    def _processThat(self,elem, sessionID):
        """处理 <that> AIML 元素。

        可选元素属性:
        索引：指定要从输出历史记录中删除的元素回来1是最新的回复，2是第二个最新的回复最近，等等。

        <that>元素（当它们出现在<template>元素中时）是<input>元素的输出等价物；他们还了一个内核以前的响应。

        """
        outputHistory = self.getPredicate(self._outputHistory, sessionID)
        index = 1
        try:
            # According to the AIML spec, the optional index attribute
            # can either have the form "x" or "x,y". x refers to how
            # far back in the output history to go.  y refers to which
            # sentence of the specified response to return.
            index = int(elem[1]['index'].split(',')[0])
        except:
            pass
        try: return outputHistory[-index]
        except IndexError:
            if self._verboseMode:
                err = "No such index %d while processing <that> element.\n" % index
                sys.stderr.write(err)
            return ""

    # <thatstar>
    def _processThatstar(self, elem, sessionID):
        """处理 <thatstar> AIML 元素。

        可选元素属性:
        索引：指定<that>模式中要匹配的“*”。

        <thatstar>元素与<star>元素类似，除了其中<star/>返回输入字符串的部分由模式中的“*”字符匹配，<thatstar/>返回前一个输入字符串中由
        当前类别的<that>模式中的“*”。

        """
        try: index = int(elem[1]['index'])
        except KeyError: index = 1
        # fetch the user's last input
        inputStack = self.getPredicate(self._inputStack, sessionID)
        input_ = self._subbers['normal'].sub(inputStack[-1])
        # fetch the Kernel's last response (for 'that' context)
        outputHistory = self.getPredicate(self._outputHistory, sessionID)
        try: that = self._subbers['normal'].sub(outputHistory[-1])
        except: that = "" # there might not be any output yet
        topic = self.getPredicate("topic", sessionID)
        response = self._brain.star("thatstar", input_, that, topic, index)
        return response

    # <think>
    def _processThink(self,elem, sessionID):
        """处理 <think> AIML 元素.

        <think>元素处理 它们的内容是递归的，然后
        放弃结果并返回空字符串。他们是
        用于设置谓词和学习AIML文件，无需
        生成任何输出。"""
        for e in elem[2:]:
            self._processElement(e, sessionID)
        return ""

    # <topicstar>
    def _processTopicstar(self, elem, sessionID):
        """处理<topicstar> AIML 元素.

        可选元素属性:
            index: Specifies which "*" in the <topic> pattern to match.

        <topicstar> 元素 similar to <star> 元素, except  that where <star/> returns the portion of the input string
        matched by a "*" character in the pattern, <topicstar/>
        returns the portion of current topic string that was matched
        by a "*" in  当前 category's <topic> 模式.        """
        try: index = int(elem[1]['index'])
        except KeyError: index = 1
        # fetch the user's last input
        inputStack = self.getPredicate(self._inputStack, sessionID)
        input_ = self._subbers['normal'].sub(inputStack[-1])
        # fetch the Kernel's last response (for 'that' context)
        outputHistory = self.getPredicate(self._outputHistory, sessionID)
        try: that = self._subbers['normal'].sub(outputHistory[-1])
        except: that = "" # there might not be any output yet
        topic = self.getPredicate("topic", sessionID)
        response = self._brain.star("topicstar", input_, that, topic, index)
        return response

    # <uppercase>
    def _processUppercase(self,elem, sessionID):
        """处理 <uppercase> AIML 元素

        <uppercase> 元素 process their contents recursively, and   return the results with all lower-case characters converted to
        upper-case.

        """
        response = ""
        for e in elem[2:]:
            response += self._processElement(e, sessionID)
        return response.upper()

    # <version>
    def _processVersion(self,elem, sessionID):
        """处理 <version> AIML 元素.
        <version> 元素会返回 AIML 解释器的版本号          """
        return self.version()
